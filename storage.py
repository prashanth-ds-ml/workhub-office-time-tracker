from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient, ReturnDocument, UpdateOne
from pymongo.errors import PyMongoError

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

_MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://127.0.0.1:27017"
_MONGO_DB = os.getenv("MONGO_DB", "office_time_tracker")
_FORCE_JSON = os.getenv("WORKHUB_STORAGE", "").lower() == "json"
_PRODUCTION = os.getenv("WORKHUB_ENV", "development").lower() == "production"
INDIA_TZ = timezone(timedelta(hours=5, minutes=30))

_FILE_TO_COLLECTION = {
    "users.json": "users",
    "sessions.json": "sessions",
    "breaks.json": "breaks",
    "calendar_events.json": "calendar_events",
    "holiday_master.json": "holiday_master",
    "attendance_policies.json": "attendance_policies",
    "announcements.json": "announcements",
    "company_events.json": "company_events",
    "announcement_reads.json": "announcement_reads",
    "alert_acknowledgements.json": "alert_acknowledgements",
}


def _jsonify(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonify(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonify(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonify(item) for item in value]
    return value


class _BaseStorage:
    def load(self, path: Path) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def save(self, path: Path, rows: Iterable[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def upsert(self, path: Path, rows: Iterable[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def delete(self, path: Path, row_id: str) -> None:
        raise NotImplementedError

    def clear(self, path: Path) -> None:
        raise NotImplementedError

    def health(self) -> Dict[str, Any]:
        raise NotImplementedError

    def claim_first_admin(self) -> bool:
        raise NotImplementedError

    def reset_first_admin_claim(self) -> None:
        raise NotImplementedError

    def query(
        self,
        path: Path,
        filter: Dict[str, Any] | None = None,
        sort: List[tuple[str, int]] | None = None,
        limit: int | None = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def find_one(
        self,
        path: Path,
        filter: Dict[str, Any],
        sort: List[tuple[str, int]] | None = None,
    ) -> Dict[str, Any] | None:
        rows = self.query(path, filter=filter, sort=sort, limit=1)
        return rows[0] if rows else None


class _JsonStorage(_BaseStorage):
    def load(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return []
        return json.loads(text)

    def save(self, path: Path, rows: Iterable[Dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [_jsonify(row) for row in rows]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def upsert(self, path: Path, rows: Iterable[Dict[str, Any]]) -> None:
        existing = self.load(path)
        payload = [_jsonify(row) for row in rows]
        by_id = {row.get("id"): row for row in existing if row.get("id")}
        singletons = [row for row in existing if not row.get("id")]
        for row in payload:
            if row.get("id"):
                by_id[row["id"]] = row
            else:
                singletons = [row]
        self.save(path, [*by_id.values(), *singletons])

    def delete(self, path: Path, row_id: str) -> None:
        rows = [row for row in self.load(path) if row.get("id") != row_id]
        self.save(path, rows)

    def clear(self, path: Path) -> None:
        self.save(path, [])

    def health(self) -> Dict[str, Any]:
        return {"backend": "json", "connected": True, "production_safe": False}

    def claim_first_admin(self) -> bool:
        return True

    def reset_first_admin_claim(self) -> None:
        return

    @staticmethod
    def _coerce(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value
        return value

    def _matches(self, row: Dict[str, Any], filter: Dict[str, Any]) -> bool:
        for key, expected in filter.items():
            actual = row.get(key)
            if isinstance(expected, dict):
                left = self._coerce(actual)
                for operator, right in expected.items():
                    right_value = self._coerce(right)
                    if operator == "$in":
                        if actual not in right:
                            return False
                    elif operator == "$ne":
                        if actual == right:
                            return False
                    elif operator == "$gte":
                        if left < right_value:
                            return False
                    elif operator == "$gt":
                        if left <= right_value:
                            return False
                    elif operator == "$lte":
                        if left > right_value:
                            return False
                    elif operator == "$lt":
                        if left >= right_value:
                            return False
                    else:
                        raise ValueError(f"Unsupported query operator: {operator}")
            elif actual != expected:
                return False
        return True

    def query(
        self,
        path: Path,
        filter: Dict[str, Any] | None = None,
        sort: List[tuple[str, int]] | None = None,
        limit: int | None = None,
    ) -> List[Dict[str, Any]]:
        rows = self.load(path)
        if filter:
            rows = [row for row in rows if self._matches(row, filter)]
        if sort:
            for key, direction in reversed(sort):
                rows.sort(key=lambda row: self._coerce(row.get(key)), reverse=direction < 0)
        if limit is not None:
            rows = rows[:limit]
        return rows


class _MongoStorage(_BaseStorage):
    def __init__(self) -> None:
        self.client = MongoClient(_MONGO_URI, serverSelectionTimeoutMS=1500)
        self.client.admin.command("ping")
        self.db = self.client[_MONGO_DB]

    def _collection_name(self, path: Path) -> str:
        return _FILE_TO_COLLECTION.get(path.name, path.stem)

    def load(self, path: Path) -> List[Dict[str, Any]]:
        collection = self.db[self._collection_name(path)]
        return [
            {key: value for key, value in row.items() if key != "_id"}
            for row in collection.find({})
        ]

    def save(self, path: Path, rows: Iterable[Dict[str, Any]]) -> None:
        self.upsert(path, rows)

    def upsert(self, path: Path, rows: Iterable[Dict[str, Any]]) -> None:
        collection = self.db[self._collection_name(path)]
        payload = [_jsonify(row) for row in rows]
        operations = [
            UpdateOne(
                {"id": row["id"]} if row.get("id") else {"_singleton": row["_singleton"]},
                {"$set": row},
                upsert=True,
            )
            for row in payload
            if row.get("id") or row.get("_singleton")
        ]
        if operations:
            collection.bulk_write(operations, ordered=False)

    def delete(self, path: Path, row_id: str) -> None:
        self.db[self._collection_name(path)].delete_one({"id": row_id})

    def clear(self, path: Path) -> None:
        self.db[self._collection_name(path)].delete_many({})

    def ensure_indexes(self) -> None:
        self.db["users"].create_index([("id", ASCENDING)], unique=True)
        self.db["users"].create_index([("email", ASCENDING)], unique=True)
        self.db["users"].create_index([("username", ASCENDING)])
        for collection_name in _FILE_TO_COLLECTION.values():
            self.db[collection_name].create_index([("id", ASCENDING)], unique=True)
        self.db["sessions"].create_index([("user_id", ASCENDING), ("start", ASCENDING)])
        self.db["sessions"].create_index([("user_id", ASCENDING), ("end", ASCENDING)])
        self.db["breaks"].create_index([("session_id", ASCENDING), ("start", ASCENDING)])
        self.db["breaks"].create_index([("session_id", ASCENDING), ("end", ASCENDING)])
        self.db["calendar_events"].create_index([("date", ASCENDING)], unique=True)
        self.db["announcements"].create_index([("created_at", ASCENDING)])
        self.db["company_work_policy"].create_index([("_singleton", ASCENDING)], unique=True)
        self.db["announcement_reads"].create_index([("user_id", ASCENDING), ("announcement_id", ASCENDING)])
        self.db["announcement_reads"].create_index(
            [("announcement_id", ASCENDING), ("user_id", ASCENDING)],
            unique=True,
        )
        self.db["company_events"].create_index([("event_date", ASCENDING)])

    def health(self) -> Dict[str, Any]:
        self.client.admin.command("ping")
        return {
            "backend": "mongo",
            "connected": True,
            "production_safe": True,
            "database": self.db.name,
        }

    def claim_first_admin(self) -> bool:
        try:
            previous = self.db["_workhub_system"].find_one_and_update(
                {"_id": "bootstrap_admin", "claimed": {"$ne": True}},
                {"$set": {"claimed": True, "claimed_at": datetime.now(INDIA_TZ).isoformat()}},
                upsert=True,
                return_document=ReturnDocument.BEFORE,
            )
            return previous is None or not previous.get("claimed", False)
        except PyMongoError:
            return False

    def reset_first_admin_claim(self) -> None:
        self.db["_workhub_system"].delete_one({"_id": "bootstrap_admin"})

    def query(
        self,
        path: Path,
        filter: Dict[str, Any] | None = None,
        sort: List[tuple[str, int]] | None = None,
        limit: int | None = None,
    ) -> List[Dict[str, Any]]:
        collection = self.db[self._collection_name(path)]
        cursor = collection.find(filter or {}, {"_id": 0})
        if sort:
            cursor = cursor.sort(sort)
        if limit is not None:
            cursor = cursor.limit(limit)
        return [row for row in cursor]


def _build_storage() -> _BaseStorage:
    if not _FORCE_JSON:
        try:
            storage = _MongoStorage()
            storage.ensure_indexes()
            return storage
        except PyMongoError as exc:
            if _PRODUCTION:
                raise RuntimeError("MongoDB is required when WORKHUB_ENV=production") from exc
    if _PRODUCTION:
        raise RuntimeError("JSON storage is not allowed when WORKHUB_ENV=production")
    return _JsonStorage()


_STORAGE = _build_storage()


def load_rows(path: Path) -> List[Dict[str, Any]]:
    return _STORAGE.load(path)


def query_rows(
    path: Path,
    filter: Dict[str, Any] | None = None,
    sort: List[tuple[str, int]] | None = None,
    limit: int | None = None,
) -> List[Dict[str, Any]]:
    return _STORAGE.query(path, filter=filter, sort=sort, limit=limit)


def find_one_row(
    path: Path,
    filter: Dict[str, Any],
    sort: List[tuple[str, int]] | None = None,
) -> Dict[str, Any] | None:
    return _STORAGE.find_one(path, filter, sort=sort)


def save_rows(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    _STORAGE.save(path, rows)


def upsert_rows(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    _STORAGE.upsert(path, rows)


def delete_row(path: Path, row_id: str) -> None:
    _STORAGE.delete(path, row_id)


def clear_rows(path: Path) -> None:
    _STORAGE.clear(path)


def storage_backend() -> str:
    return "mongo" if isinstance(_STORAGE, _MongoStorage) else "json"


def storage_health() -> Dict[str, Any]:
    return _STORAGE.health()


def claim_first_admin() -> bool:
    return _STORAGE.claim_first_admin()


def reset_first_admin_claim() -> None:
    _STORAGE.reset_first_admin_claim()
