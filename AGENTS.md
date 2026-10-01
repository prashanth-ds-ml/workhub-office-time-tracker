# AGENTS.md

## WorkHub – Office Time Tracker

**Core Philosophy:** Employees should never wonder about holidays, half-days, or work targets. The system answers everything immediately through a dynamic Company Calendar Engine in a fast web workspace, with the Windows desktop client retained as a legacy distribution option.

### Quick Start

**Backend (Terminal 1):**
```bash
.\create_venv.bat  # or manually: python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt
uvicorn app:app --reload
```
API docs at `http://127.0.0.1:8000/docs`

**Web App (Terminal 2):**
```bash
cd web_app
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

### Current Status

**PRD Status:** WorkHub v1.1 PRD created with new Calendar Engine module. Core calendar event types defined, attendance policies derived from events, not hardcoded.

**What's Implemented now:**
- React web UI with login, calendar, attendance history, announcements, employees, policies, and reports
- FastAPI backend with user auth, session/break tracking, calendar events, and announcements
- Postgres (Neon) persistence on Vercel, with a JSON-file fallback for local dev only (production refuses the fallback)
- Python Tkinter desktop UI as a legacy client (not maintained; known timezone bug against the IST-aware API)
- Standalone Windows reminder app (`scripts/reminder_daemon.py`, built by `scripts/build_reminder_exe.ps1` into `release/WorkHubReminder.zip`): opens WorkHub at login and wake, and reminds on working days only. See `docs/REMINDER_APP.md`.

**Beta Status:** The web app is ready for a small monitored employee beta. Use the browser surface as the primary experience and treat the desktop client as legacy distribution only.

**WorkHub v1.1 New Requirements:**
- Calendar events drive attendance rules
- Manager can modify calendar via UI without code changes
- Data lives in Postgres (Neon) in production
- Web app is the primary employee and admin surface
- The reminder app auto-starts at login and wake; reminders follow the company calendar (`GET /api/calendar/public/today`)

### Accounts

No demo or default users are seeded.

- Employee/User registration does not require the Admin bootstrap key.
- Administrator registration requires `WORKHUB_BOOTSTRAP_SECRET`.

### Authentication

Email/password login. The API returns a time-limited JWT, and the desktop app
sends it using `Authorization: Bearer <token>`.

The React web app also uses the JWT for authenticated API requests and relies on
FastAPI-served bootstrap/config endpoints for first load.

### API Calls

Primary web app → FastAPI-served React bundle and JSON API over HTTPS.

Hosting: Vercel (React build + FastAPI function under `/api`), auto-deployed from `main`.

Live URL: `https://workhub-office-time-tracker.vercel.app` (Render is no longer used).

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
| Run web app | `cd web_app && npm install && npm run dev` |
| Build web app | `cd web_app && npm run build` |
| Run desktop app | `python desktop_app.py` |
| Install auto-start | `python desktop_app.py --install-startup` |
| Build reminder package | `.\scriptsuild_reminder_exe.ps1` → `release\WorkHubReminder.zip` |
| Run smoke checks | `$env:PYTHONPATH='.'; $env:WORKHUB_STORAGE='json'; python tests\integration_smoke.py` (JSON store, no database needed); `tests\postgres_integration_smoke.py` needs a real `POSTGRES_URL` and writes to that DB |
| Run web tests | `cd web_app && npm test` |

### Gotchas (v1.0)

1. Postgres is the primary store. JSON fallback is for local dev only. Each Vercel instance caches some tables in memory (users, calendar); use `_refresh_users_cache()` / `_refresh_calendar_cache()` before reading them in new endpoints.
2. The React web app is the primary product surface; the desktop app is legacy.
3. The desktop app minimizes to the background on close instead of exiting.
4. Auto-start is installed through the desktop app helper and Windows startup folder.

### v1.1 Priority Tasks

1. **Web UX** — Keep the calendar compact, minimal, and easy to scan by month.
2. **Backend** — Keep attendance and announcements derived from calendar events.
3. **Deployment** — Keep the Postgres connection and Vercel deployment straightforward; the reminder app is the supported desktop piece.
