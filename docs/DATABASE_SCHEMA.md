# Database Schema – WorkHub v1.1

## Overview

This document describes the Postgres tables used by WorkHub v1.1. The backend
can fall back to the JSON files in `data/` for local development, but Postgres
is the primary store. Each table has the shape `id TEXT PRIMARY KEY (or
_singleton TEXT PRIMARY KEY for the one config doc), data JSONB NOT NULL` —
the JSON shapes below live inside the `data` column, unchanged from the
previous MongoDB documents.

## Table Structure

```
users
sessions
breaks
calendar_events
holiday_master
attendance_policies
announcements
company_events
announcement_reads
alert_acknowledgements
```

## Existing Tables (v1.0)

### users

```json
{
  "id": "string (UUID)",
  "username": "string",
  "email": "string",
  "password": "string",
  "role": "User|Admin",
  "office_hours": {
    "start": "HH:MM",
    "end": "HH:MM"
  },
  "rules": {
    "min_work_hours": "number",
    "max_work_hours": "number",
    "min_break_minutes": "number",
    "max_break_minutes": "number"
  }
}
```

### sessions

```json
{
  "id": "string (UUID)",
  "user_id": "string (UUID)",
  "start": "ISO8601",
  "end": "ISO8601|null",
  "breaks": [
    {
      "start": "ISO8601",
      "end": "ISO8601|null"
    }
  ]
}
```

### breaks

```json
{
  "id": "string (UUID)",
  "session_id": "string (UUID)",
  "start": "ISO8601",
  "end": "ISO8601|null"
}
```

## New Tables (v1.1)

### calendar_events

```json
{
  "id": "string (UUID)",
  "event_type": "enum(WORKING_DAY, HALF_DAY, FULL_DAY_SATURDAY, HOLIDAY, COMP_OFF, LONG_WEEKEND, COMPANY_EVENT)",
  "date": "YYYY-MM-DD",
  "title": "string",
  "description": "string|null",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "manager_id": "string (UUID)|null",
  "related_event_id": "string (UUID)|null"
}
```

**Relationships:**
- `manager_id` → `users.id` (who created/modified the event)
- `related_event_id` → `calendar_events.id` (for comp-offs, etc.)

### attendance_policies

```json
{
  "id": "string (UUID)",
  "event_type": "enum(WORKING_DAY, HALF_DAY, FULL_DAY_SATURDAY, HOLIDAY, COMP_OFF, LONG_WEEKEND, COMPANY_EVENT)",
  "min_work_hours": "number",
  "target_work_hours": "number",
  "max_break_minutes": "number",
  "created_at": "ISO8601"
}
```

**Default Policies:**

| Event Type | Min Hours | Target Hours | Max Break |
|------------|-----------|--------------|-----------|
| WORKING_DAY | 6 | 6.5 | 90 min |
| HALF_DAY | 3.5 | 4 | 30 min |
| FULL_DAY_SATURDAY | 6 | 6.5 | 90 min |
| HOLIDAY | 0 | 0 | 0 |
| COMP_OFF | 0 | 0 | 0 |
| LONG_WEEKEND | 0 | 0 | 0 |
| COMPANY_EVENT | 0 | 0 | 0 |

### announcements

```json
{
  "id": "string (UUID)",
  "title": "string",
  "content": "string",
  "created_at": "ISO8601",
  "effective_date": "YYYY-MM-DD",
  "event_id": "string (UUID)|null",
  "event_type": "string|null",
  "is_read": "boolean (auto-calculated per user)"
}
```

**Example Auto-Generated Announcement:**
```json
{
  "id": "a001",
  "title": "Calendar Update",
  "content": "June 27 marked as Full Working Saturday.",
  "created_at": "2026-06-19T10:00:00",
  "effective_date": "2026-06-27",
  "event_id": "h013",
  "event_type": "FULL_DAY_SATURDAY"
}
```

### company_events

```json
{
  "id": "string (UUID)",
  "title": "string",
  "description": "string",
  "event_date": "YYYY-MM-DD",
  "event_time": "HH:MM",
  "location": "string|null",
  "organizer": "string (UUID)|null",
  "created_at": "ISO8601"
}
```

**Example:**
```json
{
  "id": "c001",
  "title": "Monthly Review Meeting",
  "description": "Quarterly team review",
  "event_date": "2026-06-30",
  "event_time": "14:00",
  "location": "Conference Room A",
  "organizer": "admin123",
  "created_at": "2026-06-19T09:00:00"
}
```

### announcement_reads

```json
{
  "id": "string (UUID)",
  "announcement_id": "string (UUID)",
  "user_id": "string (UUID)",
  "read_at": "ISO8601|null",
  "acknowledged": "boolean"
}
```

### alert_acknowledgements

```json
{
  "id": "string (UUID)",
  "user_id": "string (UUID)",
  "alert_type": "enum(ATTENDANCE_WARNING, BREAK_WARNING, WORK_LIMIT_WARNING)",
  "message": "string",
  "created_at": "ISO8601",
  "acknowledged": "boolean",
  "acknowledged_at": "ISO8601|null"
}
```

## Data Relationships

```
users
  └── sessions (user_id)
        └── breaks (session_id)
  └── calendar_events (manager_id)
        └── announcements (event_id)
  └── announcement_reads (user_id)
        └── announcements (announcement_id)
  └── alert_acknowledgements (user_id)

calendar_events
  └── attendance_policies (event_type)
  └── announcements (event_id)
```

## Migration Path

### v1.0 → v1.1

The migration script still seeds the same records, but the backend now writes to Postgres when available:
```bash
python scripts/migrate_v1.0_to_v1.1.py
```

If Postgres is unavailable, the backend falls back to `data/*.json` for local development.

### v1.1 → v1.2 (MongoDB → Postgres)

```bash
python initialize_postgres.py
python migrate_json_to_postgres.py --source data --confirm
```

See `MIGRATION.md` for details.

## Queries

### Get Today's Calendar Event
```json
GET /calendar/events/2026-06-19
Response: {"id": "...", "event_type": "WORKING_DAY", "title": "Normal Working Day", ...}
```

### Get Attendance Policy for Event Type
```json
GET /calendar/policy/WORKING_DAY
Response: {"min_work_hours": 6, "target_work_hours": 6.5, "max_break_minutes": 90}
```

### Get Attendance for User (Daily)
```bash
GET /attendance/2026-06-19
Response: {
  "calendar_event": "WORKING_DAY",
  "target_hours": 6.5,
  "work_done": 4.5,
  "remaining": 2.0,
  "breaks_used": 35,
  "break_remaining": 55,
  "estimated_completion": "16:30"
}
```

## Future Extensions

- Add `deleted_at` for soft deletes
- Add `audit_log` for tracking who changed what and when
- Add `recurring_event` support for weekly events
