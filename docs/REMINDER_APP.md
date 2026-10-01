# WorkHub Reminder App

A standalone background helper that lives outside the FastAPI/React app. It
does not talk to Postgres or run any server-side code - it's a small client
that every employee runs on their own laptop, hitting the same public API
(`https://workhub-office-time-tracker.vercel.app`) a browser would.

Source: [`scripts/reminder_daemon.py`](../scripts/reminder_daemon.py)
Build script: [`scripts/build_reminder_exe.ps1`](../scripts/build_reminder_exe.ps1)
Employee-facing readme: [`scripts/WorkHubReminder-README.txt`](../scripts/WorkHubReminder-README.txt)

## What it does

1. **Opens WorkHub in the default browser**
   - Once at Windows login (via a Startup-folder entry).
   - Once every time the laptop wakes from sleep (via a Task Scheduler task),
     since Windows Startup-folder items only fire on an actual login, not on
     resume-from-sleep.
2. **Reminder popups.** A small always-running tkinter process checks the
   time every minute (in IST, via a fixed UTC+5:30 offset - independent of the
   laptop's own timezone) and shows a popup once per day, per window, **on
   working days only**:
   - **10:30 AM-11:00 AM IST** - punch in (working day, half day, full Saturday)
   - **5:30 PM-6:00 PM IST** - punch out (working day, full Saturday)
   - **2:30 PM-3:00 PM IST** - punch out on a **half day** (replaces the evening one)

   No reminders on `HOLIDAY`, `COMP_OFF`, `LONG_WEEKEND` or `COMPANY_EVENT`.
   The day type comes from the unauthenticated endpoint
   `GET /api/calendar/public/today` (added in `app.py`; returns only date,
   event type and title). It is fetched only when the clock is inside a
   window. If the API can't be reached (offline, or not yet deployed), the
   daemon falls back to the synthetic calendar rules: Sunday and 2nd/4th
   Saturday off, other Saturdays half day - so calendar overrides made by a
   manager are only honoured while the API is reachable.

   Popups show times in 12-hour IST (plus the laptop's local time in
   brackets when its timezone isn't IST).

   By design it still does **not** check whether the employee has actually
   punched in/out (that would need the daemon to hold a login token) - the
   employee dismisses the popup on days they're already done.

## How it's packaged for distribution

Employees don't have Python installed, so the script is built into a single
`.exe` with PyInstaller (`--onefile --windowed`, no console window):

```powershell
./scripts/build_reminder_exe.ps1
```

This produces `release/WorkHubReminder.zip` (the `.exe` + a README). Copy
that into [`distribution/`](../distribution/) - the one folder that holds
everything handed to employees (this zip, plus the older browser-extension
packaging, kept for reference) - and that's the file to hand out. Employees
just double-click the `.exe` once:

- It **relocates itself** to `%LOCALAPPDATA%\WorkHub\WorkHubReminder.exe` on
  first run, so Startup/the resume task keep working even after they delete
  the file they originally downloaded (e.g. from Downloads).
- It registers its own Startup-folder launcher and Task Scheduler resume
  trigger, pointing at that relocated copy.
- It shows a one-time "WorkHub Reminder installed" popup so they know it
  worked, then opens WorkHub immediately.

No admin rights, no installer, no manual configuration. The zip also contains `Uninstall.bat` (double-click to remove everything), the setup guide, and `release/WorkHubReminder.sha256.txt` is written next to the zip so IT can allow-list the exact exe.

## Command-line flags (source or built .exe)

| Flag | Effect |
|---|---|
| *(none)* | Run the daemon: auto-install if needed, open WorkHub, start the reminder loop |
| `--install-startup` / `--uninstall-startup` | Add/remove the Windows Startup-folder launcher |
| `--install-resume-trigger` / `--uninstall-resume-trigger` | Add/remove the sleep/wake Task Scheduler task |
| `--open-only` | Open WorkHub and exit (what the resume trigger actually runs) |
| `--preview` | Show a sample reminder popup immediately, for testing |

## Known gotcha: Task Scheduler + battery power

`schtasks /create /sc onevent ...` (the simple CLI form) defaults to
`DisallowStartIfOnBatteries=true` and `StopIfGoingOnBatteries=true`. On a
laptop - which runs on battery most of the time - this silently no-ops the
resume-wake trigger: the task "runs" (no error, `Last Result` looks fine) but
the action never actually fires. Discovered 2026-09-30 when a real employee
laptop's wake trigger produced no browser tab despite the task reporting
success.

**Fix**: `install_resume_trigger()` now builds the task from a full Task
Scheduler XML definition instead of the simple flag form, explicitly setting
both battery settings to `false`, plus a 15-second `<Delay>` after the wake
event fires (so the action runs after the session has had a moment to become
interactive again, not at the exact instant of wake). If this trigger is
ever silently not firing again, check first with:

```powershell
schtasks /query /tn "WorkHub Open On Resume" /xml
```

and confirm `DisallowStartIfOnBatteries`/`StopIfGoingOnBatteries` are still
`false` - Windows can reset scheduled task settings after certain updates.

## Related, now-superseded work

An earlier approach used a Chrome/Edge browser extension
(`browser-extension/` in this repo) for the same reminder popups. That
extension's service-worker popup never reliably appeared and was never
resolved; this standalone daemon replaced it as the active mechanism. The
extension folder is left in the repo but is not the maintained path going
forward.
