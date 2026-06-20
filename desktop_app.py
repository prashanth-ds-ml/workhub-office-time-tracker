from __future__ import annotations

import argparse
import calendar as pycalendar
import json
import os
import socket
import sys
import threading
import time
from datetime import date, datetime, time as dtime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

try:
    import pystray  # type: ignore
    from PIL import Image, ImageDraw  # type: ignore
except Exception:  # pragma: no cover - optional tray support
    pystray = None
    Image = None
    ImageDraw = None

import uvicorn

WORKHUB_HOME = Path(os.getenv("LOCALAPPDATA", Path.home())) / "WorkHub"
CLIENT_CONFIG_FILE = WORKHUB_HOME / "client_config.json"


def _configured_api_url() -> str:
    environment_url = os.getenv("WORKHUB_API_URL")
    if environment_url:
        return environment_url.rstrip("/")
    try:
        config = json.loads(CLIENT_CONFIG_FILE.read_text(encoding="utf-8"))
        configured = str(config.get("api_url", "")).strip()
        if configured:
            return configured.rstrip("/")
    except Exception:
        pass
    return "http://127.0.0.1:8000"


DEFAULT_BASE_URL = _configured_api_url()
BASE_URL = DEFAULT_BASE_URL
STATE_FILE = WORKHUB_HOME / "desktop_state.json"
APP_DIR = Path(__file__).resolve().parent
STARTUP_BAT = Path(os.getenv("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "WorkHub Desktop.bat"

EVENT_COLORS = {
    "WORKING_DAY": "#2563eb",
    "HALF_DAY": "#d97706",
    "FULL_DAY_SATURDAY": "#0f766e",
    "HOLIDAY": "#7c3aed",
    "COMP_OFF": "#db2777",
    "LONG_WEEKEND": "#ef4444",
    "COMPANY_EVENT": "#0284c7",
}

SHORT_LABELS = {
    "WORKING_DAY": "Work",
    "HALF_DAY": "Half",
    "FULL_DAY_SATURDAY": "Sat",
    "HOLIDAY": "Off",
    "COMP_OFF": "Comp",
    "LONG_WEEKEND": "Long",
    "COMPANY_EVENT": "Event",
}


def format_minutes(minutes: float) -> str:
    total = max(0, int(round(minutes)))
    hours, mins = divmod(total, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def month_key_for(date_value: Optional[date] = None) -> str:
    date_value = date_value or date.today()
    return f"{date_value.year:04d}-{date_value.month:02d}"


def month_title(month_key: str) -> str:
    year, month = map(int, month_key.split("-"))
    return datetime(year, month, 1).strftime("%B %Y")


def parse_time(value: str) -> dtime:
    hour, minute = map(int, value.split(":"))
    return dtime(hour=hour, minute=minute)


def load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def response_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if detail:
            return str(detail)
    except Exception:
        pass
    return f"Request failed ({response.status_code})"


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def wait_for_health(base_url: str, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(f"{base_url}/health", timeout=1.0)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def find_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def ensure_backend() -> None:
    global BASE_URL

    if wait_for_health(BASE_URL, timeout=1.0):
        return

    if BASE_URL.rstrip("/") not in {"http://127.0.0.1:8000", "http://localhost:8000"}:
        raise RuntimeError(
            f"The shared WorkHub server at {BASE_URL} is unavailable. "
            "Check the company network/VPN or contact the administrator."
        )

    host = "127.0.0.1"
    port = 8000
    if not is_port_in_use(host, port):
        def run_server() -> None:
            try:
                from app import app as api_app

                config = uvicorn.Config(api_app, host=host, port=port, log_level="warning")
                server = uvicorn.Server(config)
                server.run()
            except OSError:
                # Another process may have started the API while we were launching.
                return

        threading.Thread(target=run_server, daemon=True).start()

        if wait_for_health(BASE_URL, timeout=15.0):
            return

    if wait_for_health(BASE_URL, timeout=4.0):
        return

    # If 8000 is occupied by something else, start a private API instance on a free port.
    alt_port = find_free_port(host)

    def run_alt_server() -> None:
        try:
            from app import app as api_app

            config = uvicorn.Config(api_app, host=host, port=alt_port, log_level="warning")
            server = uvicorn.Server(config)
            server.run()
        except OSError:
            return

    BASE_URL = f"http://{host}:{alt_port}"
    threading.Thread(target=run_alt_server, daemon=True).start()
    if wait_for_health(BASE_URL, timeout=15.0):
        return

    raise RuntimeError(
        f"Backend did not start on {DEFAULT_BASE_URL} or fallback {BASE_URL}. "
        "Check whether another process is using the port or the API server is stuck starting."
    )


def wake_shared_backend() -> bool:
    if BASE_URL.rstrip("/") in {"http://127.0.0.1:8000", "http://localhost:8000"}:
        return True
    if wait_for_health(BASE_URL, timeout=1.0):
        return True

    splash = tk.Tk()
    splash.title("Starting WorkHub")
    splash.resizable(False, False)
    frame = ttk.Frame(splash, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Starting WorkHub server…", font=("Segoe UI", 14, "bold")).pack(anchor="w")
    ttk.Label(
        frame,
        text="The free server may take up to 90 seconds to wake after being idle.",
        foreground="#64748b",
        wraplength=360,
        justify="left",
    ).pack(anchor="w", pady=(5, 14))
    progress = ttk.Progressbar(frame, mode="indeterminate", length=360)
    progress.pack(fill="x")
    progress.start(12)
    splash.update_idletasks()
    width, height = splash.winfo_reqwidth(), splash.winfo_reqheight()
    splash.geometry(
        f"{width}x{height}+{max(0, (splash.winfo_screenwidth() - width) // 2)}"
        f"+{max(0, (splash.winfo_screenheight() - height) // 2)}"
    )

    result = {"connected": False, "done": False}

    def wake() -> None:
        result["connected"] = wait_for_health(BASE_URL, timeout=90.0)
        result["done"] = True

    threading.Thread(target=wake, daemon=True).start()
    while not result["done"]:
        splash.update()
        time.sleep(0.05)
    progress.stop()
    splash.destroy()
    if not result["connected"]:
        messagebox.showerror(
            "WorkHub server unavailable",
            f"Could not connect to {BASE_URL} after 90 seconds.\n\n"
            "Check your internet connection or the configured server URL.",
        )
    return result["connected"]


def startup_installed() -> bool:
    return STARTUP_BAT.exists()


def install_startup() -> None:
    STARTUP_BAT.parent.mkdir(parents=True, exist_ok=True)
    if getattr(sys, "frozen", False):
        command = f'start "" "{sys.executable}"'
    else:
        command = f'start "" "{sys.executable}" "{APP_DIR / "desktop_app.py"}"'
    STARTUP_BAT.write_text(
        f"@echo off\r\n{command}\r\n",
        encoding="utf-8",
    )


def uninstall_startup() -> None:
    if STARTUP_BAT.exists():
        STARTUP_BAT.unlink()


class LoginDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.title("Welcome to WorkHub")
        self.resizable(False, False)
        self.result: Optional[Dict[str, Any]] = None
        self.configure(bg="#f8fafc")
        self.grab_set()

        frame = ttk.Frame(self, padding=24)
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frame, text="WorkHub", font=("Segoe UI", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Office calendar and time tracking", foreground="#475569").grid(
            row=1, column=0, sticky="w", pady=(2, 16)
        )

        tabs = ttk.Notebook(frame)
        tabs.grid(row=2, column=0, sticky="nsew")
        login = ttk.Frame(tabs, padding=16)
        register = ttk.Frame(tabs, padding=16)
        tabs.add(login, text="Sign in")
        tabs.add(register, text="Create account")

        # Sign in
        self.email_var = tk.StringVar()
        self.password_var = tk.StringVar()
        ttk.Label(login, text="Email").grid(row=0, column=0, sticky="w")
        self.email_entry = ttk.Entry(login, textvariable=self.email_var, width=36)
        self.email_entry.grid(row=1, column=0, sticky="ew", pady=(3, 12))
        ttk.Label(login, text="Password").grid(row=2, column=0, sticky="w")
        ttk.Entry(login, textvariable=self.password_var, width=36, show="*").grid(
            row=3, column=0, sticky="ew", pady=(3, 16)
        )
        ttk.Button(login, text="Sign in", style="Primary.TButton", command=self.submit_login).grid(
            row=4, column=0, sticky="ew"
        )
        ttk.Label(
            login,
            text="Employees and admins use the same sign-in form.",
            foreground="#64748b",
        ).grid(row=5, column=0, sticky="w", pady=(10, 0))

        # Registration
        self.register_name_var = tk.StringVar()
        self.register_email_var = tk.StringVar()
        self.register_password_var = tk.StringVar()
        self.register_confirm_var = tk.StringVar()
        self.register_setup_var = tk.StringVar()
        self.register_role_var = tk.StringVar(value="User")
        register_fields = [
            ("Full name", self.register_name_var, False),
            ("Email", self.register_email_var, False),
            ("Password", self.register_password_var, True),
            ("Confirm password", self.register_confirm_var, True),
        ]
        for row, (label, variable, hidden) in enumerate(register_fields):
            ttk.Label(register, text=label).grid(row=row * 2, column=0, sticky="w")
            ttk.Entry(register, textvariable=variable, width=36, show="*" if hidden else "").grid(
                row=row * 2 + 1, column=0, sticky="ew", pady=(3, 10)
            )
        ttk.Label(register, text="Account type").grid(row=8, column=0, sticky="w")
        role_row = ttk.Frame(register)
        role_row.grid(row=9, column=0, sticky="ew", pady=(3, 10))
        ttk.Radiobutton(
            role_row,
            text="Register as User",
            variable=self.register_role_var,
            value="User",
            command=self._toggle_admin_setup,
        ).pack(side="left")
        ttk.Radiobutton(
            role_row,
            text="Register as Admin",
            variable=self.register_role_var,
            value="Admin",
            command=self._toggle_admin_setup,
        ).pack(side="left", padx=(14, 0))

        self.setup_label = ttk.Label(register, text="Admin bootstrap key")
        self.setup_entry = ttk.Entry(register, textvariable=self.register_setup_var, width=36, show="*")
        ttk.Button(register, text="Create account", style="Primary.TButton", command=self.submit_registration).grid(
            row=12, column=0, sticky="ew", pady=(4, 0)
        )
        self.registration_note = ttk.Label(
            register,
            text="User accounts do not require the Admin bootstrap key.",
            foreground="#64748b",
            wraplength=300,
            justify="left",
        )
        self.registration_note.grid(row=13, column=0, sticky="w", pady=(10, 0))

        self.bind("<Return>", lambda _event: self.submit_login() if tabs.index(tabs.select()) == 0 else self.submit_registration())
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.after(50, self._show_front)

    def _toggle_admin_setup(self) -> None:
        if self.register_role_var.get() == "Admin":
            self.setup_label.grid(row=10, column=0, sticky="w")
            self.setup_entry.grid(row=11, column=0, sticky="ew", pady=(3, 10))
            self.registration_note.configure(text="Admin registration requires the private bootstrap key.")
        else:
            self.setup_label.grid_remove()
            self.setup_entry.grid_remove()
            self.register_setup_var.set("")
            self.registration_note.configure(text="User accounts do not require the Admin bootstrap key.")

    def _show_front(self) -> None:
        self.update_idletasks()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        screen_x = max(0, (self.winfo_screenwidth() - width) // 2)
        screen_y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{screen_x}+{screen_y}")
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(250, lambda: self.attributes("-topmost", False))
        self.email_entry.focus_force()

    def submit_login(self) -> None:
        email = self.email_var.get().strip()
        password = self.password_var.get().strip()
        if not email or not password:
            messagebox.showerror("Sign in", "Email and password are required", parent=self)
            return
        self.result = {"mode": "login", "payload": {"email": email, "password": password}}
        self.destroy()

    def submit_registration(self) -> None:
        name = self.register_name_var.get().strip()
        email = self.register_email_var.get().strip()
        password = self.register_password_var.get()
        confirm = self.register_confirm_var.get()
        if not name or not email or not password:
            messagebox.showerror("Create account", "Name, email, and password are required.", parent=self)
            return
        if "@" not in email:
            messagebox.showerror("Create account", "Enter a valid email address.", parent=self)
            return
        if len(password) < 6:
            messagebox.showerror("Create account", "Password must contain at least 6 characters.", parent=self)
            return
        if password != confirm:
            messagebox.showerror("Create account", "Passwords do not match.", parent=self)
            return
        role = self.register_role_var.get()
        setup_code = self.register_setup_var.get().strip()
        if role == "Admin" and not setup_code:
            messagebox.showerror("Create account", "Admin bootstrap key is required.", parent=self)
            return
        self.result = {
            "mode": "register",
            "payload": {
                "username": name,
                "email": email,
                "password": password,
                "role": role,
                "bootstrap_secret": setup_code or None,
            },
        }
        self.destroy()

    def cancel(self) -> None:
        self.result = None
        self.destroy()


class AnnouncementDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.title("Post announcement")
        self.resizable(False, False)
        self.result: Optional[Dict[str, str]] = None
        self.configure(bg="#f8fafc")
        self.transient(master)
        self.grab_set()

        frame = ttk.Frame(self, padding=18)
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frame, text="Team announcement", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")

        self.title_var = tk.StringVar()
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self.content = tk.Text(frame, width=42, height=6, wrap="word")

        ttk.Label(frame, text="Title").grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(frame, textvariable=self.title_var, width=42).grid(row=2, column=0, sticky="ew")
        ttk.Label(frame, text="Date").grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frame, textvariable=self.date_var, width=42).grid(row=4, column=0, sticky="ew")
        ttk.Label(frame, text="Message").grid(row=5, column=0, sticky="w", pady=(10, 0))
        self.content.grid(row=6, column=0, sticky="ew")

        button_row = ttk.Frame(frame)
        button_row.grid(row=7, column=0, sticky="e", pady=(12, 0))
        ttk.Button(button_row, text="Cancel", command=self.cancel).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(button_row, text="Post", command=self.submit).grid(row=0, column=1)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def submit(self) -> None:
        title = self.title_var.get().strip()
        content = self.content.get("1.0", "end").strip()
        effective_date = self.date_var.get().strip() or date.today().isoformat()
        if not title or not content:
            messagebox.showerror("Announcement", "Title and message are required", parent=self)
            return
        self.result = {"title": title, "content": content, "effective_date": effective_date}
        self.destroy()

    def cancel(self) -> None:
        self.result = None
        self.destroy()


class WorkHubDesktop(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("WorkHub Desktop")
        self.geometry("1280x860")
        self.minsize(1120, 760)
        self.configure(bg="#f3f4f6")
        self.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.session = requests.Session()
        self.user: Optional[Dict[str, Any]] = None
        self.access_token: Optional[str] = None
        self.overview: Optional[Dict[str, Any]] = None
        self.month_key = load_state().get("month_key") or month_key_for()
        self.current_session_id: Optional[str] = None
        self.hidden_to_tray = False
        self.manually_hidden = False
        self.tray_icon = None
        self.startup_note_var = tk.StringVar(value="")
        self.last_heartbeat_at = 0.0

        self._build_styles()
        self._build_ui()
        self._restore_user()
        self.after(100, self._tick)

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Heading.TLabel", font=("Segoe UI", 18, "bold"), background="#f3f4f6")
        style.configure("Subtle.TLabel", foreground="#64748b", background="#f3f4f6")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("CardTitle.TLabel", font=("Segoe UI", 8, "bold"), background="#ffffff", foreground="#64748b")
        style.configure("CardValue.TLabel", font=("Segoe UI", 16, "bold"), background="#ffffff", foreground="#0f172a")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"))

    def _build_ui(self) -> None:
        root = tk.Frame(self, bg="#f3f4f6")
        root.pack(fill="both", expand=True, padx=16, pady=16)

        header = tk.Frame(root, bg="#f3f4f6")
        header.pack(fill="x")
        left = tk.Frame(header, bg="#f3f4f6")
        left.pack(side="left", anchor="w")
        ttk.Label(left, text="WorkHub", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(left, text="Minimal desktop calendar and time tracker", style="Subtle.TLabel").pack(anchor="w")

        self.user_label = ttk.Label(header, text="Not signed in", style="Subtle.TLabel")
        self.user_label.pack(side="right")

        body = tk.Frame(root, bg="#f3f4f6")
        body.pack(fill="both", expand=True)

        left_body = tk.Frame(body, bg="#f3f4f6")
        left_body.pack(side="left", fill="both", expand=True, padx=(0, 12))
        right_body = tk.Frame(body, bg="#f3f4f6", width=320)
        right_body.pack(side="right", fill="y")

        toolbar = tk.Frame(left_body, bg="#f3f4f6")
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Previous", command=self.prev_month).pack(side="left")
        self.month_label = ttk.Label(toolbar, text=month_title(self.month_key), style="Heading.TLabel")
        self.month_label.pack(side="left", padx=14)
        ttk.Button(toolbar, text="Next", command=self.next_month).pack(side="left")
        ttk.Button(toolbar, text="Today", command=self.go_today).pack(side="left", padx=(12, 0))
        self.startup_note = ttk.Label(toolbar, textvariable=self.startup_note_var, style="Subtle.TLabel")
        self.startup_note.pack(side="right")

        self.status_row = tk.Frame(left_body, bg="#f3f4f6")
        self.status_row.pack(fill="x", pady=(0, 10))

        self.cards: Dict[str, Dict[str, ttk.Label]] = {}
        for title, key in [
            ("Today", "today"),
            ("Work", "work"),
            ("Break", "break"),
            ("Target", "target"),
        ]:
            card = tk.Frame(self.status_row, bg="#ffffff", bd=0, relief="flat", highlightbackground="#e2e8f0", highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w", padx=10, pady=(8, 0))
            value = ttk.Label(card, text="--", style="CardValue.TLabel")
            value.pack(anchor="w", padx=10, pady=(2, 8))
            self.cards[key] = {"value": value}

        self.calendar_outer = tk.Frame(left_body, bg="#ffffff", highlightbackground="#e2e8f0", highlightthickness=1)
        self.calendar_outer.pack(fill="both", expand=True)
        self.calendar_header = tk.Frame(self.calendar_outer, bg="#ffffff")
        self.calendar_header.pack(fill="x", padx=12, pady=(12, 8))
        self.calendar_frame = tk.Frame(self.calendar_outer, bg="#ffffff")
        self.calendar_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        legend = tk.Frame(self.calendar_outer, bg="#ffffff")
        legend.pack(fill="x", padx=12, pady=(0, 12))
        for label, color in [("Work", EVENT_COLORS["WORKING_DAY"]), ("Half", EVENT_COLORS["HALF_DAY"]), ("Holiday", EVENT_COLORS["HOLIDAY"]), ("Comp off", EVENT_COLORS["COMP_OFF"]), ("Event", EVENT_COLORS["COMPANY_EVENT"])]:
            pill = tk.Frame(legend, bg=color, padx=8, pady=2)
            pill.pack(side="left", padx=(0, 8))
            tk.Label(pill, text=label, bg=color, fg="white", font=("Segoe UI", 9, "bold")).pack()

        action_bar = tk.Frame(left_body, bg="#f3f4f6")
        action_bar.pack(fill="x", pady=(12, 0))
        self.start_work_btn = ttk.Button(action_bar, text="Start Work", style="Primary.TButton", command=self.start_work)
        self.start_break_btn = ttk.Button(action_bar, text="Start Break", command=self.start_break)
        self.stop_break_btn = ttk.Button(action_bar, text="Stop Break", command=self.stop_break)
        self.stop_work_btn = ttk.Button(action_bar, text="Stop Work", command=self.stop_work)
        for widget in [self.start_work_btn, self.start_break_btn, self.stop_break_btn, self.stop_work_btn]:
            widget.pack(side="left", padx=(0, 8))

        self.calendar_canvas = None
        self.employees_box = tk.Frame(right_body, bg="#ffffff", highlightbackground="#e2e8f0", highlightthickness=1)
        self.employees_box.pack(fill="x")
        tk.Label(self.employees_box, text="Employees", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 0))
        tk.Label(self.employees_box, text="Registered people in the app", bg="#ffffff", fg="#64748b", font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(0, 10))
        self.employees_list = tk.Frame(self.employees_box, bg="#ffffff")
        self.employees_list.pack(fill="x", padx=12, pady=(0, 12))

        self.announcements_box = tk.Frame(right_body, bg="#ffffff", highlightbackground="#e2e8f0", highlightthickness=1)
        self.announcements_box.pack(fill="x", pady=(12, 0))
        tk.Label(self.announcements_box, text="Team announcements", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 0))
        tk.Label(self.announcements_box, text="Short updates for the team", bg="#ffffff", fg="#64748b", font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(0, 10))
        self.announcements_list = tk.Frame(self.announcements_box, bg="#ffffff")
        self.announcements_list.pack(fill="x", padx=12, pady=(0, 12))

        self.upcoming_box = tk.Frame(right_body, bg="#ffffff", highlightbackground="#e2e8f0", highlightthickness=1)
        self.upcoming_box.pack(fill="x", pady=(12, 0))
        tk.Label(self.upcoming_box, text="Upcoming", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 0))
        self.upcoming_list = tk.Frame(self.upcoming_box, bg="#ffffff")
        self.upcoming_list.pack(fill="x", padx=12, pady=(0, 12))

        self.month_summary_box = tk.Frame(right_body, bg="#ffffff", highlightbackground="#e2e8f0", highlightthickness=1)
        self.month_summary_box.pack(fill="x", pady=(12, 0))
        tk.Label(self.month_summary_box, text="Month summary", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 0))
        self.month_summary_list = tk.Frame(self.month_summary_box, bg="#ffffff")
        self.month_summary_list.pack(fill="x", padx=12, pady=(0, 12))

        self.post_announcement_btn = ttk.Button(right_body, text="Post announcement", command=self.post_announcement)
        self.post_announcement_btn.pack(fill="x", pady=(12, 0))

    def _api_headers(self) -> Dict[str, str]:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        response = self.session.request(method, f"{BASE_URL}{path}", timeout=10, headers={**self._api_headers(), **kwargs.pop("headers", {})}, **kwargs)
        if response.status_code == 401 and self.user:
            self.access_token = None
            self.user = None
            self.session.headers.pop("Authorization", None)
            self.withdraw()
            self.after(100, self.login_flow)
            raise RuntimeError("Your session expired. Sign in again.")
        if not response.ok:
            raise RuntimeError(response_error_message(response))
        return response

    def _restore_user(self) -> None:
        # Authentication is always the first screen. Persisted state keeps only
        # non-sensitive preferences such as the last viewed month.
        self.withdraw()
        self.after(100, self.login_flow)

    def login_flow(self) -> None:
        dialog = LoginDialog(self)
        self.wait_window(dialog)
        if not dialog.result:
            self.destroy()
            return
        try:
            mode = dialog.result["mode"]
            payload = dialog.result["payload"]
            endpoint = "/register" if mode == "register" else "/login"
            response = self.session.post(f"{BASE_URL}{endpoint}", json=payload, timeout=10)
            if not response.ok:
                raise RuntimeError(response_error_message(response))
            auth = response.json()
            self.access_token = auth["access_token"]
            self.user = auth["user"]
            self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
            save_state({"month_key": self.month_key})
            self.user_label.configure(text=f"{self.user['username']} ({self.user['role']})")
            self.refresh_overview()
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.focus_force()
            self.after(500, lambda: self.attributes("-topmost", False))
        except Exception as exc:
            title = "Registration failed" if dialog.result["mode"] == "register" else "Login failed"
            messagebox.showerror(title, str(exc))
            self.after(100, self.login_flow)

    def refresh_overview(self) -> None:
        if not self.user:
            return
        try:
            response = self.session.get(f"{BASE_URL}/dashboard/overview", params={"month": self.month_key}, timeout=10)
            response.raise_for_status()
            self.overview = response.json()
            self.employees = []
            if self.user.get("role") == "Admin":
                employees_response = self.session.get(f"{BASE_URL}/admin/users", timeout=10)
                employees_response.raise_for_status()
                self.employees = employees_response.json()
            save_state({"month_key": self.month_key})
            self._render_all()
        except Exception as exc:
            self.startup_note_var.set(f"Backend error: {exc}")

    def _render_all(self) -> None:
        if not self.overview:
            return
        today = self.overview["today"]
        session = today.get("session")
        active_break = session.get("active_break") if session else None
        is_off = today["calendar_event"]["event_type"] in {"HOLIDAY", "COMP_OFF", "LONG_WEEKEND"}

        self.cards["today"]["value"].configure(text=today["calendar_event"]["title"])
        self.cards["work"]["value"].configure(text=format_minutes(today.get("work_done_minutes", 0)))
        self.cards["break"]["value"].configure(text=format_minutes(today.get("breaks_used_minutes", 0)))
        self.cards["target"]["value"].configure(text=format_minutes(today["policy"].get("target_work_hours", 0) * 60))

        self.month_label.configure(text=month_title(self.month_key))
        self.start_work_btn.configure(state="disabled" if session and session.get("is_active") else ("disabled" if is_off else "normal"))
        self.stop_work_btn.configure(state="normal" if session and session.get("is_active") else "disabled")
        self.start_break_btn.configure(state="normal" if session and session.get("is_active") and not active_break else "disabled")
        self.stop_break_btn.configure(state="normal" if active_break else "disabled")
        self.post_announcement_btn.configure(state="normal" if self.user and self.user.get("role") == "Admin" else "disabled")

        self._render_calendar()
        self._render_employees()
        self._render_announcements()
        self._render_upcoming()
        self._render_summary()
        self._update_timer_titles()

    def _render_employees(self) -> None:
        for child in self.employees_list.winfo_children():
            child.destroy()
        if not self.user or self.user.get("role") != "Admin":
            tk.Label(self.employees_list, text="Admin access required to view employees.", bg="#ffffff", fg="#64748b", wraplength=260, justify="left").pack(anchor="w")
            return

        employees: List[Dict[str, Any]] = getattr(self, "employees", [])
        if not employees:
            tk.Label(self.employees_list, text="No employees found.", bg="#ffffff", fg="#64748b").pack(anchor="w")
            return

        for employee in employees:
            row = tk.Frame(self.employees_list, bg="#f8fafc", highlightbackground="#e2e8f0", highlightthickness=1)
            row.pack(fill="x", pady=(0, 8))
            top = tk.Frame(row, bg="#f8fafc")
            top.pack(fill="x", padx=8, pady=(6, 0))
            tk.Label(top, text=employee.get("username", "Unknown"), bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 10, "bold")).pack(side="left")
            tk.Label(top, text=employee.get("role", "User"), bg="#f8fafc", fg="#2563eb", font=("Segoe UI", 8, "bold")).pack(side="right")
            status = employee.get("active_session")
            status_text = "Working now" if status and status.get("is_active") else "Idle"
            tk.Label(row, text=status_text, bg="#f8fafc", fg="#64748b", font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(0, 6))

    def _render_calendar(self) -> None:
        for child in self.calendar_header.winfo_children():
            child.destroy()
        for child in self.calendar_frame.winfo_children():
            child.destroy()

        tk.Label(self.calendar_header, text="Sun", bg="#ffffff", fg="#64748b", font=("Segoe UI", 8, "bold"), width=8).grid(row=0, column=0, padx=2)
        for idx, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], start=1):
            tk.Label(self.calendar_header, text=name, bg="#ffffff", fg="#64748b", font=("Segoe UI", 8, "bold"), width=8).grid(row=0, column=idx, padx=2)

        calendar_events = {item["date"]: item for item in self.overview.get("calendar_month", [])}
        year, month = map(int, self.month_key.split("-"))
        cal = pycalendar.Calendar(firstweekday=6)
        weeks = cal.monthdayscalendar(year, month)
        today_iso = date.today().isoformat()
        for row_idx, week in enumerate(weeks):
            for col_idx, day_num in enumerate(week):
                cell = tk.Frame(self.calendar_frame, bg="#ffffff", bd=0, highlightbackground="#e2e8f0", highlightthickness=1, width=94, height=68)
                cell.grid(row=row_idx, column=col_idx, padx=2, pady=2, sticky="nsew")
                cell.grid_propagate(False)
                if day_num == 0:
                    continue
                date_key = f"{year:04d}-{month:02d}-{day_num:02d}"
                event = calendar_events.get(date_key, {"event_type": "WORKING_DAY", "title": "Working Day"})
                event_type = event["event_type"]
                bg = EVENT_COLORS.get(event_type, "#e2e8f0")
                inner = tk.Frame(cell, bg=bg)
                inner.pack(fill="both", expand=True, padx=1, pady=1)
                top = tk.Frame(inner, bg=bg)
                top.pack(fill="x", padx=5, pady=(4, 0))
                tk.Label(top, text=str(day_num), bg=bg, fg="white", font=("Segoe UI", 9, "bold")).pack(side="left")
                if date_key == today_iso:
                    tk.Label(top, text="Today", bg=bg, fg="white", font=("Segoe UI", 7, "bold")).pack(side="right")
                tk.Label(inner, text=SHORT_LABELS.get(event_type, event.get("title", "Work")), bg=bg, fg="white", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=5, pady=(6, 0))
                if event.get("title") and event_type in {"HOLIDAY", "COMP_OFF", "LONG_WEEKEND", "COMPANY_EVENT"}:
                    tk.Label(inner, text=event["title"], bg=bg, fg="white", font=("Segoe UI", 7)).pack(anchor="w", padx=5, pady=(0, 0))

        for idx in range(7):
            self.calendar_frame.grid_columnconfigure(idx, weight=1, uniform="calendar")

    def _render_announcements(self) -> None:
        for child in self.announcements_list.winfo_children():
            child.destroy()
        announcements = self.overview.get("announcements", [])[:4]
        if not announcements:
            tk.Label(self.announcements_list, text="No team announcements yet.", bg="#ffffff", fg="#64748b").pack(anchor="w")
            return
        for announcement in announcements:
            item = tk.Frame(self.announcements_list, bg="#f8fafc", highlightbackground="#e2e8f0", highlightthickness=1)
            item.pack(fill="x", pady=(0, 8))
            tk.Label(item, text=announcement["title"], bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 10, "bold"), wraplength=260, justify="left").pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(item, text=announcement["content"], bg="#f8fafc", fg="#475569", font=("Segoe UI", 9), wraplength=260, justify="left").pack(anchor="w", padx=8, pady=(2, 4))
            tk.Label(item, text=announcement["created_at"][:10], bg="#f8fafc", fg="#64748b", font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(0, 6))

    def _render_upcoming(self) -> None:
        for child in self.upcoming_list.winfo_children():
            child.destroy()
        upcoming = self.overview.get("upcoming_events", {})
        entries = [
            ("Next holiday", upcoming.get("next_holiday")),
            ("Next half day", upcoming.get("next_half_day")),
            ("Next company event", upcoming.get("next_company_event")),
        ]
        for label, item in entries:
            row = tk.Frame(self.upcoming_list, bg="#ffffff")
            row.pack(fill="x", pady=(0, 8))
            tk.Label(row, text=label, bg="#ffffff", fg="#64748b", font=("Segoe UI", 8, "bold")).pack(anchor="w")
            text = item["title"] if item else "None"
            date_text = item.get("date") or item.get("event_date") if item else ""
            tk.Label(row, text=text, bg="#ffffff", fg="#0f172a", font=("Segoe UI", 10, "bold"), wraplength=260, justify="left").pack(anchor="w")
            tk.Label(row, text=date_text or "", bg="#ffffff", fg="#64748b", font=("Segoe UI", 8)).pack(anchor="w")

    def _render_summary(self) -> None:
        for child in self.month_summary_list.winfo_children():
            child.destroy()
        summary = self.overview.get("month_summary", {})
        fields = [
            ("Working days", summary.get("working_days", 0)),
            ("Completed", summary.get("completed", 0)),
            ("Remaining", summary.get("remaining", 0)),
            ("Holidays", summary.get("holidays", 0)),
            ("Comp offs", summary.get("comp_offs", 0)),
        ]
        for label, value in fields:
            row = tk.Frame(self.month_summary_list, bg="#ffffff")
            row.pack(fill="x", pady=(0, 4))
            tk.Label(row, text=label, bg="#ffffff", fg="#64748b", font=("Segoe UI", 9)).pack(side="left")
            tk.Label(row, text=str(value), bg="#ffffff", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(side="right")

    def _update_timer_titles(self) -> None:
        today = self.overview.get("today", {}) if self.overview else {}
        session = today.get("session")
        active_break = session.get("active_break") if session else None
        if not session:
            self.cards["today"]["value"].configure(text=today.get("calendar_event", {}).get("title", "Today"))
            return

        start = datetime.fromisoformat(session["start"])
        completed_break = float(session.get("break_minutes", 0))
        live_break = 0.0
        if active_break:
            live_break = max(0.0, (datetime.utcnow() - datetime.fromisoformat(active_break["start"])).total_seconds() / 60)
        work_minutes = max(0.0, (datetime.utcnow() - start).total_seconds() / 60 - completed_break - live_break)
        break_minutes = live_break
        self.cards["work"]["value"].configure(text=format_minutes(work_minutes))
        self.cards["break"]["value"].configure(text=format_minutes(break_minutes))

    def _tick(self) -> None:
        try:
            if self.user and self.overview:
                self._update_timer_titles()
            if self.user:
                self._sync_visibility_policy()
                self._heartbeat_if_due()
        finally:
            self.after(1000, self._tick)

    def _heartbeat_if_due(self) -> None:
        if not self._within_office_hours() or time.time() - self.last_heartbeat_at < 600:
            return
        self.last_heartbeat_at = time.time()

        def ping() -> None:
            try:
                requests.get(f"{BASE_URL}/health", timeout=15).raise_for_status()
            except Exception:
                pass

        threading.Thread(target=ping, daemon=True).start()

    def _sync_visibility_policy(self) -> None:
        if not self.user:
            return
        office_hours = self.user.get("office_hours") or {"start": "09:00", "end": "17:00"}
        current = datetime.now().time()
        try:
            start = parse_time(office_hours["start"])
            end = parse_time(office_hours["end"])
        except Exception:
            return
        should_show = start <= current <= end
        if should_show and self.hidden_to_tray and not self.manually_hidden:
            self.deiconify()
            self.lift()
            self.hidden_to_tray = False

    def go_today(self) -> None:
        self.month_key = month_key_for()
        self.refresh_overview()

    def prev_month(self) -> None:
        year, month = map(int, self.month_key.split("-"))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        self.month_key = f"{year:04d}-{month:02d}"
        self.refresh_overview()

    def next_month(self) -> None:
        year, month = map(int, self.month_key.split("-"))
        month += 1
        if month == 13:
            month = 1
            year += 1
        self.month_key = f"{year:04d}-{month:02d}"
        self.refresh_overview()

    def _current_session_id(self) -> Optional[str]:
        if not self.overview:
            return None
        today = self.overview.get("today", {})
        session = today.get("session")
        if session and session.get("is_active"):
            return session["id"]
        return None

    def start_work(self) -> None:
        if not self.user:
            return
        try:
            self._request("post", f"/sessions/{self.user['id']}/start")
            self.refresh_overview()
        except Exception as exc:
            messagebox.showerror("Start work", str(exc))

    def stop_work(self) -> None:
        session_id = self._current_session_id()
        if not session_id:
            return
        try:
            self._request("post", f"/sessions/{session_id}/stop")
            self.refresh_overview()
        except Exception as exc:
            messagebox.showerror("Stop work", str(exc))

    def start_break(self) -> None:
        session_id = self._current_session_id()
        if not session_id:
            return
        try:
            self._request("post", f"/sessions/{session_id}/break/start")
            self.refresh_overview()
        except Exception as exc:
            messagebox.showerror("Start break", str(exc))

    def stop_break(self) -> None:
        session_id = self._current_session_id()
        if not session_id:
            return
        try:
            self._request("post", f"/sessions/{session_id}/break/stop")
            self.refresh_overview()
        except Exception as exc:
            messagebox.showerror("Stop break", str(exc))

    def post_announcement(self) -> None:
        if not self.user or self.user.get("role") != "Admin":
            return
        dialog = AnnouncementDialog(self)
        self.wait_window(dialog)
        if not dialog.result:
            return
        try:
            self._request("post", "/announcements", json=dialog.result)
            self.refresh_overview()
        except Exception as exc:
            messagebox.showerror("Announcement", str(exc))

    def hide_window(self) -> None:
        if self._within_office_hours():
            if not messagebox.askokcancel(
                "Office hours are active",
                "WorkHub should remain running during office hours so work and break timers stay accurate.\n\n"
                "The window will be minimized to the background, not closed.",
                parent=self,
            ):
                return
        self.withdraw()
        self.hidden_to_tray = True
        self.manually_hidden = True

    def quit_app(self) -> None:
        if self._within_office_hours():
            today = self.overview.get("today", {}) if self.overview else {}
            session = today.get("session")
            active_note = "\n\nYour active work session will continue on the server." if session and session.get("is_active") else ""
            if not messagebox.askyesno(
                "Exit during office hours?",
                "You are exiting WorkHub during configured office hours. Timers and reminders will no longer be visible."
                f"{active_note}\n\nExit anyway?",
                parent=self,
            ):
                return
        self.destroy()

    def logout(self) -> None:
        self.access_token = None
        self.user = None
        self.overview = None
        self.session.headers.pop("Authorization", None)
        self.withdraw()
        self.after(100, self.login_flow)

    def _within_office_hours(self) -> bool:
        if not self.user:
            return False
        office_hours = self.user.get("office_hours") or {"start": "09:00", "end": "18:00"}
        try:
            start = parse_time(office_hours["start"])
            end = parse_time(office_hours["end"])
        except Exception:
            return False
        current = datetime.now().time()
        return start <= current <= end


def run_app() -> None:
    if not wake_shared_backend():
        return
    ensure_backend()
    from admin_panel import WorkHubAdminDesktop

    app = WorkHubAdminDesktop()
    app.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="WorkHub Desktop")
    parser.add_argument("--install-startup", action="store_true", help="Create a Windows startup entry")
    parser.add_argument("--uninstall-startup", action="store_true", help="Remove the Windows startup entry")
    args = parser.parse_args()

    if args.install_startup:
        install_startup()
        print(f"Startup entry installed: {STARTUP_BAT}")
        return
    if args.uninstall_startup:
        uninstall_startup()
        print("Startup entry removed")
        return

    run_app()


if __name__ == "__main__":
    main()
