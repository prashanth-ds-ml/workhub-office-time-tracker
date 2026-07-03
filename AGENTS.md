# AGENTS.md

## WorkHub v1.1 – Office Time Tracker

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
- MongoDB-backed persistence with JSON fallback for local dev
- Python Tkinter desktop UI with login, compact month calendar, work/break timer, and team announcements as a legacy client

**Beta Status:** The web app is ready for a small monitored employee beta. Use the browser surface as the primary experience and treat the desktop client as legacy distribution only.

**WorkHub v1.1 New Requirements:**
- Calendar events drive attendance rules
- Manager can modify calendar via UI without code changes
- Data should be live in MongoDB by default
- Web app is the primary employee and admin surface
- Desktop app should auto-start during office hours and stay in the tray/background when used

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

Legacy desktop app → configured Render HTTPS API via `requests`.

Current API: `https://workhub-api-u07x.onrender.com`

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
| Run smoke checks | `.\.venv\Scripts\python.exe integration_smoke.py` and `.\.venv\Scripts\python.exe mongo_integration_smoke.py` |
| Run web tests | `cd web_app && npm test` |

### Gotchas (v1.0)

1. MongoDB is the primary store, but the backend falls back to JSON if Mongo is unavailable.
2. The React web app is the primary product surface; the desktop app is legacy.
3. The desktop app minimizes to the background on close instead of exiting.
4. Auto-start is installed through the desktop app helper and Windows startup folder.

### v1.1 Priority Tasks

1. **Web UX** — Keep the calendar compact, minimal, and easy to scan by month.
2. **Backend** — Keep attendance and announcements derived from calendar events.
3. **Deployment** — Keep MongoDB connection and web deployment straightforward, with the desktop installer maintained as a secondary option.
