from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("MONGO_DB", "workhub")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app  # noqa: E402


def to_ist_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=app.INDIA_TZ)
    return parsed.astimezone(app.INDIA_TZ)


def main() -> None:
    changed_breaks = []
    changed_sessions = []

    for brk in app.breaks_cache:
        old = (brk.start, brk.end)
        brk.start = to_ist_datetime(brk.start)  # type: ignore[assignment]
        brk.end = to_ist_datetime(brk.end) if brk.end else None  # type: ignore[assignment]
        if old != (brk.start, brk.end):
            changed_breaks.append(brk)

    for session in app.sessions_cache:
        old_start = session.start
        old_end = session.end
        old_breaks = list(session.breaks or [])
        session.start = to_ist_datetime(session.start)  # type: ignore[assignment]
        session.end = to_ist_datetime(session.end) if session.end else None  # type: ignore[assignment]
        app._sync_session_breaks(session)
        if old_start != session.start or old_end != session.end or old_breaks != (session.breaks or []):
            changed_sessions.append(session)

    if changed_breaks:
        app._upsert_models(app.BREAKS_FILE, changed_breaks)
    if changed_sessions:
        app._upsert_models(app.SESSIONS_FILE, changed_sessions)

    print("database", app.storage_health()["database"])
    print("changed_sessions", len(changed_sessions))
    print("changed_breaks", len(changed_breaks))
    print("attendance_history")
    for session in sorted(app.sessions_cache, key=lambda row: row.start, reverse=True):
        view = app._session_view(session)
        print(
            {
                key: view.get(key)
                for key in (
                    "id",
                    "user_id",
                    "attendance_date",
                    "start_time",
                    "end_time",
                    "start",
                    "end",
                    "work_minutes",
                    "break_minutes",
                    "is_active",
                )
            }
        )


if __name__ == "__main__":
    main()
