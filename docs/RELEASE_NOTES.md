# Release Notes – WorkHub

## v1.0 – Initial Release

**Release Date:** June 19, 2026

### Features
- User registration and login (basic email/password)
- Work session tracking (start/stop)
- Break tracking with in-session support
- Admin dashboard showing hours worked per user
- Office hours and rule configuration (admin only)
- JSON file data persistence

### Technology Stack
- Backend: FastAPI, uvicorn, pydantic
- Desktop: Tkinter
- Data: MongoDB primary, JSON fallback for local dev

### Important Notes
- Authentication uses plain text passwords (for demo only)
- No break/work duration validation enforced (policy exists but not applied)
- No testing infrastructure yet (pytest framework present)

---

## v1.1 – Calendar Engine and Desktop Shell

**Release Date:** June 2026

### New Features

#### Calendar Engine
- Dynamic calendar events drive attendance rules
- Manager can modify calendar via UI without code changes
- 7 calendar event types: WORKING_DAY, HALF_DAY, FULL_DAY_SATURDAY, HOLIDAY, COMP_OFF, LONG_WEEKEND, COMPANY_EVENT

#### Enhanced Dashboard
- Today's status with calendar event info and target hours
- Today's progress with work/time remaining and estimated completion
- Monthly summary with working days counter and holiday count
- Upcoming calendar events feed
- Team announcements section
- Compact calendar with month navigation

#### Calendar View
- Monthly calendar with compact color-coded day cells
- Month navigation for previous/next views
- Holiday and company event visibility

#### Manager Features
- Calendar management (create holidays, comp-offs, long weekends)
- Auto-announcement generation when calendar changes
- Team attendance reports
- React web app now serves as the primary beta surface
- Browser forgot-password flow remains available

#### Attendance Policy Engine
- Rules derived from calendar event types
- Configurable min/target/max values per event type
- Automatic attendance calculation from events

### Breaking Changes
- None (backward compatible with v1.0)

### Migration Notes
1. Run migration script: `python scripts/migrate_v1.0_to_v1.1.py`
2. Start MongoDB or set `MONGO_URI`
3. Restart backend server
4. If MongoDB is unavailable, the backend falls back to `data/*.json`

### New Endpoints
- `POST /calendar/events` – Create calendar event
- `GET /calendar/events/{date}` – Get event for date
- `GET /calendar/policy/{type}` – Get attendance policy
- `POST /announcements` – Create team announcement
- `GET /announcements` – List announcements
- `POST /announcements/{id}/read` – Mark as read

### Technical Improvements
- Modular calendar engine service
- Better separation of concerns
- Extensible event type system
- MongoDB-backed persistence with JSON fallback
- Auto-announcement generator
- Web-only beta rollout supported with browser config, session-scoped state, and report CSV export
- Admin calendar date entry normalizes common formats before save

---

## Future Releases

### v2.0 – Extended Features
- Leave management system
- WhatsApp notification integration
- Mobile app (iOS/Android)

### v3.0 – Enterprise Features
- Payroll integration
- SSO login (LDAP/OAuth2)
- Teams/Slack integration
