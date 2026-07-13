from __future__ import annotations

import os
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from dotenv import load_dotenv


load_dotenv()

COLLECTIONS = [
    "users",
    "sessions",
    "breaks",
    "calendar_events",
    "holiday_master",
    "attendance_policies",
    "company_work_policy",
    "announcements",
    "company_events",
    "announcement_reads",
    "alert_acknowledgements",
]

DEFAULT_POLICIES: list[dict[str, Any]] = [
    {"id": "p001", "event_type": "WORKING_DAY", "min_work_hours": 6, "target_work_hours": 6.5, "max_break_minutes": 90},
    {"id": "p002", "event_type": "HALF_DAY", "min_work_hours": 3.5, "target_work_hours": 4, "max_break_minutes": 30},
    {"id": "p003", "event_type": "FULL_DAY_SATURDAY", "min_work_hours": 6, "target_work_hours": 6.5, "max_break_minutes": 90},
    {"id": "p004", "event_type": "HOLIDAY", "min_work_hours": 0, "target_work_hours": 0, "max_break_minutes": 0},
    {"id": "p005", "event_type": "COMP_OFF", "min_work_hours": 0, "target_work_hours": 0, "max_break_minutes": 0},
    {"id": "p006", "event_type": "LONG_WEEKEND", "min_work_hours": 0, "target_work_hours": 0, "max_break_minutes": 0},
    {"id": "p007", "event_type": "COMPANY_EVENT", "min_work_hours": 0, "target_work_hours": 0, "max_break_minutes": 0},
]

DEFAULT_COMPANY_POLICY = {
    "_singleton": "company_work_policy",
    "office_hours": {"start": "09:00", "end": "18:00"},
    "rules": {
        "min_work_hours": 6.0,
        "max_work_hours": 9.0,
        "min_break_minutes": 30.0,
        "max_break_minutes": 90.0,
    },
}


def main() -> None:
    postgres_url = (
        os.getenv("POSTGRES_URL") or os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("DATABASE_URL") or ""
    ).strip()
    if not postgres_url:
        raise SystemExit("POSTGRES_URL is missing from .env")

    conn = psycopg.connect(postgres_url, autocommit=True)
    with conn.cursor() as cur:
        for name in COLLECTIONS:
            cur.execute(
                f'CREATE TABLE IF NOT EXISTS "{name}" '
                f'(id TEXT PRIMARY KEY, _singleton TEXT UNIQUE, data JSONB NOT NULL)'
            )
        cur.execute('CREATE TABLE IF NOT EXISTS "_workhub_system" (id TEXT PRIMARY KEY, data JSONB NOT NULL)')

        for policy in DEFAULT_POLICIES:
            cur.execute(
                'INSERT INTO "attendance_policies" (id, data) VALUES (%s, %s) '
                'ON CONFLICT (id) DO NOTHING',
                (policy["id"], Jsonb(policy)),
            )
        cur.execute(
            'INSERT INTO "company_work_policy" (id, _singleton, data) VALUES (%s, %s, %s) '
            'ON CONFLICT (_singleton) DO NOTHING',
            ("company_work_policy", "company_work_policy", Jsonb(DEFAULT_COMPANY_POLICY)),
        )

        cur.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS "users_email_idx" ON "users" ((data ->> \'email\'))'
        )
        cur.execute(
            'CREATE INDEX IF NOT EXISTS "sessions_user_start_idx" ON "sessions" '
            '((data ->> \'user_id\'), (data ->> \'start\'))'
        )
        cur.execute(
            'CREATE INDEX IF NOT EXISTS "breaks_session_start_idx" ON "breaks" '
            '((data ->> \'session_id\'), (data ->> \'start\'))'
        )
        cur.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS "calendar_events_date_idx" ON "calendar_events" '
            '((data ->> \'date\'))'
        )
        cur.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS "announcement_reads_ann_user_idx" ON "announcement_reads" '
            '((data ->> \'announcement_id\'), (data ->> \'user_id\'))'
        )

        counts: dict[str, int] = {}
        for name in COLLECTIONS:
            cur.execute(f'SELECT count(*) FROM "{name}"')
            counts[name] = cur.fetchone()[0]

    print("Postgres initialized")
    for name in COLLECTIONS:
        print(f"  {name}: {counts[name]} row(s)")


if __name__ == "__main__":
    main()
