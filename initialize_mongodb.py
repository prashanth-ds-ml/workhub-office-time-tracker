from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient


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
    mongo_uri = (os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "").strip()
    database_name = os.getenv("MONGO_DB", "workhub").strip() or "workhub"
    if not mongo_uri:
        raise SystemExit("MONGO_URI is missing from .env")

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    database = client[database_name]

    existing = set(database.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            database.create_collection(name)

    for policy in DEFAULT_POLICIES:
        database.attendance_policies.update_one(
            {"id": policy["id"]},
            {"$setOnInsert": policy},
            upsert=True,
        )
    database.company_work_policy.update_one(
        {"_singleton": "company_work_policy"},
        {"$setOnInsert": DEFAULT_COMPANY_POLICY},
        upsert=True,
    )

    database.users.create_index([("id", ASCENDING)], unique=True)
    database.users.create_index([("email", ASCENDING)], unique=True)
    database.sessions.create_index([("id", ASCENDING)], unique=True)
    database.sessions.create_index([("user_id", ASCENDING), ("start", ASCENDING)])
    database.breaks.create_index([("id", ASCENDING)], unique=True)
    database.breaks.create_index([("session_id", ASCENDING), ("start", ASCENDING)])
    database.calendar_events.create_index([("id", ASCENDING)], unique=True)
    database.calendar_events.create_index([("date", ASCENDING)], unique=True)
    database.announcements.create_index([("id", ASCENDING)], unique=True)
    database.announcement_reads.create_index(
        [("announcement_id", ASCENDING), ("user_id", ASCENDING)],
        unique=True,
    )

    counts = {name: database[name].count_documents({}) for name in COLLECTIONS}
    print(f"MongoDB initialized: database={database_name}")
    for name in COLLECTIONS:
        print(f"  {name}: {counts[name]} document(s)")


if __name__ == "__main__":
    main()
