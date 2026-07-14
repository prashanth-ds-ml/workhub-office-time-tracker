# Migration Guide – v1.0 to v1.1

This guide covers the database schema and API changes between v1.0 and v1.1.

## Overview

v1.1 introduces the **Calendar Engine** as the source of truth for attendance rules. All attendance policies are derived from calendar events, removing hardcoded rules from the codebase.

## Database Changes

### New Files

| File | Purpose |
|------|---------|
| `data/calendar_events.json` | Calendar events (holidays, half-days, etc.) |
| `data/attendance_policies.json` | Rules for each event type |
| `data/announcements.json` | Company announcements |
| `data/company_events.json` | Non-attendance events (meetings, outings) |
| `data/announcement_reads.json` | User read status (future) |
| `data/alert_acknowledgements.json` | User alert ack (future) |

### Existing Files (No Change)
- `data/users.json`
- `data/sessions.json`
- `data/breaks.json`

### v1.0 Data Fields (No Change)
```json
{
  "id": "string",
  "username": "string",
  "email": "string",
  "password": "string",
  "role": "User|Admin",
  "office_hours": {"start": "HH:MM", "end": "HH:MM"},
  "rules": {"min_work_hours": number, "max_work_hours": number, "min_break_minutes": number, "max_break_minutes": number}
}
```

## API Changes

### New v1.1 Endpoints

#### Calendar API (`/api/v1/calendar/...`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/events` | POST | Create calendar event (admin/manager) |
| `/events/{date}` | GET | Get event for specific date |
| `/events/types` | GET | List all event types |
| `/policy/{event_type}` | GET | Get attendance policy for event type |
| `/engine/today` | GET | Get today's calendar + policy |

#### Announcement API (`/announcements`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/announcements` | POST | Create announcement |
| `/announcements` | GET | List announcements |
| `/announcements/{id}/read` | POST | Mark announcement as read |

### Modified v1.0 Endpoints

#### `/me` (Enhanced)
**v1.0 Response:**
```json
{
  "id": "...",
  "username": "...",
  "email": "...",
  "role": "User"
}
```

**v1.1 Response:**
```json
{
  "id": "...",
  "username": "...",
  "email": "...",
  "role": "User",
  "today": {
    "calendar_event": "WORKING_DAY",
    "target_hours": 6.5,
    "office_hours": {"start": "09:00", "end": "17:00"}
  }
}
```

#### `/office_hours/{user_id}` (Enhanced)
**v1.1 Request Body:**
```json
{
  "start_time": "09:00",
  "end_time": "17:00",
  "policy_override": {
    "min_work_hours": 6,
    "target_work_hours": 6.5
  }
}
```

## Migration Script

### Run Migration

```bash
python scripts/migrate_v1.0_to_v1.1.py
```

This script:
1. Creates new JSON files with empty arrays
2. Populates `calendar_events.json` with 2026 holidays
3. Populates `attendance_policies.json` with default policies
4. Preserves existing data (users, sessions, breaks)

### Manual Migration (if needed)

```python
# Create calendar_events.json
[
  {"id": "h001", "event_type": "HOLIDAY", "date": "2026-01-01", "title": "New Year", "created_at": "2026-06-19T...", "manager_id": "admin123"},
  {"id": "h002", "event_type": "HOLIDAY", "date": "2026-01-15", "title": "Makara Sankranti", "created_at": "2026-06-19T..."}
  # ... add all 2026 holidays
]

# Create attendance_policies.json
[
  {"id": "p001", "event_type": "WORKING_DAY", "min_work_hours": 6, "target_work_hours": 6.5, "max_break_minutes": 90},
  {"id": "p002", "event_type": "HALF_DAY", "min_work_hours": 3.5, "target_work_hours": 4, "max_break_minutes": 30}
]

# Create announcements.json
[]

# Create company_events.json
[]

# Create announcement_reads.json
[]

# Create alert_acknowledgements.json
[]
```

## Attendance Engine Changes

### v1.0 (Hardcoded)
```python
def calculate_work_target():
    # Hardcoded 6h target
    return 6
```

### v1.1 (Dynamic)
```python
def calculate_work_target(date):
    event_type = get_calendar_event(date).event_type
    policy = get_attendance_policy(event_type)
    return policy.target_work_hours
```

## Breaking Changes

### None

v1.1 is fully backward compatible with v1.0 data. Existing sessions and breaks continue to work.

## Testing Checklist

After migration:

- [ ] Calendar events load correctly
- [ ] Attendance policies return correct values
- [ ] Dashboard shows today's calendar event
- [ ] Manager can create holiday
- [ ] Auto-announcement generates correctly
- [ ] v1.0 sessions still display
- [ ] v1.1 attendance calculation matches policy

## Rollback Plan

If v1.1 issues occur:

```bash
# Stop backend
# backup data/ folder
# Restore from backup
cd data
git checkout HEAD -- .
# Restart backend
```

## Support

For migration issues, refer to:
- BUILD_ORDER.md for step-by-step guidance
- API docs at http://127.0.0.1:8000/docs
- Test scripts in `tests/test_v1.1_migration.py`

# Migration Guide – v1.1 to v1.2 (MongoDB → Postgres, Render → Vercel)

v1.2 replaces the MongoDB storage backend with Postgres (Vercel
Postgres/Neon) and moves hosting from Render to Vercel. No API or data-shape
changes — every collection becomes a Postgres table with the same JSON
document stored in a `data JSONB` column. See `DATABASE_SCHEMA.md` for the
table shape and `VERCEL_DEPLOYMENT.md` for the hosting setup.

### Steps

1. Provision a Postgres database (Vercel Postgres/Neon) and set `POSTGRES_URL`.
2. Run `python initialize_postgres.py` to create tables/indexes and seed
   default attendance policies.
3. If migrating existing data out of MongoDB Atlas: export each collection to
   JSON (or point a modified `migrate_json_to_postgres.py` at a live Mongo
   connection instead of `data/*.json`), then run:
   ```bash
   python migrate_json_to_postgres.py --source <dir> --confirm
   ```
4. Remove `MONGO_URI`/`MONGO_DB` env vars; add `POSTGRES_URL` in their place.
5. Deploy via Vercel (`vercel.json` + `api/index.py`) instead of Render
   (`render.yaml`, now removed).

### Breaking Changes

None for API consumers. `storage.storage_backend()` now returns `"postgres"`
instead of `"mongo"`; anything asserting on that value (tests, `/health`
checks) must be updated — already done in `postgres_integration_smoke.py`.