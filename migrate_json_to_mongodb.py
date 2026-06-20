from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

from pymongo import ASCENDING, MongoClient, UpdateOne


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
    parser = argparse.ArgumentParser(description="Migrate WorkHub JSON data to MongoDB")
    parser.add_argument("--source", type=Path, required=True, help="Directory containing WorkHub JSON files")
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI") or os.getenv("MONGODB_URI"))
    parser.add_argument("--database", default=os.getenv("MONGO_DB", "workhub"))
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        raise SystemExit("Refusing migration without --confirm")
    if not args.mongo_uri:
        raise SystemExit("Provide --mongo-uri or set MONGO_URI")

    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[args.database]

    migrated = 0
    for filename, collection_name in COLLECTIONS.items():
        rows = load_rows(args.source / filename)
        if filename == "users.json":
            rows = [{**row, "password": hash_password(row["password"])} for row in rows]
        operations = []
        for row in rows:
            if row.get("id"):
                key = {"id": row["id"]}
            else:
                key = {"_singleton": Path(filename).stem}
                row = {**row, "_singleton": Path(filename).stem}
            operations.append(UpdateOne(key, {"$set": row}, upsert=True))
        if operations:
            db[collection_name].bulk_write(operations, ordered=False)
            migrated += len(operations)

    db["users"].create_index([("id", ASCENDING)], unique=True)
    db["users"].create_index([("email", ASCENDING)], unique=True)
    db["calendar_events"].create_index([("date", ASCENDING)], unique=True)
    db["announcement_reads"].create_index(
        [("announcement_id", ASCENDING), ("user_id", ASCENDING)],
        unique=True,
    )
    if db["users"].count_documents({}) > 0:
        db["_workhub_system"].update_one(
            {"_id": "bootstrap_admin"},
            {"$set": {"claimed": True}},
            upsert=True,
        )
    print(f"Migrated {migrated} records into MongoDB database '{args.database}'.")


if __name__ == "__main__":
    main()
