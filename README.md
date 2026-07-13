# WorkHub v1.1

WorkHub is a web-first office time tracker built with React, FastAPI, and
Postgres (Vercel Postgres/Neon). The Windows desktop client remains available
as a legacy distribution option for installs that still need it.

## Project Shape

- Primary web UI: `web_app/`
- Central API/backend: `app.py`
- Production storage: Postgres (Vercel Postgres/Neon)
- Legacy Windows UI: `desktop_app.py`

## Main Features

- Email/password login
- Start and stop work sessions
- Start and stop breaks
- Live work and break timers
- Compact month calendar with month navigation
- Calendar-driven attendance rules
- Team announcements
- Admin tools for calendar, employees, policy, and analytics
- CSV export for admin reports

## Quick Start

```powershell
# Terminal 1
uvicorn app:app --reload

# Terminal 2
cd web_app
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The React app uses a single workspace bootstrap
request and cached static assets for fast repeat loads.

Registration explicitly selects Employee/User or Administrator. Administrator
registration requires the private bootstrap key. All accounts must use the
company email domain configured by the backend.

## Production build

```powershell
cd web_app
npm ci
npm run build
```

Vercel builds `web_app/dist` as a static site and deploys `api/index.py`
(which mounts `app.py`'s FastAPI app under `/api`) as a serverless function,
per `vercel.json`. See `VERCEL_DEPLOYMENT.md` for the full setup.

## Beta readiness

The web app is ready for a limited employee beta. The current release has been
verified with the frontend build and test suite plus backend smoke checks.
Treat it as a monitored beta rather than full production rollout.
Password recovery is available again in the browser login flow, and date
inputs are normalized before save in the admin calendar dialog.

## Legacy Windows package

```powershell
.\build_share_package.ps1
```

The shareable package is created at:

```text
release\WorkHub-Installer.zip
```

This installer bundles Python and all application dependencies. Employee
computers do not need Python, pip, or a separate dependency installation.

See `DISTRIBUTION.md` for shared-company deployment requirements.
See `OPERATIONS.md` for the complete live setup, maintenance, and
troubleshooting guide.

If you want to run the API separately for debugging:

```bash
uvicorn app:app --reload
```

## Legacy Windows Auto-Start

Install:

```bash
python desktop_app.py --install-startup
```

Remove:

```bash
python desktop_app.py --uninstall-startup
```

## Notes

- Postgres is the primary live data store.
- JSON files remain available as a local fallback.
- The desktop app minimizes to the background instead of exiting on close.
