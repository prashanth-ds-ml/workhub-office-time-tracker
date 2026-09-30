"""Background punch-in / punch-out reminder for WorkHub.

Runs quietly in the background (no browser extension needed), opens the
WorkHub site once at login, and pops up a reminder window once per day per
window, on working days only:

    punch in    10:30-11:00 IST          (working day, half day, full Saturday)
    punch out   17:30-18:00 IST          (working day, full Saturday)
    punch out   14:30-15:00 IST          (half day)

No reminders on holidays, comp-offs, long weekends or company events. The day
type comes from the WorkHub API (/calendar/public/today, no login needed), with
a built-in fallback (Sunday and 2nd/4th Saturday off, other Saturdays half day)
if the API can't be reached. Windows are evaluated in IST regardless of the
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
import urllib.request
import webbrowser
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tkinter import Button, Frame, Label, Tk, Toplevel

APP_URL = "https://workhub-office-time-tracker.vercel.app"

INDIA_TZ = timezone(timedelta(hours=5, minutes=30))

# (start_hour, start_minute, end_hour, end_minute)
PUNCH_IN_WINDOW = (10, 30, 11, 0)
PUNCH_OUT_WINDOW = (17, 30, 18, 0)
HALF_DAY_PUNCH_OUT_WINDOW = (14, 30, 15, 0)

ATTENDANCE_DAY_TYPES = {"WORKING_DAY", "HALF_DAY", "FULL_DAY_SATURDAY"}
DAY_TYPE_TIMEOUT_SECONDS = 5

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

    width, height = 380, 210
    screen_w = popup.winfo_screenwidth()
    screen_h = popup.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    popup.geometry(f"{width}x{height}+{x}+{y}")

    Label(popup, text=title, font=("Segoe UI", 12, "bold"), wraplength=340, justify="left").pack(
        padx=20, pady=(20, 8), anchor="w"
    )
    Label(popup, text=message, font=("Segoe UI", 10), wraplength=340, justify="left").pack(
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


def _fallback_day_type(day: date) -> str:
    """Mirror of app.py's synthetic calendar, used when the API is unreachable."""
    if day.weekday() == 6:
        return "HOLIDAY"
    if day.weekday() == 5:
        return "HOLIDAY" if ((day.day - 1) // 7) + 1 in {2, 4} else "HALF_DAY"
    return "WORKING_DAY"


def _fetch_day_type(day: date) -> str:
    try:
        with urllib.request.urlopen(
            f"{APP_URL}/api/calendar/public/today", timeout=DAY_TYPE_TIMEOUT_SECONDS
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("date") == day.isoformat() and data.get("event_type"):
            return data["event_type"]
    except Exception:
        pass
    return _fallback_day_type(day)


def _fmt_12h(hour: int, minute: int) -> str:
    return f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"


def _fmt_window(window: tuple[int, int, int, int]) -> str:
    return f"{_fmt_12h(window[0], window[1])} - {_fmt_12h(window[2], window[3])} IST"


def _fmt_now(now: datetime) -> str:
    """12-hour IST, plus the laptop's own local time in brackets when it differs."""
    text = f"{_fmt_12h(now.hour, now.minute)} IST"
    local = now.astimezone()
    if local.utcoffset() != now.utcoffset():
        text += f" ({_fmt_12h(local.hour, local.minute)} {local.tzname() or 'local time'})"
    return text


def due_reminders(now: datetime, day_type_for) -> list[tuple[str, str, str]]:
    """Return [(state_key, title, message)] for the windows `now` falls in.

    `day_type_for` is called lazily, only once a window matches, so the API is
    hit at most a few times a day rather than every minute."""
    in_punch_in = _in_window(now, PUNCH_IN_WINDOW)
    in_punch_out = _in_window(now, PUNCH_OUT_WINDOW)
    in_half_day_out = _in_window(now, HALF_DAY_PUNCH_OUT_WINDOW)
    if not (in_punch_in or in_punch_out or in_half_day_out):
        return []
    day_type = day_type_for(now.date())
    if day_type not in ATTENDANCE_DAY_TYPES:
        return []
    clock = _fmt_now(now)
    due = []
    if in_punch_in:
        due.append(("punch_in", "WorkHub: Time to punch in",
                    f"It's {clock}. Don't forget to punch in for the day. "
                    f"(Punch-in window: {_fmt_window(PUNCH_IN_WINDOW)})"))
    if in_punch_out and day_type != "HALF_DAY":
        due.append(("punch_out", "WorkHub: Time to punch out",
                    f"It's {clock}. Don't forget to punch out before you leave. "
                    f"(Punch-out window: {_fmt_window(PUNCH_OUT_WINDOW)})"))
    if in_half_day_out and day_type == "HALF_DAY":
        due.append(("punch_out", "WorkHub: Half day - time to punch out",
                    f"It's {clock}. Today is a half day, so don't forget to punch out before you leave. "
                    f"(Half-day punch-out window: {_fmt_window(HALF_DAY_PUNCH_OUT_WINDOW)})"))
    return due


def check_reminders(root: Tk) -> None:
    try:
        now = _ist_now()
        today_key = now.date().isoformat()
        state = _load_state()
        for key, title, message in due_reminders(now, _fetch_day_type):
            if state.get(f"{key}_notified") != today_key:
                state[f"{key}_notified"] = today_key
                _save_state(state)
                show_popup(root, title, message)
    finally:
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
        "WorkHub: Time to punch in",
        f"This is a preview. It's {_fmt_now(_ist_now())}. Don't forget to punch in for the day. "
        f"(Punch-in window: {_fmt_window(PUNCH_IN_WINDOW)})",
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


def _target_command_parts(extra_args: str = "") -> tuple[str, str]:
    """Like _target_command, but split into (command, arguments) the way a
    Task Scheduler <Exec> action wants them, rather than one shell string."""
    if getattr(sys, "frozen", False):
        exe_path = STABLE_EXE_PATH if STABLE_EXE_PATH.is_file() else Path(sys.executable)
        return str(exe_path), extra_args
    script_path = Path(__file__).resolve()
    return _pythonw_executable(), f'"{script_path}" {extra_args}'.strip()


RESUME_TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Delay>PT15S</Delay>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;{event_query}&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
    </EventTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT1M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{command}</Command>
      <Arguments>{arguments}</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def install_resume_trigger() -> None:
    # Built via a full task XML (instead of the simple `schtasks /create /sc
    # onevent ...` flags) because that simple form defaults to
    # DisallowStartIfOnBatteries/StopIfGoingOnBatteries = true, which silently
    # no-ops the task on a laptop running on battery - i.e. most of the time.
    command, arguments = _target_command_parts("--open-only")
    xml = RESUME_TASK_XML.format(event_query=RESUME_EVENT_QUERY, command=command, arguments=arguments)
    xml_path = STATE_DIR / "resume_task.xml"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    xml_path.write_text(xml, encoding="utf-16")
    result = subprocess.run(
        ["schtasks", "/create", "/tn", RESUME_TASK_NAME, "/xml", str(xml_path), "/f"],
        capture_output=True, text=True,
    )
    xml_path.unlink(missing_ok=True)
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
