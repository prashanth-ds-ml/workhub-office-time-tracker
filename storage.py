from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

_POSTGRES_URL = (
    os.getenv("POSTGRES_URL")
    or os.getenv("POSTGRES_URL_NON_POOLING")
    or os.getenv("DATABASE_URL")
)
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


def _to_text(value: Any) -> str:
    """Render a filter value the same way `data ->> key` renders a stored JSON scalar."""
    value = _jsonify(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


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


import re

_SAFE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_key(key: str) -> str:
    if not _SAFE_KEY.match(key):
        raise ValueError(f"Unsafe sort key: {key!r}")
    return key


_OPERATORS = {
    "$in": "= ANY(%s)",
    "$ne": "!=",
    "$gte": ">=",
    "$gt": ">",
    "$lte": "<=",
    "$lt": "<",
}


class _PostgresStorage(_BaseStorage):
    def __init__(self) -> None:
        self.conn = psycopg.connect(_POSTGRES_URL, autocommit=True, row_factory=dict_row)
        self.conn.execute("SELECT 1")

    def _table(self, path: Path) -> str:
        return _FILE_TO_COLLECTION.get(path.name, path.stem)

    def _where(self, filter: Dict[str, Any] | None) -> tuple[str, list[Any]]:
        if not filter:
            return "", []
        clauses: list[str] = []
        params: list[Any] = []
        for key, expected in filter.items():
            column = f"(data ->> %s)"
            if isinstance(expected, dict):
                for operator, right in expected.items():
                    if operator not in _OPERATORS:
                        raise ValueError(f"Unsupported query operator: {operator}")
                    if operator == "$in":
                        params.append(key)
                        clauses.append(f"{column} = ANY(%s)")
                        params.append([_to_text(item) for item in right])
                    elif operator == "$ne" and right is None:
                        params.append(key)
                        clauses.append(f"{column} IS NOT NULL")
                    else:
                        params.append(key)
                        clauses.append(f"{column} {_OPERATORS[operator]} %s")
                        params.append(_to_text(right))
            elif expected is None:
                params.append(key)
                clauses.append(f"{column} IS NULL")
            else:
                params.append(key)
                clauses.append(f"{column} = %s")
                params.append(_to_text(expected))
        return " WHERE " + " AND ".join(clauses), params

    def load(self, path: Path) -> List[Dict[str, Any]]:
        return self.query(path)

    def save(self, path: Path, rows: Iterable[Dict[str, Any]]) -> None:
        self.upsert(path, rows)

    def upsert(self, path: Path, rows: Iterable[Dict[str, Any]]) -> None:
        table = self._table(path)
        payload = [_jsonify(row) for row in rows]
        with self.conn.cursor() as cur:
            for row in payload:
                if row.get("id"):
                    cur.execute(
                        f'INSERT INTO "{table}" (id, data) VALUES (%s, %s) '
                        f'ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data',
                        (row["id"], Jsonb(row)),
                    )
                elif row.get("_singleton"):
                    cur.execute(
                        f'INSERT INTO "{table}" (id, _singleton, data) VALUES (%s, %s, %s) '
                        f'ON CONFLICT (_singleton) DO UPDATE SET data = EXCLUDED.data',
                        (row["_singleton"], row["_singleton"], Jsonb(row)),
                    )

    def delete(self, path: Path, row_id: str) -> None:
        self.conn.execute(f'DELETE FROM "{self._table(path)}" WHERE id = %s', (row_id,))

    def clear(self, path: Path) -> None:
        self.conn.execute(f'TRUNCATE "{self._table(path)}"')

    def ensure_indexes(self) -> None:
        with self.conn.cursor() as cur:
            for collection_name in {*_FILE_TO_COLLECTION.values(), "company_work_policy"}:
                cur.execute(
                    f'CREATE TABLE IF NOT EXISTS "{collection_name}" ('
                    f'id TEXT PRIMARY KEY, _singleton TEXT UNIQUE, data JSONB NOT NULL)'
                )
            cur.execute('CREATE TABLE IF NOT EXISTS "_workhub_system" (id TEXT PRIMARY KEY, data JSONB NOT NULL)')

            def index(table: str, name: str, expr: str, unique: bool = False) -> None:
                cur.execute(
                    f'CREATE {"UNIQUE " if unique else ""}INDEX IF NOT EXISTS "{name}" '
                    f'ON "{table}" ({expr})'
                )

            index("users", "users_email_idx", "(data ->> 'email')", unique=True)
            index("users", "users_username_idx", "(data ->> 'username')")
            index("sessions", "sessions_user_start_idx", "(data ->> 'user_id'), (data ->> 'start')")
            index("sessions", "sessions_user_end_idx", "(data ->> 'user_id'), (data ->> 'end')")
            index("breaks", "breaks_session_start_idx", "(data ->> 'session_id'), (data ->> 'start')")
            index("breaks", "breaks_session_end_idx", "(data ->> 'session_id'), (data ->> 'end')")
            index("calendar_events", "calendar_events_date_idx", "(data ->> 'date')", unique=True)
            index("announcements", "announcements_created_at_idx", "(data ->> 'created_at')")
            index(
                "announcement_reads",
                "announcement_reads_user_ann_idx",
                "(data ->> 'user_id'), (data ->> 'announcement_id')",
            )
            index(
                "announcement_reads",
                "announcement_reads_ann_user_idx",
                "(data ->> 'announcement_id'), (data ->> 'user_id')",
                unique=True,
            )
            index("company_events", "company_events_date_idx", "(data ->> 'event_date')")

    def health(self) -> Dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            database = cur.fetchone()["current_database"]
        return {
            "backend": "postgres",
            "connected": True,
            "production_safe": True,
            "database": database,
        }

    def claim_first_admin(self) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                'INSERT INTO "_workhub_system" (id, data) VALUES (%s, %s) '
                'ON CONFLICT (id) DO NOTHING RETURNING id',
                (
                    "bootstrap_admin",
                    Jsonb({"claimed": True, "claimed_at": datetime.now(INDIA_TZ).isoformat()}),
                ),
            )
            return cur.fetchone() is not None

    def reset_first_admin_claim(self) -> None:
        self.conn.execute('DELETE FROM "_workhub_system" WHERE id = %s', ("bootstrap_admin",))

    def query(
        self,
        path: Path,
        filter: Dict[str, Any] | None = None,
        sort: List[tuple[str, int]] | None = None,
        limit: int | None = None,
    ) -> List[Dict[str, Any]]:
        table = self._table(path)
        where_sql, params = self._where(filter)
        sql = f'SELECT data FROM "{table}"{where_sql}'
        if sort:
            order_parts = [
                f"(data ->> '{_safe_key(key)}') {'DESC' if direction < 0 else 'ASC'}"
                for key, direction in sort
            ]
            sql += " ORDER BY " + ", ".join(order_parts)
        if limit is not None:
            sql += " LIMIT %s"
            params = [*params, limit]
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return [row["data"] for row in cur.fetchall()]


def _build_storage() -> _BaseStorage:
    if not _FORCE_JSON and _POSTGRES_URL:
        try:
            storage = _PostgresStorage()
            storage.ensure_indexes()
            return storage
        except psycopg.Error as exc:
            if _PRODUCTION:
                raise RuntimeError("Postgres is required when WORKHUB_ENV=production") from exc
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
    return "postgres" if isinstance(_STORAGE, _PostgresStorage) else "json"


def storage_health() -> Dict[str, Any]:
    return _STORAGE.health()


def claim_first_admin() -> bool:
    return _STORAGE.claim_first_admin()


def reset_first_admin_claim() -> None:
    _STORAGE.reset_first_admin_claim()
