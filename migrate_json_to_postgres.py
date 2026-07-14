from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb


COLLECTIONS = {
    "users.json": "users",
    "sessions.json": "sessions",
    "breaks.json": "breaks",
    "calendar_events.json": "calendar_events",
    "holiday_master.json": "holiday_master",
    "attendance_policies.json": "attendance_policies",
    "company_work_policy.json": "company_work_policy",
    "announcements.json": "announcements",
    "company_events.json": "company_events",
    "announcement_reads.json": "announcement_reads",
    "alert_acknowledgements.json": "alert_acknowledgements",
}


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8").strip()
    return json.loads(content) if content else []


def hash_password(password: str) -> str:
    if password.startswith("pbkdf2_sha256$"):
        return password
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256$200000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate WorkHub JSON data to Postgres")
    parser.add_argument("--source", type=Path, required=True, help="Directory containing WorkHub JSON files")
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("POSTGRES_URL") or os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("DATABASE_URL"),
    )
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        raise SystemExit("Refusing migration without --confirm")
    if not args.postgres_url:
        raise SystemExit("Provide --postgres-url or set POSTGRES_URL")

    conn = psycopg.connect(args.postgres_url, autocommit=True)
    migrated = 0
    with conn.cursor() as cur:
        for name in COLLECTIONS.values():
            cur.execute(
                f'CREATE TABLE IF NOT EXISTS "{name}" '
                f'(id TEXT PRIMARY KEY, _singleton TEXT UNIQUE, data JSONB NOT NULL)'
            )

        for filename, table in COLLECTIONS.items():
            rows = load_rows(args.source / filename)
            if filename == "users.json":
                rows = [{**row, "password": hash_password(row["password"])} for row in rows]
            for row in rows:
                if row.get("id"):
                    cur.execute(
                        f'INSERT INTO "{table}" (id, data) VALUES (%s, %s) '
                        f'ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data',
                        (row["id"], Jsonb(row)),
                    )
                else:
                    singleton = Path(filename).stem
                    row = {**row, "_singleton": singleton}
                    cur.execute(
                        f'INSERT INTO "{table}" (id, _singleton, data) VALUES (%s, %s, %s) '
                        f'ON CONFLICT (_singleton) DO UPDATE SET data = EXCLUDED.data',
                        (singleton, singleton, Jsonb(row)),
                    )
                migrated += 1

        cur.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS "users_email_idx" ON "users" ((data ->> \'email\'))'
        )
        cur.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS "calendar_events_date_idx" ON "calendar_events" '
            '((data ->> \'date\'))'
        )
        cur.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS "announcement_reads_ann_user_idx" ON "announcement_reads" '
            '((data ->> \'announcement_id\'), (data ->> \'user_id\'))'
        )

        cur.execute('CREATE TABLE IF NOT EXISTS "_workhub_system" (id TEXT PRIMARY KEY, data JSONB NOT NULL)')
        cur.execute('SELECT count(*) FROM "users"')
        if cur.fetchone()[0] > 0:
            cur.execute(
                'INSERT INTO "_workhub_system" (id, data) VALUES (%s, %s) '
                'ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data',
                ("bootstrap_admin", Jsonb({"claimed": True})),
            )

    print(f"Migrated {migrated} records into Postgres.")


if __name__ == "__main__":
    main()
