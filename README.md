# WorkHub v1.1

WorkHub is a Python desktop office time tracker built around a Tkinter app and a local FastAPI backend.

## Project Shape

- Desktop UI: `desktop_app.py`
- Local API/backend: `app.py`
- Storage: MongoDB primary, JSON fallback for local development
- Product surface: Tkinter desktop window with tray/background support

There is no web frontend in the intended setup. The desktop app is the primary interface.

## Main Features

- Email/password login
- Start and stop work sessions
- Start and stop breaks
- Live work and break timers
- Compact month calendar with month navigation
- Calendar-driven attendance rules
- Team announcements
- Admin announcement posting
- Windows auto-start helper

## Quick Start

```bash
pip install -r requirements.txt
python desktop_app.py
```

`desktop_app.py` will connect to `http://127.0.0.1:8000` and can auto-start the local backend if it is not already running.

On a clean installation, the first registered account becomes Admin. Later
registrations become Employee accounts.

## Build a Windows package

```powershell
.\build_share_package.ps1
```

The shareable package is created at:

```text
release\WorkHub-Installer.zip
```

See `DISTRIBUTION.md` for shared-company deployment requirements.

If you want to run the API separately for debugging:

```bash
uvicorn app:app --reload
```

## Windows Auto-Start

Install:

```bash
python desktop_app.py --install-startup
```

Remove:

```bash
python desktop_app.py --uninstall-startup
```

## Notes

- MongoDB is the primary live data store.
- JSON files remain available as a local fallback.
- The desktop app minimizes to the background instead of exiting on close.
