# AGENTS.md

## WorkHub v1.1 – Office Time Tracker

**Core Philosophy:** Employees should never wonder about holidays, half-days, or work targets. The system answers everything immediately through a dynamic Company Calendar Engine in a minimal Python desktop app.

### Quick Start

**Backend (Terminal 1):**
```bash
.\create_venv.bat  # or manually: python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt
uvicorn app:app --reload
```
API docs at `http://127.0.0.1:8000/docs`

**Desktop App (Terminal 2):**
```bash
python desktop_app.py
```

### Current Status

**PRD Status:** WorkHub v1.1 PRD created with new Calendar Engine module. Core calendar event types defined, attendance policies derived from events, not hardcoded.

**What's Implemented now:**
- FastAPI backend with user auth, session/break tracking, calendar events, and announcements
- MongoDB-backed persistence with JSON fallback for local dev
- Python Tkinter desktop UI with login, compact month calendar, work/break timer, and team announcements

**WorkHub v1.1 New Requirements:**
- Calendar events drive attendance rules
- Manager can modify calendar via UI without code changes
- Data should be live in MongoDB by default
- Desktop app should auto-start during office hours and stay in the tray/background

### Default Users (in `data/users.json`)

- User: `user@example.com` / `user123`
- Admin: `admin@example.com` / `admin123`

### Authentication

Email/password login. The desktop app stores the current user id locally and sends `X-User-Id` to the API.

### API Calls

Desktop app → `http://127.0.0.1:8000` via `requests`.

### Calendar Event Types (v1.1)

- `WORKING_DAY` (6h min, 6h30m target, 1h30m break max)
- `HALF_DAY` (3h30m min, 4h target, 30m break max)
- `FULL_DAY_SATURDAY`
- `HOLIDAY`
- `COMP_OFF`
- `LONG_WEEKEND`
- `COMPANY_EVENT`

### Commands Summary

| Purpose | Command |
|---------|---------|
| Create venv | `.venv\Scripts\activate` (Windows) |
| Install deps | `pip install -r requirements.txt` |
| Run backend | `uvicorn app:app --reload` |
| Run desktop app | `python desktop_app.py` |
| Install auto-start | `python desktop_app.py --install-startup` |
| Run tests | `pytest` (no tests yet) |

### Gotchas (v1.0)

1. MongoDB is the primary store, but the backend falls back to JSON if Mongo is unavailable.
2. The desktop app minimizes to the background on close instead of exiting.
3. Auto-start is installed through the desktop app helper and Windows startup folder.
4. The Tkinter desktop app is the primary product surface.

### v1.1 Priority Tasks

1. **Desktop UX** — Keep the calendar compact, minimal, and easy to scan by month.
2. **Backend** — Keep attendance and announcements derived from calendar events.
3. **Deployment** — Make MongoDB connection and desktop auto-start straightforward to install.
