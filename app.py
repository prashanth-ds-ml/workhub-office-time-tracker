"""FastAPI backend for Office Time Tracker / WorkHub v1.1.

The backend keeps the same calendar-driven attendance rules and summary APIs,
but now persists to MongoDB by default with a JSON fallback for local dev.
The Python desktop app uses this API for the office dashboard experience.
"""

from __future__ import annotations

import calendar
import base64
import hashlib
import hmac
import json
import os
import secrets
import smtplib
import threading
import time
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import jwt
from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
from email.message import EmailMessage

from storage import claim_first_admin, delete_row, load_rows, save_rows, storage_health, upsert_rows

load_dotenv()

app = FastAPI(title="Office Time Tracker API")
bearer_scheme = HTTPBearer(auto_error=False)
INDIA_TZ = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

WORKHUB_ENV = os.getenv("WORKHUB_ENV", "development").lower()
JWT_SECRET = os.getenv("WORKHUB_JWT_SECRET", "development-only-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("WORKHUB_JWT_EXPIRE_HOURS", "12"))
PASSWORD_RESET_MINUTES = int(os.getenv("WORKHUB_PASSWORD_RESET_MINUTES", "30"))
BOOTSTRAP_SECRET = os.getenv("WORKHUB_BOOTSTRAP_SECRET", "")
AUTH_COOKIE_NAME = "workhub_session"
ALLOWED_EMAIL_DOMAIN = os.getenv("WORKHUB_EMAIL_DOMAIN", "sims.healthcare").strip().lower()
configured_cors_origins = [
    origin.strip()
    for origin in os.getenv("WORKHUB_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
ALLOW_SELF_REGISTRATION = os.getenv(
    "WORKHUB_ALLOW_SELF_REGISTRATION",
    "false" if WORKHUB_ENV == "production" else "true",
).lower() == "true"
if WORKHUB_ENV == "production" and JWT_SECRET == "development-only-change-me":
    raise RuntimeError("WORKHUB_JWT_SECRET must be set in production")
if WORKHUB_ENV == "production" and not BOOTSTRAP_SECRET:
    raise RuntimeError("WORKHUB_BOOTSTRAP_SECRET must be set in production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins or [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def web_cache_headers(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    if request.url.path.startswith("/assets/") and response.status_code == 200:
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response

BASE_DIR = Path(__file__).resolve().parent
WEB_DIST_DIR = BASE_DIR / "web_app" / "dist"
WEB_INDEX_FILE = WEB_DIST_DIR / "index.html"
if (WEB_DIST_DIR / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=WEB_DIST_DIR / "assets"),
        name="web-assets",
    )
APP_DATA_DIR = Path(
    os.getenv(
        "WORKHUB_DATA_DIR",
        Path(os.getenv("LOCALAPPDATA", Path.home())) / "WorkHub" / "data",
    )
)
DATA_DIR = APP_DATA_DIR
USERS_FILE = DATA_DIR / "users.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"
BREAKS_FILE = DATA_DIR / "breaks.json"
CALENDAR_EVENTS_FILE = DATA_DIR / "calendar_events.json"
HOLIDAY_MASTER_FILE = DATA_DIR / "holiday_master.json"
ATTENDANCE_POLICIES_FILE = DATA_DIR / "attendance_policies.json"
COMPANY_WORK_POLICY_FILE = DATA_DIR / "company_work_policy.json"
ANNOUNCEMENTS_FILE = DATA_DIR / "announcements.json"
COMPANY_EVENTS_FILE = DATA_DIR / "company_events.json"
ANNOUNCEMENT_READS_FILE = DATA_DIR / "announcement_reads.json"
ALERT_ACK_FILE = DATA_DIR / "alert_acknowledgements.json"

EVENT_TYPES = {
    "WORKING_DAY",
    "HALF_DAY",
    "FULL_DAY_SATURDAY",
    "HOLIDAY",
    "COMP_OFF",
    "LONG_WEEKEND",
    "COMPANY_EVENT",
}
USER_PRIVATE_FIELDS = {"password", "password_reset_hash", "password_reset_expires_at"}

DEFAULT_POLICIES: List[Dict[str, Any]] = [
    {
        "id": "p001",
        "event_type": "WORKING_DAY",
        "min_work_hours": 6,
        "target_work_hours": 6.5,
        "max_break_minutes": 90,
        "created_at": "2026-06-19T00:00:00",
    },
    {
        "id": "p002",
        "event_type": "HALF_DAY",
        "min_work_hours": 3.5,
        "target_work_hours": 4,
        "max_break_minutes": 30,
        "created_at": "2026-06-19T00:00:00",
    },
    {
        "id": "p003",
        "event_type": "FULL_DAY_SATURDAY",
        "min_work_hours": 6,
        "target_work_hours": 6.5,
        "max_break_minutes": 90,
        "created_at": "2026-06-19T00:00:00",
    },
    {
        "id": "p004",
        "event_type": "HOLIDAY",
        "min_work_hours": 0,
        "target_work_hours": 0,
        "max_break_minutes": 0,
        "created_at": "2026-06-19T00:00:00",
    },
    {
        "id": "p005",
        "event_type": "COMP_OFF",
        "min_work_hours": 0,
        "target_work_hours": 0,
        "max_break_minutes": 0,
        "created_at": "2026-06-19T00:00:00",
    },
    {
        "id": "p006",
        "event_type": "LONG_WEEKEND",
        "min_work_hours": 0,
        "target_work_hours": 0,
        "max_break_minutes": 0,
        "created_at": "2026-06-19T00:00:00",
    },
    {
        "id": "p007",
        "event_type": "COMPANY_EVENT",
        "min_work_hours": 0,
        "target_work_hours": 0,
        "max_break_minutes": 0,
        "created_at": "2026-06-19T00:00:00",
    },
]

DEFAULT_COMPANY_WORK_POLICY: Dict[str, Any] = {
    "office_hours": {"start": "09:00", "end": "18:00"},
    "rules": {
        "min_work_hours": 6.0,
        "max_work_hours": 9.0,
        "min_break_minutes": 30.0,
        "max_break_minutes": 90.0,
    },
}


def _now() -> datetime:
    return datetime.now(UTC).astimezone(INDIA_TZ)


def _iso_now() -> str:
    return _now().isoformat()


def _ensure_ist(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=INDIA_TZ)
    return value.astimezone(INDIA_TZ)


def _ist_date(value: datetime) -> date:
    return _ensure_ist(value).date()


def _ist_today(reference: Optional[datetime] = None) -> date:
    return (reference or _now()).astimezone(INDIA_TZ).date()


def _session_day(session: Session) -> date:
    return _ist_date(session.start)


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return _ensure_ist(value).isoformat()


def _normalize_session(session: Session) -> Session:
    session.start = _ensure_ist(session.start)  # type: ignore[assignment]
    session.end = _ensure_ist(session.end) if session.end else None  # type: ignore[assignment]
    return session


def _normalize_break(brk: Break) -> Break:
    brk.start = _ensure_ist(brk.start)  # type: ignore[assignment]
    brk.end = _ensure_ist(brk.end) if brk.end else None  # type: ignore[assignment]
    return brk


def _normalize_timestamp_string(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=INDIA_TZ)
    return parsed.astimezone(INDIA_TZ).isoformat()


def _migrate_cached_timestamps_to_ist() -> bool:
    changed = False
    for session in sessions_cache:
        start = _ensure_ist(session.start)
        end = _ensure_ist(session.end) if session.end else None
        if start != session.start or end != session.end:
            session.start = start  # type: ignore[assignment]
            session.end = end  # type: ignore[assignment]
            changed = True
    for brk in breaks_cache:
        start = _ensure_ist(brk.start)
        end = _ensure_ist(brk.end) if brk.end else None
        if start != brk.start or end != brk.end:
            brk.start = start  # type: ignore[assignment]
            brk.end = end  # type: ignore[assignment]
            changed = True
    for event in calendar_events_cache:
        created_at = _normalize_timestamp_string(event.created_at)
        updated_at = _normalize_timestamp_string(event.updated_at)
        if created_at != event.created_at or updated_at != event.updated_at:
            event.created_at = created_at or event.created_at
            event.updated_at = updated_at or event.updated_at
            changed = True
    for announcement in announcements_cache:
        created_at = _normalize_timestamp_string(announcement.created_at)
        if created_at != announcement.created_at:
            announcement.created_at = created_at or announcement.created_at
            changed = True
    for company_event in company_events_cache:
        created_at = _normalize_timestamp_string(company_event.created_at)
        if created_at != company_event.created_at:
            company_event.created_at = created_at or company_event.created_at
            changed = True
    for read_row in announcement_reads_cache:
        read_at = _normalize_timestamp_string(read_row.read_at)
        if read_at != read_row.read_at:
            read_row.read_at = read_at
            changed = True
    for alert in alert_ack_cache:
        created_at = _normalize_timestamp_string(alert.created_at)
        acknowledged_at = _normalize_timestamp_string(alert.acknowledged_at)
        if created_at != alert.created_at or acknowledged_at != alert.acknowledged_at:
            alert.created_at = created_at or alert.created_at
            alert.acknowledged_at = acknowledged_at
            changed = True
    return changed


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256$200000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def _verify_password(password: str, encoded: str) -> bool:
    if not encoded.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(password, encoded)
    try:
        _algorithm, iterations, salt_value, digest_value = encoded.split("$", 3)
        salt = base64.b64decode(salt_value)
        expected = base64.b64decode(digest_value)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _hash_reset_token(token: str) -> str:
    return hmac.new(JWT_SECRET.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def _send_password_reset_email(email: str, token: str) -> bool:
    smtp_host = os.getenv("WORKHUB_SMTP_HOST", "").strip()
    smtp_from = os.getenv("WORKHUB_SMTP_FROM", "").strip()
    if not smtp_host or not smtp_from:
        return False

    smtp_port = int(os.getenv("WORKHUB_SMTP_PORT", "587"))
    smtp_user = os.getenv("WORKHUB_SMTP_USER", "").strip()
    smtp_password = os.getenv("WORKHUB_SMTP_PASSWORD", "")
    use_tls = os.getenv("WORKHUB_SMTP_TLS", "true").lower() == "true"

    message = EmailMessage()
    message["From"] = smtp_from
    message["To"] = email
    message["Subject"] = "WorkHub password reset code"
    message.set_content(
        "\n".join(
            [
                "Use this WorkHub reset code to set a new password:",
                "",
                token,
                "",
                f"This code expires in {PASSWORD_RESET_MINUTES} minutes.",
                "If you did not request this, ignore this email.",
            ]
        )
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
        if use_tls:
            smtp.starttls()
        if smtp_user:
            smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)
    return True


def _create_access_token(user: "User") -> str:
    now = _now()
    return jwt.encode(
        {
            "sub": user.id,
            "role": user.role,
            "iat": now,
            "exp": now + timedelta(hours=JWT_EXPIRE_HOURS),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def _normalize_company_email(value: str) -> str:
    email = value.strip().lower()
    if not email or email.rsplit("@", 1)[-1] != ALLOWED_EMAIL_DOMAIN:
        raise HTTPException(
            status_code=403,
            detail=f"Use your @{ALLOWED_EMAIL_DOMAIN} company email address",
        )
    return email


def _load_json(path: Path) -> List[Dict[str, Any]]:
    return load_rows(path)


def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    save_rows(path, data)


def _upsert_models(path: Path, rows: List[Any]) -> None:
    upsert_rows(path, [row.dict() if hasattr(row, "dict") else row for row in rows])


def _default_2026_holidays() -> List[Dict[str, Any]]:
    created_at = _iso_now()
    holidays = [
        ("h001", "2026-01-01", "New Year", "New Year Holiday"),
        ("h002", "2026-01-15", "Makara Sankranti", "Harvest Festival"),
        ("h003", "2026-01-26", "Republic Day", "India Republic Day"),
        ("h004", "2026-03-03", "Holi", "Festival of Colors"),
        ("h005", "2026-03-19", "Ugadi", "New Year (Karnataka)"),
        ("h006", "2026-03-20", "Ramzan", "Eid-ul-Fitr"),
        ("h007", "2026-08-15", "Independence Day", "India Independence Day"),
        ("h008", "2026-09-14", "Vinayaka Chavithi", "Ganesh Festival"),
        ("h009", "2026-10-02", "Gandhi Jayanthi", "Mahatma Gandhi's birthday"),
        ("h010", "2026-10-20", "Vijaya Dasami", "Dussehra"),
        ("h011", "2026-11-07", "Diwali", "Festival of Lights"),
        ("h012", "2026-12-25", "Christmas", "Christmas Day"),
    ]
    return [
        {
            "id": event_id,
            "event_type": "HOLIDAY",
            "date": event_date,
            "title": title,
            "description": description,
            "created_at": created_at,
            "updated_at": created_at,
            "manager_id": None,
            "related_event_id": None,
        }
        for event_id, event_date, title, description in holidays
    ]


def _holiday_master_rows() -> List[Dict[str, Any]]:
    return [
        {
            "id": event["id"],
            "date": event["date"],
            "title": event["title"],
            "description": event["description"],
            "event_type": event["event_type"],
            "source": "company_circular_2026",
            "updated_at": event["updated_at"],
        }
        for event in _default_2026_holidays()
    ]


def _seed_initial_data() -> None:
    if not USERS_FILE.exists() or not _load_json(USERS_FILE):
        _save_json(USERS_FILE, [])
    if not ATTENDANCE_POLICIES_FILE.exists() or not _load_json(ATTENDANCE_POLICIES_FILE):
        _save_json(ATTENDANCE_POLICIES_FILE, DEFAULT_POLICIES)
    if not COMPANY_WORK_POLICY_FILE.exists() or not _load_json(COMPANY_WORK_POLICY_FILE):
        _save_json(COMPANY_WORK_POLICY_FILE, [DEFAULT_COMPANY_WORK_POLICY])
    if not CALENDAR_EVENTS_FILE.exists():
        _save_json(CALENDAR_EVENTS_FILE, [])
    if not HOLIDAY_MASTER_FILE.exists():
        _save_json(HOLIDAY_MASTER_FILE, [])
    for path in [
        ANNOUNCEMENTS_FILE,
        COMPANY_EVENTS_FILE,
        ANNOUNCEMENT_READS_FILE,
        ALERT_ACK_FILE,
    ]:
        if not path.exists():
            _save_json(path, [])


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    password: str
    role: str = "User"
    is_active: bool = True
    office_hours: Optional[Dict[str, str]] = None
    rules: Optional[Dict[str, float]] = None
    password_reset_hash: Optional[str] = None
    password_reset_expires_at: Optional[str] = None

    @validator("role")
    def _check_role(cls, value: str) -> str:
        if value not in {"User", "Admin"}:
            raise ValueError("role must be 'User' or 'Admin'")
        return value


class UserPublic(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool = True
    office_hours: Optional[Dict[str, str]] = None
    rules: Optional[Dict[str, float]] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class LoginRequest(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    password: str


class RegistrationRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "User"
    bootstrap_secret: Optional[str] = None

    @validator("role")
    def _check_registration_role(cls, value: str) -> str:
        if value not in {"User", "Admin"}:
            raise ValueError("role must be 'User' or 'Admin'")
        return value


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    token: str
    new_password: str


class AdminUserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "User"

    @validator("role")
    def _check_role(cls, value: str) -> str:
        if value not in {"User", "Admin"}:
            raise ValueError("role must be 'User' or 'Admin'")
        return value


class AdminUserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @validator("role")
    def _check_role(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in {"User", "Admin"}:
            raise ValueError("role must be 'User' or 'Admin'")
        return value


class OfficeHoursUpdate(BaseModel):
    start: str
    end: str


class RulesUpdate(BaseModel):
    min_work_hours: Optional[float] = None
    max_work_hours: Optional[float] = None
    min_break_minutes: Optional[float] = None
    max_break_minutes: Optional[float] = None


class CompanyWorkPolicyUpdate(BaseModel):
    office_hours: OfficeHoursUpdate
    rules: RulesUpdate


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    start: datetime
    end: Optional[datetime] = None
    breaks: List[Dict[str, Any]] = Field(default_factory=list)


class Break(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    start: datetime
    end: Optional[datetime] = None


class CalendarEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    date: str
    title: str
    description: Optional[str] = None
    created_at: str = Field(default_factory=_iso_now)
    updated_at: str = Field(default_factory=_iso_now)
    manager_id: Optional[str] = None
    related_event_id: Optional[str] = None

    @validator("event_type")
    def _check_event_type(cls, value: str) -> str:
        if value not in EVENT_TYPES:
            raise ValueError("invalid event type")
        return value


class CalendarEventCreate(BaseModel):
    event_type: str
    date: str
    title: str
    description: Optional[str] = None
    related_event_id: Optional[str] = None


class AttendancePolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    min_work_hours: float
    target_work_hours: float
    max_break_minutes: float
    created_at: str = Field(default_factory=_iso_now)


class CompanyEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    event_date: str
    event_time: str
    location: Optional[str] = None
    organizer: Optional[str] = None
    created_at: str = Field(default_factory=_iso_now)


class CompanyEventCreate(BaseModel):
    title: str
    description: str
    event_date: str
    event_time: str
    location: Optional[str] = None


class Announcement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str
    created_at: str = Field(default_factory=_iso_now)
    effective_date: str
    event_id: Optional[str] = None
    event_type: Optional[str] = None


class AnnouncementCreate(BaseModel):
    title: str
    content: str
    effective_date: Optional[str] = None


class AnnouncementRead(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    announcement_id: str
    user_id: str
    read_at: Optional[str] = None
    acknowledged: bool = False


class AlertAcknowledgement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    alert_type: str
    message: str
    created_at: str = Field(default_factory=_iso_now)
    acknowledged: bool = False
    acknowledged_at: Optional[str] = None


users_cache: List[User] = []
sessions_cache: List[Session] = []
breaks_cache: List[Break] = []
calendar_events_cache: List[CalendarEvent] = []
holiday_master_cache: List[Dict[str, Any]] = []
attendance_policies_cache: List[AttendancePolicy] = []
announcements_cache: List[Announcement] = []
company_events_cache: List[CompanyEvent] = []
announcement_reads_cache: List[AnnouncementRead] = []
alert_ack_cache: List[AlertAcknowledgement] = []
_cache_refreshed_at = 0.0
_cache_lock = threading.RLock()
_CACHE_TTL_SECONDS = float(os.getenv("WORKHUB_CACHE_TTL_SECONDS", "2"))


def _refresh_cache(force: bool = False) -> None:
    global users_cache, sessions_cache, breaks_cache
    global calendar_events_cache, attendance_policies_cache
    global announcements_cache, company_events_cache
    global announcement_reads_cache, alert_ack_cache, holiday_master_cache
    global _cache_refreshed_at

    now = time.monotonic()
    if not force and now - _cache_refreshed_at < _CACHE_TTL_SECONDS:
        return
    with _cache_lock:
        now = time.monotonic()
        if not force and now - _cache_refreshed_at < _CACHE_TTL_SECONDS:
            return
        loaded_users = [User(**row) for row in _load_json(USERS_FILE)]
        loaded_sessions = [_normalize_session(Session(**row)) for row in _load_json(SESSIONS_FILE)]
        loaded_breaks = [_normalize_break(Break(**row)) for row in _load_json(BREAKS_FILE)]
        loaded_calendar_events = [
            CalendarEvent(**row) for row in _load_json(CALENDAR_EVENTS_FILE)
        ]
        loaded_holidays = _load_json(HOLIDAY_MASTER_FILE)
        loaded_policies = [
            AttendancePolicy(**row) for row in _load_json(ATTENDANCE_POLICIES_FILE)
        ]
        loaded_announcements = [
            Announcement(**row) for row in _load_json(ANNOUNCEMENTS_FILE)
        ]
        loaded_company_events = [
            CompanyEvent(**row) for row in _load_json(COMPANY_EVENTS_FILE)
        ]
        loaded_reads = [
            AnnouncementRead(**row) for row in _load_json(ANNOUNCEMENT_READS_FILE)
        ]
        loaded_alerts = [
            AlertAcknowledgement(**row) for row in _load_json(ALERT_ACK_FILE)
        ]
        users_cache = loaded_users
        sessions_cache = loaded_sessions
        breaks_cache = loaded_breaks
        calendar_events_cache = loaded_calendar_events
        holiday_master_cache = loaded_holidays
        attendance_policies_cache = loaded_policies
        announcements_cache = loaded_announcements
        company_events_cache = loaded_company_events
        announcement_reads_cache = loaded_reads
        alert_ack_cache = loaded_alerts
        if _migrate_cached_timestamps_to_ist():
            _persist_cache()
        _cache_refreshed_at = now


def _persist_cache() -> None:
    _save_json(USERS_FILE, [row.dict() for row in users_cache])
    _save_json(SESSIONS_FILE, [row.dict() for row in sessions_cache])
    _save_json(BREAKS_FILE, [row.dict() for row in breaks_cache])
    _save_json(CALENDAR_EVENTS_FILE, [row.dict() for row in calendar_events_cache])
    _save_json(HOLIDAY_MASTER_FILE, holiday_master_cache)
    _save_json(ATTENDANCE_POLICIES_FILE, [row.dict() for row in attendance_policies_cache])
    _save_json(ANNOUNCEMENTS_FILE, [row.dict() for row in announcements_cache])
    _save_json(COMPANY_EVENTS_FILE, [row.dict() for row in company_events_cache])
    _save_json(ANNOUNCEMENT_READS_FILE, [row.dict() for row in announcement_reads_cache])
    _save_json(ALERT_ACK_FILE, [row.dict() for row in alert_ack_cache])


_seed_initial_data()
_refresh_cache()


def _ensure_default_policies() -> None:
    if not attendance_policies_cache:
        attendance_policies_cache.extend(AttendancePolicy(**row) for row in DEFAULT_POLICIES)
        _upsert_models(ATTENDANCE_POLICIES_FILE, attendance_policies_cache)


def get_user_by_id(user_id: str) -> User:
    for user in users_cache:
        if user.id == user_id:
            return user
    raise HTTPException(status_code=404, detail="User not found")


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session_token: Optional[str] = Cookie(default=None, alias=AUTH_COOKIE_NAME),
) -> User:
    token = (
        credentials.credentials
        if credentials and credentials.scheme.lower() == "bearer"
        else session_token
    )
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("missing subject")
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    _refresh_cache()
    user = get_user_by_id(user_id)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is inactive")
    return user


def is_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin rights required")
    return current_user


def _policy_map() -> Dict[str, AttendancePolicy]:
    _ensure_default_policies()
    return {policy.event_type: policy for policy in attendance_policies_cache}


def _get_policy_for_event_type(event_type: str) -> AttendancePolicy:
    policies = _policy_map()
    if event_type in policies:
        return policies[event_type]
    return AttendancePolicy(
        id=f"fallback-{event_type}",
        event_type=event_type,
        min_work_hours=0,
        target_work_hours=0,
        max_break_minutes=0,
        created_at=_iso_now(),
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD") from exc


def _parse_month(value: str) -> tuple[int, int]:
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid month format, expected YYYY-MM") from exc
    return parsed.year, parsed.month


def _format_minutes(value: float | int) -> str:
    total_minutes = max(0, int(round(value)))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def _format_time_from_minutes(minutes: float, anchor: Optional[datetime] = None) -> Optional[str]:
    if minutes <= 0:
        return None
    anchor = anchor or _now()
    result = anchor + timedelta(minutes=minutes)
    return result.strftime("%I:%M %p")


def _sync_session_breaks(session: Session) -> None:
    session.breaks = [
        {
            "id": brk.id,
            "start": _serialize_datetime(brk.start),
            "end": _serialize_datetime(brk.end),
        }
        for brk in breaks_cache
        if brk.session_id == session.id
    ]


def _session_break_minutes(session: Session) -> float:
    total = 0.0
    for brk in breaks_cache:
        if brk.session_id != session.id or brk.end is None:
            continue
        total += (_ensure_ist(brk.end) - _ensure_ist(brk.start)).total_seconds() / 60
    return total


def _session_work_minutes(session: Session, reference: Optional[datetime] = None) -> float:
    reference = _ensure_ist(reference or _now())
    end = _ensure_ist(session.end) or reference
    total = (end - _ensure_ist(session.start)).total_seconds() / 60
    active_break = next(
        (brk for brk in breaks_cache if brk.session_id == session.id and brk.end is None),
        None,
    )
    active_break_minutes = 0.0
    if active_break:
        active_break_minutes = max(0.0, (reference - _ensure_ist(active_break.start)).total_seconds() / 60)
    return max(0.0, total - _session_break_minutes(session) - active_break_minutes)


def _session_view(session: Session) -> Dict[str, Any]:
    _sync_session_breaks(session)
    active_break = next(
        (brk for brk in breaks_cache if brk.session_id == session.id and brk.end is None),
        None,
    )
    start_ist = _ensure_ist(session.start)
    end_ist = _ensure_ist(session.end) if session.end else None
    return {
        **session.dict(),
        "work_minutes": round(_session_work_minutes(session), 2),
        "break_minutes": round(_session_break_minutes(session), 2),
        "active_break": _break_view(active_break) if active_break else None,
        "is_active": session.end is None,
        "start": start_ist.isoformat(),
        "end": end_ist.isoformat() if end_ist else None,
        "attendance_date": start_ist.strftime("%d %b %Y"),
        "start_time": start_ist.strftime("%I:%M %p"),
        "end_time": end_ist.strftime("%I:%M %p") if end_ist else None,
    }


def _break_view(brk: Break) -> Dict[str, Any]:
    return {
        "id": brk.id,
        "session_id": brk.session_id,
        "start": _serialize_datetime(brk.start),
        "end": _serialize_datetime(brk.end),
    }


def _user_summary(user: User) -> Dict[str, Any]:
    summary = user.dict(exclude=USER_PRIVATE_FIELDS)
    active_session = next(
        (session for session in sessions_cache if session.user_id == user.id and session.end is None),
        None,
    )
    summary["active_session"] = _session_view(active_session) if active_session else None
    return summary


def _find_session_for_user(user_id: str, target_date: date) -> Optional[Session]:
    candidates = [session for session in sessions_cache if session.user_id == user_id and _session_day(session) == target_date]
    if candidates:
        candidates.sort(key=lambda item: item.start, reverse=True)
        return candidates[0]
    active_sessions = [session for session in sessions_cache if session.user_id == user_id and session.end is None]
    if active_sessions:
        active_sessions.sort(key=lambda item: item.start, reverse=True)
        return active_sessions[0]
    return None


def _explicit_calendar_event(event_date: date) -> Optional[CalendarEvent]:
    date_key = event_date.isoformat()
    for event in calendar_events_cache:
        if event.date == date_key:
            return event
    return None


def _synthetic_calendar_event(event_date: date) -> Dict[str, Any]:
    weekday = event_date.weekday()
    if weekday == 6:
        event_type = "HOLIDAY"
        title = "Sunday"
    elif weekday == 5:
        saturday_index = ((event_date.day - 1) // 7) + 1
        if saturday_index in {2, 4}:
            event_type = "HOLIDAY"
            title = "Saturday Holiday"
        else:
            event_type = "HALF_DAY"
            title = "Saturday Half Day"
    else:
        event_type = "WORKING_DAY"
        title = "Working Day"
    event = CalendarEvent(
        id=f"synthetic-{event_date.isoformat()}",
        event_type=event_type,
        date=event_date.isoformat(),
        title=title,
        description=None,
        created_at=_iso_now(),
        updated_at=_iso_now(),
        manager_id=None,
        related_event_id=None,
    )
    return {**event.dict(), "is_synthetic": True}


def _calendar_event_for_date(event_date: date) -> Dict[str, Any]:
    master_match = next((row for row in holiday_master_cache if row.get("date") == event_date.isoformat()), None)
    if master_match:
        explicit = _explicit_calendar_event(event_date)
        if explicit:
            return {**explicit.dict(), "is_synthetic": False, "from_master": True}
        event = CalendarEvent(
            id=master_match["id"],
            event_type=master_match["event_type"],
            date=master_match["date"],
            title=master_match["title"],
            description=master_match.get("description"),
            created_at=master_match.get("updated_at", _iso_now()),
            updated_at=master_match.get("updated_at", _iso_now()),
            manager_id=None,
            related_event_id=None,
        )
        return {**event.dict(), "is_synthetic": False, "from_master": True}
    explicit = _explicit_calendar_event(event_date)
    if explicit:
        return {**explicit.dict(), "is_synthetic": False}
    return _synthetic_calendar_event(event_date)


def _calendar_event_to_summary(event: Dict[str, Any]) -> Dict[str, Any]:
    policy = _get_policy_for_event_type(event["event_type"])
    return {
        **event,
        "policy": policy.dict(),
    }


def _generate_announcement(event: Dict[str, Any]) -> Announcement:
    event_type = event["event_type"]
    title = "Calendar Update"
    if event_type == "HOLIDAY":
        content = f"{event['title']} on {event['date']} marked as a holiday. Attendance not required."
    elif event_type == "COMP_OFF":
        content = f"Compensatory holiday declared for {event['date']}."
    elif event_type == "LONG_WEEKEND":
        content = f"Long weekend declared starting {event['date']}."
    elif event_type == "FULL_DAY_SATURDAY":
        content = f"{event['date']} marked as a full working Saturday."
    elif event_type == "HALF_DAY":
        content = f"{event['date']} marked as a half day."
    else:
        content = f"{event['title']} scheduled for {event['date']}."
    return Announcement(
        title=title,
        content=content,
        effective_date=event["date"],
        event_id=event["id"],
        event_type=event_type,
    )


def _read_status_for_user(announcement_id: str, user_id: str) -> bool:
    return any(
        row.announcement_id == announcement_id and row.user_id == user_id and row.acknowledged
        for row in announcement_reads_cache
    )


def _month_calendar(month: str) -> List[Dict[str, Any]]:
    year, month_num = _parse_month(month)
    days_in_month = calendar.monthrange(year, month_num)[1]
    rows: List[Dict[str, Any]] = []
    for day in range(1, days_in_month + 1):
        event_date = date(year, month_num, day)
        event = _calendar_event_for_date(event_date)
        policy = _get_policy_for_event_type(event["event_type"])
        rows.append(
            {
                **event,
                "policy": policy.dict(),
            }
        )
    return rows


def _derive_long_weekends(month_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    long_weekends: List[Dict[str, Any]] = []
    run_start: Optional[str] = None
    run_end: Optional[str] = None

    def _flush() -> None:
        nonlocal run_start, run_end
        if run_start and run_end:
            start_date = date.fromisoformat(run_start)
            end_date = date.fromisoformat(run_end)
            if (end_date - start_date).days >= 2:
                long_weekends.append(
                    {
                        "start_date": run_start,
                        "end_date": run_end,
                        "label": f"{start_date.strftime('%d-%b')} to {end_date.strftime('%d-%b')}",
                        "days": (end_date - start_date).days + 1,
                    }
                )
        run_start = None
        run_end = None

    for event in month_events:
        is_off = event["event_type"] in {"HOLIDAY", "COMP_OFF", "LONG_WEEKEND"} or event.get("is_synthetic") and event["event_type"] == "HOLIDAY"
        if is_off:
            run_start = run_start or event["date"]
            run_end = event["date"]
        else:
            _flush()
    _flush()
    return long_weekends


def _count_workdays(month_events: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for event in month_events
        if event["event_type"] in {"WORKING_DAY", "HALF_DAY", "FULL_DAY_SATURDAY"}
    )


def _current_month_label(today: Optional[date] = None) -> str:
    today = today or _ist_today()
    return today.strftime("%Y-%m")


def _event_requires_attendance(event_type: str) -> bool:
    return event_type in {"WORKING_DAY", "HALF_DAY", "FULL_DAY_SATURDAY"}


def _attendance_summary_for_date(user: User, target_date: date) -> Dict[str, Any]:
    event = _calendar_event_for_date(target_date)
    policy = _get_policy_for_event_type(event["event_type"])
    session = _find_session_for_user(user.id, target_date)
    work_minutes = _session_work_minutes(session) if session else 0.0
    break_minutes = _session_break_minutes(session) if session else 0.0
    remaining_minutes = max(0.0, policy.target_work_hours * 60 - work_minutes)
    break_remaining = max(0.0, policy.max_break_minutes - break_minutes)
    estimated_completion = None
    if session and session.end is None and remaining_minutes > 0:
        estimated_completion = _format_time_from_minutes(remaining_minutes)

    alerts: List[str] = []
    if _event_requires_attendance(event["event_type"]):
        if not session:
            alerts.append("No active session started for a working day.")
        elif session.end is None and work_minutes < policy.min_work_hours * 60:
            alerts.append("Below minimum work threshold.")
        if break_minutes > policy.max_break_minutes > 0:
            alerts.append("Break limit exceeded.")
    if event["event_type"] in {"HOLIDAY", "COMP_OFF", "LONG_WEEKEND"}:
        alerts = []
    if session and session.end is None:
        active_break = next(
            (brk for brk in breaks_cache if brk.session_id == session.id and brk.end is None),
            None,
        )
        if active_break:
            alerts.append("Break in progress.")

    return {
        "date": target_date.isoformat(),
        "calendar_event": event,
        "policy": policy.dict(),
        "session": _session_view(session) if session else None,
        "work_done_minutes": round(work_minutes, 2),
        "remaining_minutes": round(remaining_minutes, 2),
        "breaks_used_minutes": round(break_minutes, 2),
        "break_remaining_minutes": round(break_remaining, 2),
        "estimated_completion": estimated_completion,
        "alerts": alerts,
    }


def _dashboard_overview(user: User, month: str, announcement_limit: Optional[int] = None) -> Dict[str, Any]:
    today = _ist_today()
    month_events = _month_calendar(month)
    long_weekends = _derive_long_weekends(month_events)
    attendance_today = _attendance_summary_for_date(user, today)

    sessions_for_month = [
        session for session in sessions_cache if session.user_id == user.id and _session_day(session).strftime("%Y-%m") == month
    ]
    month_sessions_by_day: Dict[str, float] = defaultdict(float)
    for session in sessions_for_month:
        day_key = _session_day(session).isoformat()
        month_sessions_by_day[day_key] = max(
            month_sessions_by_day[day_key],
            _session_work_minutes(session),
        )

    working_days = [
        event for event in month_events if event["event_type"] in {"WORKING_DAY", "FULL_DAY_SATURDAY"}
    ]
    half_days = [event for event in month_events if event["event_type"] == "HALF_DAY"]
    holidays = [event for event in month_events if event["event_type"] == "HOLIDAY"]
    company_holidays = [event for event in holidays if not event.get("is_synthetic")]
    comp_offs = [event for event in month_events if event["event_type"] == "COMP_OFF"]
    weekends = [event for event in month_events if date.fromisoformat(event["date"]).weekday() == 6]

    completed = 0
    for event in working_days + half_days:
        policy = _get_policy_for_event_type(event["event_type"])
        if month_sessions_by_day.get(event["date"], 0) >= policy.target_work_hours * 60:
            completed += 1

    attendance_days = working_days + half_days
    elapsed_working_days = sum(
        1 for event in attendance_days if date.fromisoformat(event["date"]) <= today
    )
    remaining_working_days = sum(
        1 for event in attendance_days if date.fromisoformat(event["date"]) > today
    )

    upcoming_events = [_calendar_event_for_date(today + timedelta(days=offset)) for offset in range(1, 90)]
    next_holiday = next((event for event in upcoming_events if event["event_type"] == "HOLIDAY"), None)
    next_half_day = next((event for event in upcoming_events if event["event_type"] == "HALF_DAY"), None)
    next_company_holiday = next(
        (
            event
            for event in sorted(
                (event for event in calendar_events_cache if event.event_type == "HOLIDAY"),
                key=lambda item: item.date,
            )
            if event.date > today.isoformat()
        ),
        None,
    )
    next_company_event = next(
        (
            event
            for event in sorted(
                company_events_cache,
                key=lambda item: item.event_date,
            )
            if event.event_date > today.isoformat()
        ),
        None,
    )
    upcoming_holidays = [
        {
            "date": event["date"],
            "title": event["title"],
            "event_type": event["event_type"],
            "days_until": (date.fromisoformat(event["date"]) - today).days,
        }
        for event in upcoming_events
        if event["event_type"] in {"HOLIDAY", "COMP_OFF", "LONG_WEEKEND", "HALF_DAY"}
    ][:6]

    unread_count = sum(
        1 for announcement in announcements_cache if not _read_status_for_user(announcement.id, user.id)
    )

    sorted_announcements = sorted(announcements_cache, key=lambda row: row.created_at, reverse=True)
    if announcement_limit is not None:
        sorted_announcements = sorted_announcements[:announcement_limit]

    return {
        "user": user.dict(),
        "today": attendance_today,
        "month": month,
        "month_summary": {
            "total_days": len(month_events),
            "working_days": len(working_days) + len(half_days),
            "completed": completed,
            "remaining": max(0, len(working_days) + len(half_days) - completed),
            "elapsed_working_days": elapsed_working_days,
            "remaining_working_days": remaining_working_days,
            "days_left_in_month": max(0, calendar.monthrange(today.year, today.month)[1] - today.day),
            "holidays": len(holidays),
            "company_holidays": len(company_holidays),
            "comp_offs": len(comp_offs),
            "half_days": len(half_days),
            "weekends": len(weekends),
            "long_weekends": len(long_weekends),
        },
        "calendar_month": month_events,
        "long_weekends": long_weekends,
        "upcoming_events": {
            "next_holiday": next_holiday,
            "next_half_day": next_half_day,
            "next_company_holiday": next_company_holiday.dict() if next_company_holiday else None,
            "next_company_event": next_company_event.dict() if next_company_event else None,
        },
        "upcoming_holidays": upcoming_holidays,
        "announcements": [
            {**announcement.dict(), "is_read": _read_status_for_user(announcement.id, user.id)}
            for announcement in sorted_announcements
        ],
        "alerts": attendance_today["alerts"],
        "unread_announcements": unread_count,
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    try:
        persistence = storage_health()
        return {"status": "ok", "environment": WORKHUB_ENV, "storage": persistence}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Storage unavailable: {exc}") from exc


@app.get("/")
def root() -> Any:
    if WEB_INDEX_FILE.is_file():
        return FileResponse(
            WEB_INDEX_FILE,
            headers={"Cache-Control": "no-cache"},
        )
    return {
        "name": "WorkHub API",
        "status": "running",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/med360-logo.png", include_in_schema=False)
def med360_logo() -> Any:
    logo_path = WEB_DIST_DIR / "med360-logo.png"
    if not logo_path.is_file():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(
        logo_path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/med360-launcher.svg", include_in_schema=False)
def med360_launcher() -> Any:
    icon_path = WEB_DIST_DIR / "med360-launcher.svg"
    if not icon_path.is_file():
        raise HTTPException(status_code=404, detail="Launcher icon not found")
    return FileResponse(
        icon_path,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response) -> Dict[str, Any]:
    _refresh_cache()
    lookup_email = _normalize_company_email(payload.email) if payload.email else None
    lookup_username = payload.username.lower() if payload.username else None
    user = next(
        (
            candidate
            for candidate in users_cache
            if _verify_password(payload.password, candidate.password)
            and (
                (lookup_email and candidate.email.lower() == lookup_email)
                or (lookup_username and candidate.username.lower() == lookup_username)
            )
        ),
        None,
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is inactive")
    if not user.password.startswith("pbkdf2_sha256$"):
        user.password = _hash_password(payload.password)
        _upsert_models(USERS_FILE, [user])
    access_token = _create_access_token(user)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        access_token,
        max_age=JWT_EXPIRE_HOURS * 3600,
        httponly=True,
        secure=WORKHUB_ENV == "production",
        samesite="lax",
        path="/",
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user.dict(exclude=USER_PRIVATE_FIELDS),
    }


@app.post("/register", response_model=AuthResponse)
def register(payload: RegistrationRequest, response: Response) -> Dict[str, Any]:
    _refresh_cache()
    username = payload.username.strip()
    email = _normalize_company_email(payload.email)
    if not username or not email or not payload.password:
        raise HTTPException(status_code=400, detail="Name, email, and password are required")
    if any(candidate.email.lower() == email for candidate in users_cache):
        raise HTTPException(status_code=400, detail="Email already registered")
    if payload.role == "Admin":
        if not hmac.compare_digest(payload.bootstrap_secret or "", BOOTSTRAP_SECRET):
            raise HTTPException(status_code=403, detail="Invalid Admin bootstrap key")
    elif not ALLOW_SELF_REGISTRATION:
        raise HTTPException(status_code=403, detail="Self-registration is disabled; contact an administrator")
    company_policy = _company_work_policy()
    user = User(
        username=username,
        email=email,
        password=_hash_password(payload.password),
        role=payload.role,
        is_active=True,
        office_hours=company_policy["office_hours"].copy(),
        rules=company_policy["rules"].copy(),
    )
    users_cache.append(user)
    _upsert_models(USERS_FILE, [user])
    access_token = _create_access_token(user)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        access_token,
        max_age=JWT_EXPIRE_HOURS * 3600,
        httponly=True,
        secure=WORKHUB_ENV == "production",
        samesite="lax",
        path="/",
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user.dict(exclude=USER_PRIVATE_FIELDS),
    }


@app.post("/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest) -> Dict[str, Any]:
    _refresh_cache()
    try:
        email = _normalize_company_email(payload.email)
    except HTTPException:
        return {"message": "If the account exists, a reset code has been sent."}

    user = next((candidate for candidate in users_cache if candidate.email.lower() == email), None)
    response: Dict[str, Any] = {"message": "If the account exists, a reset code has been sent."}
    if not user or not user.is_active:
        return response

    token = f"{secrets.randbelow(1_000_000):06d}"
    user.password_reset_hash = _hash_reset_token(token)
    user.password_reset_expires_at = (_now() + timedelta(minutes=PASSWORD_RESET_MINUTES)).isoformat()
    _upsert_models(USERS_FILE, [user])

    delivered = False
    try:
        delivered = _send_password_reset_email(user.email, token)
    except Exception:
        delivered = False

    response["delivery"] = "email" if delivered else "manual"
    if WORKHUB_ENV != "production" or os.getenv("WORKHUB_PASSWORD_RESET_EXPOSE_TOKEN", "").lower() == "true":
        response["reset_token"] = token
    return response


@app.post("/auth/reset-password")
def reset_password(payload: ResetPasswordRequest) -> Dict[str, str]:
    _refresh_cache()
    email = _normalize_company_email(payload.email)
    token = payload.token.strip()
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    user = next((candidate for candidate in users_cache if candidate.email.lower() == email), None)
    if not user or not user.password_reset_hash or not user.password_reset_expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    expires_at = datetime.fromisoformat(user.password_reset_expires_at)
    if _ensure_ist(expires_at) < _now():
        user.password_reset_hash = None
        user.password_reset_expires_at = None
        _upsert_models(USERS_FILE, [user])
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    if not hmac.compare_digest(user.password_reset_hash, _hash_reset_token(token)):
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

    user.password = _hash_password(payload.new_password)
    user.password_reset_hash = None
    user.password_reset_expires_at = None
    _upsert_models(USERS_FILE, [user])
    return {"message": "Password updated. Sign in with your new password."}


@app.get("/me", response_model=UserPublic)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@app.post("/logout")
def logout(response: Response) -> Dict[str, str]:
    response.delete_cookie(
        AUTH_COOKIE_NAME,
        httponly=True,
        secure=WORKHUB_ENV == "production",
        samesite="lax",
        path="/",
    )
    return {"message": "Signed out"}


@app.post("/office_hours/{user_id}")
def set_office_hours(
    user_id: str,
    payload: OfficeHoursUpdate,
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin rights required")
    user = get_user_by_id(user_id)
    user.office_hours = {"start": payload.start, "end": payload.end}
    _upsert_models(USERS_FILE, [user])
    return {"message": f"Office hours set for {user.username}"}


@app.post("/rules/{user_id}")
def set_rules(
    user_id: str,
    payload: RulesUpdate,
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin rights required")
    user = get_user_by_id(user_id)
    current_rules = user.rules or {}
    current_rules.update({key: value for key, value in payload.dict().items() if value is not None})
    user.rules = current_rules
    _upsert_models(USERS_FILE, [user])
    return {"message": f"Rules set for {user.username}"}


def _company_work_policy() -> Dict[str, Any]:
    rows = _load_json(COMPANY_WORK_POLICY_FILE)
    policy = rows[0] if rows else DEFAULT_COMPANY_WORK_POLICY
    return {
        "office_hours": dict(policy.get("office_hours") or DEFAULT_COMPANY_WORK_POLICY["office_hours"]),
        "rules": dict(policy.get("rules") or DEFAULT_COMPANY_WORK_POLICY["rules"]),
    }


@app.get("/company/work-policy")
def get_company_work_policy(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return _company_work_policy()


@app.post("/company/work-policy")
def set_company_work_policy(
    payload: CompanyWorkPolicyUpdate,
    current_user: User = Depends(is_admin),
) -> Dict[str, Any]:
    policy = {
        "office_hours": payload.office_hours.dict(),
        "rules": {key: value for key, value in payload.rules.dict().items() if value is not None},
    }
    required_rules = {"min_work_hours", "max_work_hours", "min_break_minutes", "max_break_minutes"}
    if set(policy["rules"]) != required_rules:
        raise HTTPException(status_code=400, detail="All work and break limits are required")
    if policy["office_hours"]["start"] >= policy["office_hours"]["end"]:
        raise HTTPException(status_code=400, detail="Office end must be after office start")
    if policy["rules"]["min_work_hours"] > policy["rules"]["max_work_hours"]:
        raise HTTPException(status_code=400, detail="Minimum work time cannot exceed maximum work time")
    if policy["rules"]["min_break_minutes"] > policy["rules"]["max_break_minutes"]:
        raise HTTPException(status_code=400, detail="Minimum break time cannot exceed maximum break time")

    _save_json(COMPANY_WORK_POLICY_FILE, [policy])
    for user in users_cache:
        user.office_hours = policy["office_hours"].copy()
        user.rules = policy["rules"].copy()
    _upsert_models(USERS_FILE, users_cache)
    return policy


@app.get("/sessions")
def list_sessions(
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    target_user_id = user_id if current_user.role == "Admin" and user_id else current_user.id
    sessions = [session for session in sessions_cache if session.user_id == target_user_id]
    sessions.sort(key=lambda item: item.start, reverse=True)
    return [_session_view(session) for session in sessions]


@app.post("/sessions/{user_id}/start", response_model=Session)
def start_session(user_id: str, current_user: User = Depends(get_current_user)) -> Session:
    if current_user.id != user_id and current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="No permission to start session for other users")
    if any(session.user_id == user_id and session.end is None for session in sessions_cache):
        raise HTTPException(status_code=400, detail="An active session already exists")
    session = Session(user_id=user_id, start=_now())
    sessions_cache.append(session)
    _upsert_models(SESSIONS_FILE, [session])
    return session


@app.post("/sessions/{session_id}/stop", response_model=Session)
def stop_session(session_id: str, current_user: User = Depends(get_current_user)) -> Session:
    session = next((candidate for candidate in sessions_cache if candidate.id == session_id), None)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id and current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="No permission to stop this session")
    if session.end is not None:
        raise HTTPException(status_code=400, detail="Session already stopped")
    active_break = next((brk for brk in breaks_cache if brk.session_id == session.id and brk.end is None), None)
    if active_break:
        active_break.end = _now()
    session.end = _now()
    _sync_session_breaks(session)
    _upsert_models(SESSIONS_FILE, [session])
    if active_break:
        _upsert_models(BREAKS_FILE, [active_break])
    return session


@app.post("/sessions/{session_id}/break/start", response_model=Break)
def start_break(session_id: str, current_user: User = Depends(get_current_user)) -> Break:
    session = next((candidate for candidate in sessions_cache if candidate.id == session_id), None)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id and current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="No permission to modify this session")
    if session.end is not None:
        raise HTTPException(status_code=400, detail="Session already stopped")
    if any(brk.session_id == session_id and brk.end is None for brk in breaks_cache):
        raise HTTPException(status_code=400, detail="Previous break not ended")
    brk = Break(session_id=session_id, start=_now())
    breaks_cache.append(brk)
    _sync_session_breaks(session)
    _upsert_models(BREAKS_FILE, [brk])
    _upsert_models(SESSIONS_FILE, [session])
    return brk


@app.post("/sessions/{session_id}/break/stop", response_model=Break)
def stop_break(session_id: str, current_user: User = Depends(get_current_user)) -> Break:
    session = next((candidate for candidate in sessions_cache if candidate.id == session_id), None)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id and current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="No permission to modify this session")
    brk = next((candidate for candidate in breaks_cache if candidate.session_id == session_id and candidate.end is None), None)
    if not brk:
        raise HTTPException(status_code=400, detail="No active break found")
    brk.end = _now()
    _sync_session_breaks(session)
    _upsert_models(BREAKS_FILE, [brk])
    _upsert_models(SESSIONS_FILE, [session])
    return brk


@app.get("/sessions/{session_id}/breaks")
def list_session_breaks(session_id: str, current_user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    session = next((candidate for candidate in sessions_cache if candidate.id == session_id), None)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id and current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="No permission to view this session")
    _sync_session_breaks(session)
    return [_break_view(brk) for brk in breaks_cache if brk.session_id == session_id]


@app.get("/calendar/policy/{event_type}")
def get_policy(
    event_type: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    return _get_policy_for_event_type(event_type).dict()


@app.get("/calendar/events/{event_date}")
def get_calendar_event(
    event_date: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    return _calendar_event_to_summary(_calendar_event_for_date(_parse_date(event_date)))


@app.get("/calendar/today")
def get_calendar_today(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return _calendar_event_to_summary(_calendar_event_for_date(_ist_today()))


@app.get("/calendar/events")
def list_calendar_events(
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    return [_calendar_event_to_summary(event) for event in _month_calendar(month)]


@app.post("/calendar/events")
def create_or_update_calendar_event(
    payload: CalendarEventCreate,
    current_user: User = Depends(is_admin),
) -> Dict[str, Any]:
    event_date = _parse_date(payload.date)
    existing = next((event for event in calendar_events_cache if event.date == payload.date), None)
    if existing:
        existing.event_type = payload.event_type
        existing.title = payload.title
        existing.description = payload.description
        existing.updated_at = _iso_now()
        existing.manager_id = current_user.id
        existing.related_event_id = payload.related_event_id
        event = existing
    else:
        event = CalendarEvent(
            event_type=payload.event_type,
            date=event_date.isoformat(),
            title=payload.title,
            description=payload.description,
            manager_id=current_user.id,
            related_event_id=payload.related_event_id,
        )
        calendar_events_cache.append(event)

    holiday_master_entry = next((row for row in holiday_master_cache if row.get("date") == event.date), None)
    if event.event_type == "HOLIDAY":
        master_row = {
            "id": event.id,
            "date": event.date,
            "title": event.title,
            "description": event.description,
            "event_type": event.event_type,
            "source": "manual_override" if current_user.id else "company_circular_2026",
            "updated_at": _iso_now(),
        }
        if holiday_master_entry:
            holiday_master_entry.update(master_row)
        else:
            holiday_master_cache.append(master_row)
    elif holiday_master_entry:
        holiday_master_cache.remove(holiday_master_entry)
        if holiday_master_entry.get("id"):
            delete_row(HOLIDAY_MASTER_FILE, holiday_master_entry["id"])

    announcement = _generate_announcement(event.dict())
    announcements_cache.append(announcement)
    _upsert_models(CALENDAR_EVENTS_FILE, [event])
    if event.event_type == "HOLIDAY":
        master_row = next((row for row in holiday_master_cache if row.get("date") == event.date), None)
        if master_row:
            _upsert_models(HOLIDAY_MASTER_FILE, [master_row])
    _upsert_models(ANNOUNCEMENTS_FILE, [announcement])
    return {
        "calendar_event": _calendar_event_to_summary(event.dict()),
        "announcement": announcement.dict(),
    }


@app.get("/company-events")
def list_company_events(current_user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    return [event.dict() for event in sorted(company_events_cache, key=lambda item: item.event_date)]


@app.post("/company-events")
def create_company_event(
    payload: CompanyEventCreate,
    current_user: User = Depends(is_admin),
) -> Dict[str, Any]:
    event = CompanyEvent(
        title=payload.title,
        description=payload.description,
        event_date=payload.event_date,
        event_time=payload.event_time,
        location=payload.location,
        organizer=current_user.id,
    )
    company_events_cache.append(event)
    _upsert_models(COMPANY_EVENTS_FILE, [event])
    return event.dict()


@app.get("/announcements")
def list_announcements(current_user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    return [
        {**announcement.dict(), "is_read": _read_status_for_user(announcement.id, current_user.id)}
        for announcement in sorted(announcements_cache, key=lambda item: item.created_at, reverse=True)
    ]


@app.post("/announcements")
def create_announcement(
    payload: AnnouncementCreate,
    current_user: User = Depends(is_admin),
) -> Dict[str, Any]:
    announcement = Announcement(
        title=payload.title.strip(),
        content=payload.content.strip(),
        effective_date=payload.effective_date or _ist_today().isoformat(),
    )
    announcements_cache.append(announcement)
    _upsert_models(ANNOUNCEMENTS_FILE, [announcement])
    return announcement.dict()


@app.post("/announcements/{announcement_id}/read")
def mark_announcement_read(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    announcement = next((row for row in announcements_cache if row.id == announcement_id), None)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    read_row = next(
        (
            row
            for row in announcement_reads_cache
            if row.announcement_id == announcement_id and row.user_id == current_user.id
        ),
        None,
    )
    if not read_row:
        read_row = AnnouncementRead(announcement_id=announcement_id, user_id=current_user.id, read_at=_iso_now(), acknowledged=True)
        announcement_reads_cache.append(read_row)
    else:
        read_row.read_at = _iso_now()
        read_row.acknowledged = True
    _upsert_models(ANNOUNCEMENT_READS_FILE, [read_row])
    return {"message": "Announcement marked read"}


@app.get("/attendance/{target_date}")
def get_attendance_for_date(
    target_date: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    return _attendance_summary_for_date(current_user, _parse_date(target_date))


@app.get("/attendance/today")
def get_attendance_today(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return _attendance_summary_for_date(current_user, _ist_today())


@app.get("/dashboard/overview")
def get_dashboard_overview(
    month: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    return _dashboard_overview(current_user, month or _current_month_label())


@app.get("/admin/dashboard")
def admin_dashboard(current_user: User = Depends(is_admin)) -> Dict[str, Any]:
    dashboard: Dict[str, Dict[str, float]] = {}
    for user in users_cache:
        user_sessions = [session for session in sessions_cache if session.user_id == user.id]
        total_work = 0.0
        total_break = 0.0
        for session in user_sessions:
            total_work += _session_work_minutes(session)
            total_break += _session_break_minutes(session)
        dashboard[user.username] = {
            "work_hours": round(total_work / 60, 2),
            "break_minutes": round(total_break, 2),
        }
    return dashboard


def _admin_analytics(selected_month: str) -> Dict[str, Any]:
    month_events = _month_calendar(selected_month)
    attendance_events = {
        event["date"]: event
        for event in month_events
        if _event_requires_attendance(event["event_type"])
    }
    employee_rows: List[Dict[str, Any]] = []

    for user in users_cache:
        user_sessions = [
            session
            for session in sessions_cache
            if session.user_id == user.id and _session_day(session).strftime("%Y-%m") == selected_month
        ]
        work_by_day: Dict[str, float] = defaultdict(float)
        break_by_day: Dict[str, float] = defaultdict(float)
        for session in user_sessions:
            day_key = _session_day(session).isoformat()
            work_by_day[day_key] += _session_work_minutes(session)
            break_by_day[day_key] += _session_break_minutes(session)

        days_worked = len([day for day, minutes in work_by_day.items() if minutes > 0])
        total_work = sum(work_by_day.values())
        total_break = sum(break_by_day.values())
        completed_days = 0
        for day_key, event in attendance_events.items():
            policy = _get_policy_for_event_type(event["event_type"])
            if work_by_day.get(day_key, 0) >= policy.target_work_hours * 60:
                completed_days += 1

        employee_rows.append(
            {
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "days_worked": days_worked,
                "completed_days": completed_days,
                "total_work_minutes": round(total_work, 2),
                "average_work_minutes": round(total_work / days_worked, 2) if days_worked else 0,
                "total_break_minutes": round(total_break, 2),
                "average_break_minutes": round(total_break / days_worked, 2) if days_worked else 0,
                "completion_rate": round(completed_days / days_worked * 100, 1) if days_worked else 0,
            }
        )

    active_employees = [row for row in employee_rows if row["days_worked"] > 0]
    return {
        "month": selected_month,
        "working_days": len(attendance_events),
        "employees": employee_rows,
        "summary": {
            "employees": len(employee_rows),
            "active_employees": len(active_employees),
            "average_work_minutes": round(
                sum(row["average_work_minutes"] for row in active_employees) / len(active_employees), 2
            ) if active_employees else 0,
            "average_break_minutes": round(
                sum(row["average_break_minutes"] for row in active_employees) / len(active_employees), 2
            ) if active_employees else 0,
            "total_work_minutes": round(sum(row["total_work_minutes"] for row in employee_rows), 2),
        },
    }


@app.get("/admin/analytics")
def admin_analytics(
    month: Optional[str] = None,
    current_user: User = Depends(is_admin),
) -> Dict[str, Any]:
    return _admin_analytics(month or _current_month_label())


@app.get("/web/bootstrap")
def web_bootstrap(
    month: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return only the browser workspace data needed for first paint.

    Heavier tab data is loaded through focused web endpoints so dashboard
    startup does not pay for reports, employee lists, or full history tables.
    """
    selected_month = month or _current_month_label()
    return {
        "generated_at": _iso_now(),
        "user": current_user.dict(exclude=USER_PRIVATE_FIELDS),
        "overview": _dashboard_overview(current_user, selected_month, announcement_limit=5),
        "sessions": [],
        "announcements": [],
        "employees": [],
        "analytics": None,
        "policy": None,
    }


@app.get("/web/attendance")
def web_attendance(
    month: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    selected_month = month or _current_month_label()
    sessions = [
        session
        for session in sessions_cache
        if session.user_id == current_user.id and _session_day(session).strftime("%Y-%m") == selected_month
    ]
    sessions.sort(key=lambda item: item.start, reverse=True)
    return {
        "month": selected_month,
        "sessions": [_session_view(session) for session in sessions],
    }


@app.get("/web/announcements")
def web_announcements(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    sorted_announcements = sorted(
        announcements_cache,
        key=lambda item: item.created_at,
        reverse=True,
    )[:limit]
    return {
        "announcements": [
            {
                **announcement.dict(),
                "is_read": _read_status_for_user(announcement.id, current_user.id),
            }
            for announcement in sorted_announcements
        ],
        "unread_announcements": sum(
            1 for announcement in announcements_cache if not _read_status_for_user(announcement.id, current_user.id)
        ),
    }


@app.get("/admin/users")
def admin_users(current_user: User = Depends(is_admin)) -> List[Dict[str, Any]]:
    return [_user_summary(user) for user in users_cache]


@app.post("/admin/users")
def admin_create_user(
    payload: AdminUserCreate,
    current_user: User = Depends(is_admin),
) -> Dict[str, Any]:
    username = payload.username.strip()
    email = _normalize_company_email(payload.email)
    if not username or not email or not payload.password:
        raise HTTPException(status_code=400, detail="Name, email, and password are required")
    if any(user.email.lower() == email for user in users_cache):
        raise HTTPException(status_code=400, detail="Email already registered")
    company_policy = _company_work_policy()
    user = User(
        username=username,
        email=email,
        password=_hash_password(payload.password),
        role=payload.role,
        is_active=True,
        office_hours=company_policy["office_hours"].copy(),
        rules=company_policy["rules"].copy(),
    )
    users_cache.append(user)
    _upsert_models(USERS_FILE, [user])
    return _user_summary(user)


@app.patch("/admin/users/{user_id}")
def admin_update_user(
    user_id: str,
    payload: AdminUserUpdate,
    current_user: User = Depends(is_admin),
) -> Dict[str, Any]:
    user = get_user_by_id(user_id)
    updates = payload.dict(exclude_unset=True)
    if "email" in updates:
        email = _normalize_company_email(updates["email"])
        if any(candidate.id != user.id and candidate.email.lower() == email for candidate in users_cache):
            raise HTTPException(status_code=400, detail="Email already registered")
        updates["email"] = email
    if "username" in updates:
        updates["username"] = updates["username"].strip()
        if not updates["username"]:
            raise HTTPException(status_code=400, detail="Name is required")
    if updates.get("password") == "":
        updates.pop("password")
    elif "password" in updates:
        updates["password"] = _hash_password(updates["password"])
    if user.id == current_user.id and updates.get("is_active") is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if user.id == current_user.id and updates.get("role") == "User":
        raise HTTPException(status_code=400, detail="You cannot remove your own admin role")

    for key, value in updates.items():
        setattr(user, key, value)
    changed_sessions: List[Session] = []
    changed_breaks: List[Break] = []
    if user.is_active is False:
        for session in sessions_cache:
            if session.user_id == user.id and session.end is None:
                session.end = _now()
                changed_sessions.append(session)
                for brk in breaks_cache:
                    if brk.session_id == session.id and brk.end is None:
                        brk.end = _now()
                        changed_breaks.append(brk)
    _upsert_models(USERS_FILE, [user])
    if changed_sessions:
        _upsert_models(SESSIONS_FILE, changed_sessions)
    if changed_breaks:
        _upsert_models(BREAKS_FILE, changed_breaks)
    return _user_summary(user)


@app.get("/{browser_path:path}", include_in_schema=False)
def serve_react_application(browser_path: str) -> Any:
    """Serve the React SPA without changing any existing API routes."""
    if WEB_INDEX_FILE.is_file():
        return FileResponse(
            WEB_INDEX_FILE,
            headers={"Cache-Control": "no-cache"},
        )
    if not browser_path:
        return {
            "name": "WorkHub API",
            "status": "running",
            "health": "/health",
            "docs": "/docs",
            "web": "Run `cd web_app && npm run build` to enable the React interface.",
        }
    raise HTTPException(status_code=404, detail="Not found")
