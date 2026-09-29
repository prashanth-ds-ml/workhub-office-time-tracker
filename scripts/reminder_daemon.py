"""Background punch-in / punch-out reminder for WorkHub.

Runs quietly in the background (no browser extension needed), opens the
WorkHub site once at login, and pops up a reminder window during the
morning (10:45-11:00 IST) and evening (17:30-18:00 IST) windows, once per
day per window. Time windows are evaluated in IST regardless of the
machine's local timezone, matching the server (see app.py's INDIA_TZ).

A second, independent trigger opens WorkHub every time the laptop wakes from
sleep (lid close/open), regardless of punch status - registered as a
Task Scheduler task that fires on the "resumed from sleep" system event, so
it works even though Windows Startup-folder items don't re-run on resume.

Usage:
    pythonw reminder_daemon.py                    run the daemon (no console window)
                                                   - first run auto-installs the
                                                   Startup + resume-wake triggers
    python reminder_daemon.py --install-startup    add a silent launcher to Windows Startup
    python reminder_daemon.py --uninstall-startup  remove that launcher
    python reminder_daemon.py --install-resume-trigger    open WorkHub on every sleep/wake
    python reminder_daemon.py --uninstall-resume-trigger  remove that trigger
    python reminder_daemon.py --preview            show a test popup immediately and exit
    python reminder_daemon.py --open-only          open WorkHub and exit (used by the resume trigger)

When packaged with PyInstaller (see scripts/build_reminder_exe.ps1), the
built .exe IS the target - employees just download and double-click it once;
it installs itself to Startup + the resume-wake trigger, shows a one-time
confirmation, and behaves identically from then on.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import webbrowser
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tkinter import Button, Frame, Label, Tk, Toplevel

APP_URL = "https://workhub-office-time-tracker.vercel.app"

INDIA_TZ = timezone(timedelta(hours=5, minutes=30))

# (start_hour, start_minute, end_hour, end_minute)
MORNING_WINDOW = (10, 45, 11, 0)
EVENING_WINDOW = (17, 30, 18, 0)

CHECK_INTERVAL_MS = 60_000

STATE_DIR = Path(os.environ.get("APPDATA", Path.home())) / "WorkHub"
STATE_FILE = STATE_DIR / "reminder_state.json"

# Where the packaged .exe relocates itself to on first run, so Startup/resume
# triggers keep working even if the employee deletes the file they originally
# downloaded (e.g. from their Downloads folder).
STABLE_EXE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WorkHub"
STABLE_EXE_PATH = STABLE_EXE_DIR / "WorkHubReminder.exe"

STARTUP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
STARTUP_LAUNCHER = STARTUP_DIR / "WorkHub Reminder Daemon.vbs"

RESUME_TASK_NAME = "WorkHub Open On Resume"
# Fires on Event ID 1 from Power-Troubleshooter in the System log, which
# Windows logs every time the machine resumes from sleep/hibernate.
RESUME_EVENT_QUERY = "*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]"


def _ist_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(INDIA_TZ)


def _in_window(now: datetime, window: tuple[int, int, int, int]) -> bool:
    start_h, start_m, end_h, end_m = window
    minutes = now.hour * 60 + now.minute
    return start_h * 60 + start_m <= minutes < end_h * 60 + end_m


def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def _open_workhub() -> None:
    webbrowser.open(APP_URL)


def show_popup(root: Tk, title: str, message: str) -> None:
    popup = Toplevel(root)
    popup.title(title)
    popup.attributes("-topmost", True)
    popup.resizable(False, False)

    width, height = 360, 180
    screen_w = popup.winfo_screenwidth()
    screen_h = popup.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    popup.geometry(f"{width}x{height}+{x}+{y}")

    Label(popup, text=title, font=("Segoe UI", 12, "bold"), wraplength=320, justify="left").pack(
        padx=20, pady=(20, 8), anchor="w"
    )
    Label(popup, text=message, font=("Segoe UI", 10), wraplength=320, justify="left").pack(
        padx=20, pady=(0, 16), anchor="w"
    )

    button_row = Frame(popup)
    button_row.pack(padx=20, pady=(0, 16), fill="x")

    def open_and_close() -> None:
        _open_workhub()
        popup.destroy()

    Button(button_row, text="Open WorkHub", command=open_and_close).pack(side="left")
    Button(button_row, text="Dismiss", command=popup.destroy).pack(side="right")

    popup.after(15 * 60_000, lambda: popup.winfo_exists() and popup.destroy())
    popup.lift()
    popup.focus_force()


def check_reminders(root: Tk) -> None:
    now = _ist_now()
    today_key = now.date().isoformat()
    state = _load_state()

    if _in_window(now, MORNING_WINDOW) and state.get("morning_notified") != today_key:
        show_popup(
            root,
            "WorkHub: You haven't punched in",
            "It's almost 11am. Don't forget to punch in for the day.",
        )
        state["morning_notified"] = today_key
        _save_state(state)

    if _in_window(now, EVENING_WINDOW) and state.get("evening_notified") != today_key:
        show_popup(
            root,
            "WorkHub: You haven't punched out",
            "It's almost 6pm. Don't forget to punch out before you leave.",
        )
        state["evening_notified"] = today_key
        _save_state(state)

    root.after(CHECK_INTERVAL_MS, check_reminders, root)


def run_daemon() -> None:
    root = Tk()
    root.withdraw()
    if ensure_installed():
        show_popup(
            root,
            "WorkHub Reminder installed",
            "This will now start automatically whenever you log in or wake this "
            "laptop, and remind you to punch in/out. You can close this window - "
            "nothing else to do.",
        )
    _open_workhub()
    root.after(1000, check_reminders, root)
    root.mainloop()


def preview() -> None:
    root = Tk()
    root.withdraw()
    show_popup(
        root,
        "WorkHub: You haven't punched in",
        "This is a preview - it's almost 11am and you haven't started your workday yet.",
    )
    root.mainloop()


def _pythonw_executable() -> str:
    candidate = Path(sys.executable).with_name("pythonw.exe")
    if candidate.is_file():
        return str(candidate)
    return sys.executable


def _relocate_exe_if_needed() -> None:
    """Copy the running .exe to a stable AppData location on first install, so
    Startup/resume keep working even if the employee deletes the file they
    originally downloaded (e.g. from Downloads) after running it once."""
    if not getattr(sys, "frozen", False):
        return
    current = Path(sys.executable).resolve()
    if current == STABLE_EXE_PATH.resolve():
        return
    STABLE_EXE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(current, STABLE_EXE_PATH)
    except OSError:
        pass  # fall back to running from wherever it currently is


def _target_command(extra_args: str = "") -> str:
    # When packaged with PyInstaller, sys.executable IS the app itself, so it
    # runs standalone - no Python install needed on the employee's laptop.
    # When run from source, fall back to pythonw + this script's path.
    if getattr(sys, "frozen", False):
        exe_path = STABLE_EXE_PATH if STABLE_EXE_PATH.is_file() else Path(sys.executable)
        base = f'"{exe_path}"'
    else:
        base = f'"{_pythonw_executable()}" "{Path(__file__).resolve()}"'
    return f"{base} {extra_args}".strip()


def install_startup() -> None:
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    run_command = _target_command()
    vbs_literal = '"' + run_command.replace('"', '""') + '"'
    vbs_content = f'CreateObject("Wscript.Shell").Run {vbs_literal}, 0, False'
    STARTUP_LAUNCHER.write_text(vbs_content, encoding="utf-8")
    print(f"Installed startup launcher: {STARTUP_LAUNCHER}")
    print(f"It will run: {run_command}")


def uninstall_startup() -> None:
    if STARTUP_LAUNCHER.exists():
        STARTUP_LAUNCHER.unlink()
        print(f"Removed startup launcher: {STARTUP_LAUNCHER}")
    else:
        print("No startup launcher found.")


def install_resume_trigger() -> None:
    task_run = _target_command("--open-only")
    result = subprocess.run(
        [
            "schtasks", "/create", "/tn", RESUME_TASK_NAME,
            "/tr", task_run,
            "/sc", "onevent",
            "/ec", "System",
            "/mo", RESUME_EVENT_QUERY,
            "/rl", "limited",
            "/f",
        ],
        capture_output=True, text=True,
    )
    print(result.stdout.strip() or result.stderr.strip())
    if result.returncode != 0:
        print("Failed to register the resume trigger (see above).")
    else:
        print(f"WorkHub will now open every time this laptop wakes from sleep (task: {RESUME_TASK_NAME}).")


def uninstall_resume_trigger() -> None:
    result = subprocess.run(
        ["schtasks", "/delete", "/tn", RESUME_TASK_NAME, "/f"],
        capture_output=True, text=True,
    )
    print(result.stdout.strip() or result.stderr.strip())


def _is_fully_installed() -> bool:
    if not STARTUP_LAUNCHER.exists():
        return False
    result = subprocess.run(
        ["schtasks", "/query", "/tn", RESUME_TASK_NAME],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def ensure_installed() -> bool:
    """Install the startup + resume-wake triggers if missing. Returns True the
    first time it installs them, so callers can show a one-time confirmation."""
    if _is_fully_installed():
        return False
    _relocate_exe_if_needed()
    install_startup()
    install_resume_trigger()
    return True


if __name__ == "__main__":
    if "--install-startup" in sys.argv:
        install_startup()
    elif "--uninstall-startup" in sys.argv:
        uninstall_startup()
    elif "--install-resume-trigger" in sys.argv:
        install_resume_trigger()
    elif "--uninstall-resume-trigger" in sys.argv:
        uninstall_resume_trigger()
    elif "--open-only" in sys.argv:
        _open_workhub()
    elif "--preview" in sys.argv:
        preview()
    else:
        run_daemon()
