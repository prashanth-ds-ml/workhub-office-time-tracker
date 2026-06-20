from __future__ import annotations

import calendar as pycalendar
import csv
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk
from typing import Any, Dict, List, Optional

from desktop_app import (
    AnnouncementDialog,
    EVENT_COLORS,
    SHORT_LABELS,
    WorkHubDesktop,
    format_minutes,
    month_key_for,
    month_title,
    save_state,
)


BG = "#f4f6f8"
SURFACE = "#ffffff"
SIDEBAR = "#0f172a"
PRIMARY = "#2563eb"
TEXT = "#0f172a"
MUTED = "#64748b"
BORDER = "#e2e8f0"
SUCCESS = "#15803d"
WARNING = "#b45309"
DANGER = "#b91c1c"


def format_duration_seconds(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class CalendarEventDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, event_date: str, event: Optional[Dict[str, Any]] = None):
        super().__init__(master)
        self.title("Calendar event")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result: Optional[Dict[str, Any]] = None
        event = event or {}

        frame = ttk.Frame(self, padding=20)
        frame.grid(sticky="nsew")
        ttk.Label(frame, text="Calendar event", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")

        self.date_var = tk.StringVar(value=event_date)
        self.type_var = tk.StringVar(value=event.get("event_type", "WORKING_DAY"))
        self.title_var = tk.StringVar(value=event.get("title", "Working Day"))
        self.description = tk.Text(frame, width=42, height=5, wrap="word")
        self.description.insert("1.0", event.get("description") or "")

        fields = [
            ("Date", ttk.Entry(frame, textvariable=self.date_var, width=30)),
            (
                "Event type",
                ttk.Combobox(
                    frame,
                    textvariable=self.type_var,
                    values=list(EVENT_COLORS),
                    state="readonly",
                    width=28,
                ),
            ),
            ("Title", ttk.Entry(frame, textvariable=self.title_var, width=30)),
        ]
        for row, (label, widget) in enumerate(fields, start=1):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=(12, 0))
            widget.grid(row=row, column=1, sticky="ew", pady=(12, 0))
        ttk.Label(frame, text="Description").grid(row=4, column=0, sticky="nw", pady=(12, 0))
        self.description.grid(row=4, column=1, sticky="ew", pady=(12, 0))

        self.policy_var = tk.StringVar(value="Attendance rules are derived from this event type.")
        ttk.Label(frame, textvariable=self.policy_var, foreground=MUTED, wraplength=290).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )
        self.type_var.trace_add("write", self._set_default_title)

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(18, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save event", style="Primary.TButton", command=self.submit).pack(side="left")

    def _set_default_title(self, *_args: Any) -> None:
        defaults = {
            "WORKING_DAY": "Working Day",
            "HALF_DAY": "Half Day",
            "FULL_DAY_SATURDAY": "Full-day Saturday",
            "HOLIDAY": "Holiday",
            "COMP_OFF": "Comp Off",
            "LONG_WEEKEND": "Long Weekend",
            "COMPANY_EVENT": "Company Event",
        }
        current = self.title_var.get().strip()
        if not current or current in defaults.values():
            self.title_var.set(defaults.get(self.type_var.get(), "Calendar Event"))

    def submit(self) -> None:
        try:
            date.fromisoformat(self.date_var.get().strip())
        except ValueError:
            messagebox.showerror("Calendar event", "Use date format YYYY-MM-DD.", parent=self)
            return
        if not self.title_var.get().strip():
            messagebox.showerror("Calendar event", "Title is required.", parent=self)
            return
        self.result = {
            "date": self.date_var.get().strip(),
            "event_type": self.type_var.get(),
            "title": self.title_var.get().strip(),
            "description": self.description.get("1.0", "end").strip() or None,
        }
        self.destroy()


class PolicyDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, employee: Dict[str, Any]):
        super().__init__(master)
        self.title("Office timing and work limits")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result: Optional[Dict[str, Any]] = None

        office = employee.get("office_hours") or {"start": "09:00", "end": "18:00"}
        rules = employee.get("rules") or {}
        frame = ttk.Frame(self, padding=20)
        frame.grid(sticky="nsew")
        ttk.Label(frame, text=employee.get("username", "Employee"), font=("Segoe UI", 15, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(frame, text="Office timing and acceptable daily limits", foreground=MUTED).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(2, 10)
        )

        self.vars = {
            "start": tk.StringVar(value=office.get("start", "09:00")),
            "end": tk.StringVar(value=office.get("end", "18:00")),
            "min_work_hours": tk.StringVar(value=str(rules.get("min_work_hours", 6))),
            "max_work_hours": tk.StringVar(value=str(rules.get("max_work_hours", 9))),
            "min_break_minutes": tk.StringVar(value=str(rules.get("min_break_minutes", 30))),
            "max_break_minutes": tk.StringVar(value=str(rules.get("max_break_minutes", 90))),
        }
        rows = [
            ("Office starts", "start", "HH:MM"),
            ("Office ends", "end", "HH:MM"),
            ("Minimum work", "min_work_hours", "hours"),
            ("Maximum work", "max_work_hours", "hours"),
            ("Minimum break", "min_break_minutes", "minutes"),
            ("Maximum break", "max_break_minutes", "minutes"),
        ]
        for row, (label, key, unit) in enumerate(rows, start=2):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=6)
            ttk.Entry(frame, textvariable=self.vars[key], width=14).grid(row=row, column=1, padx=(18, 8))
            ttk.Label(frame, text=unit, foreground=MUTED).grid(row=row, column=2, sticky="w")

        buttons = ttk.Frame(frame)
        buttons.grid(row=9, column=0, columnspan=3, sticky="e", pady=(16, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save policy", style="Primary.TButton", command=self.submit).pack(side="left")

    def submit(self) -> None:
        try:
            datetime.strptime(self.vars["start"].get(), "%H:%M")
            datetime.strptime(self.vars["end"].get(), "%H:%M")
            minimum_work = float(self.vars["min_work_hours"].get())
            maximum_work = float(self.vars["max_work_hours"].get())
            minimum_break = float(self.vars["min_break_minutes"].get())
            maximum_break = float(self.vars["max_break_minutes"].get())
        except ValueError:
            messagebox.showerror("Policy", "Enter valid HH:MM times and numeric limits.", parent=self)
            return
        if self.vars["start"].get() >= self.vars["end"].get():
            messagebox.showerror("Policy", "Office end must be after office start.", parent=self)
            return
        if minimum_work > maximum_work or minimum_break > maximum_break:
            messagebox.showerror("Policy", "Minimum values cannot exceed maximum values.", parent=self)
            return
        self.result = {
            "office_hours": {"start": self.vars["start"].get(), "end": self.vars["end"].get()},
            "rules": {
                "min_work_hours": minimum_work,
                "max_work_hours": maximum_work,
                "min_break_minutes": minimum_break,
                "max_break_minutes": maximum_break,
            },
        }
        self.destroy()


class EmployeeDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, employee: Optional[Dict[str, Any]] = None):
        super().__init__(master)
        self.employee = employee
        self.title("Edit employee" if employee else "Add employee")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result: Optional[Dict[str, Any]] = None
        employee = employee or {}

        frame = ttk.Frame(self, padding=20)
        frame.grid(sticky="nsew")
        ttk.Label(
            frame,
            text="Edit employee" if self.employee else "Add employee",
            font=("Segoe UI", 15, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            frame,
            text="The universal company work policy is assigned automatically.",
            foreground=MUTED,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 12))

        self.name_var = tk.StringVar(value=employee.get("username", ""))
        self.email_var = tk.StringVar(value=employee.get("email", ""))
        self.password_var = tk.StringVar()
        self.role_var = tk.StringVar(value=employee.get("role", "User"))
        fields = [
            ("Name", ttk.Entry(frame, textvariable=self.name_var, width=34)),
            ("Email", ttk.Entry(frame, textvariable=self.email_var, width=34)),
            (
                "Password",
                ttk.Entry(frame, textvariable=self.password_var, width=34, show="*"),
            ),
            (
                "Role",
                ttk.Combobox(frame, textvariable=self.role_var, values=["User", "Admin"], state="readonly", width=32),
            ),
        ]
        for row, (label, widget) in enumerate(fields, start=2):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=7)
            widget.grid(row=row, column=1, sticky="ew", padx=(18, 0), pady=7)
        if self.employee:
            ttk.Label(frame, text="Leave password blank to keep it unchanged.", foreground=MUTED).grid(
                row=6, column=0, columnspan=2, sticky="w", pady=(2, 0)
            )

        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, columnspan=2, sticky="e", pady=(18, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(
            buttons,
            text="Save employee" if self.employee else "Add employee",
            style="Primary.TButton",
            command=self.submit,
        ).pack(side="left")

    def submit(self) -> None:
        name = self.name_var.get().strip()
        email = self.email_var.get().strip()
        password = self.password_var.get()
        if not name or not email or (not self.employee and not password):
            messagebox.showerror("Employee", "Name, email, and password are required.", parent=self)
            return
        if "@" not in email:
            messagebox.showerror("Employee", "Enter a valid email address.", parent=self)
            return
        self.result = {
            "username": name,
            "email": email,
            "role": self.role_var.get(),
        }
        if password:
            self.result["password"] = password
        self.destroy()


class WorkHubAdminDesktop(WorkHubDesktop):
    NAV_ITEMS = [
        ("Dashboard", "dashboard"),
        ("Calendar", "calendar"),
        ("Attendance", "attendance"),
        ("Employees", "employees"),
        ("Work Policies", "policies"),
        ("Announcements", "announcements"),
        ("Reports", "reports"),
        ("Settings", "settings"),
    ]

    def __init__(self) -> None:
        self.current_page = "dashboard"
        self.selected_date = date.today().isoformat()
        self.employees: List[Dict[str, Any]] = []
        self.admin_totals: Dict[str, Any] = {}
        self.analytics: Dict[str, Any] = {}
        self.company_policy: Dict[str, Any] = {}
        super().__init__()

    def _build_styles(self) -> None:
        super()._build_styles()
        style = ttk.Style(self)
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 7))
        style.configure("Nav.TButton", font=("Segoe UI", 10), anchor="w", padding=(14, 10))
        style.configure("Treeview", rowheight=32, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_ui(self) -> None:
        self.geometry("1360x860")
        self.minsize(1120, 720)
        self.configure(bg=BG)
        self.page_title_var = tk.StringVar(value="Dashboard")
        self.connection_var = tk.StringVar(value="Connecting…")

        shell = tk.Frame(self, bg=BG)
        shell.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(shell, bg=SIDEBAR, width=205)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="WorkHub", bg=SIDEBAR, fg="white", font=("Segoe UI", 18, "bold")).pack(
            anchor="w", padx=18, pady=(20, 2)
        )
        self.console_label = tk.Label(
            self.sidebar,
            text="ADMIN CONSOLE",
            bg=SIDEBAR,
            fg="#94a3b8",
            font=("Segoe UI", 8, "bold"),
        )
        self.console_label.pack(
            anchor="w", padx=18, pady=(0, 22)
        )
        self.nav_buttons: Dict[str, tk.Button] = {}
        for label, key in self.NAV_ITEMS:
            button = tk.Button(
                self.sidebar,
                text=label,
                command=lambda page=key: self.show_page(page),
                bg=SIDEBAR,
                fg="#cbd5e1",
                activebackground="#1e293b",
                activeforeground="white",
                bd=0,
                relief="flat",
                anchor="w",
                padx=18,
                pady=10,
                font=("Segoe UI", 10),
                cursor="hand2",
            )
            button.pack(fill="x")
            self.nav_buttons[key] = button
        self.sidebar_spacer = tk.Frame(self.sidebar, bg=SIDEBAR)
        self.sidebar_spacer.pack(fill="both", expand=True)
        self.sidebar_user = tk.Label(self.sidebar, text="Not signed in", bg=SIDEBAR, fg="#cbd5e1", justify="left")
        self.sidebar_user.pack(anchor="w", padx=18, pady=(0, 16))

        content = tk.Frame(shell, bg=BG)
        content.pack(side="left", fill="both", expand=True)
        header = tk.Frame(content, bg=SURFACE, height=62, highlightbackground=BORDER, highlightthickness=1)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, textvariable=self.page_title_var, bg=SURFACE, fg=TEXT, font=("Segoe UI", 16, "bold")).pack(
            side="left", padx=22
        )
        self.user_label = tk.Label(header, text="Not signed in", bg=SURFACE, fg=TEXT, font=("Segoe UI", 9, "bold"))
        self.user_label.pack(side="right", padx=(10, 22))
        tk.Label(header, textvariable=self.connection_var, bg=SURFACE, fg=SUCCESS, font=("Segoe UI", 9)).pack(side="right")

        self.tracker = tk.Frame(content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        self.tracker.pack(fill="x", padx=18, pady=(16, 0))
        self.tracker_values: Dict[str, tk.Label] = {}
        for index, (label, key) in enumerate(
            [("TODAY", "today"), ("WORK", "work"), ("BREAK", "break"), ("STATUS", "status")]
        ):
            block = tk.Frame(self.tracker, bg=SURFACE)
            block.pack(side="left", fill="x", expand=True, padx=16, pady=12)
            tk.Label(block, text=label, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
            value = tk.Label(block, text="—", bg=SURFACE, fg=TEXT, font=("Segoe UI", 13, "bold"))
            value.pack(anchor="w", pady=(3, 0))
            self.tracker_values[key] = value
            if index < 3:
                tk.Frame(self.tracker, bg=BORDER, width=1).pack(side="left", fill="y", pady=10)

        self.tracker_actions = tk.Frame(self.tracker, bg=SURFACE)
        self.tracker_actions.pack(side="right", padx=16)
        self.start_work_btn = ttk.Button(self.tracker_actions, text="Start Work", style="Primary.TButton", command=self.start_work)
        self.start_break_btn = ttk.Button(self.tracker_actions, text="Start Break", command=self.start_break)
        self.stop_break_btn = ttk.Button(self.tracker_actions, text="End Break", style="Primary.TButton", command=self.stop_break)
        self.stop_work_btn = ttk.Button(self.tracker_actions, text="End Work", command=self.stop_work)

        self.page_host = tk.Frame(content, bg=BG)
        self.page_host.pack(fill="both", expand=True, padx=18, pady=16)
        self.startup_note_var = tk.StringVar(value="")
        self.startup_note = tk.Label(content, textvariable=self.startup_note_var, bg=BG, fg=DANGER, anchor="w")
        self.startup_note.pack(fill="x", padx=20, pady=(0, 6))
        self._highlight_nav()

    def refresh_overview(self) -> None:
        if not self.user:
            return
        try:
            self.overview = self._request("get", "/dashboard/overview", params={"month": self.month_key}).json()
            if self.user.get("role") == "Admin":
                self.employees = self._request("get", "/admin/users").json()
                self.admin_totals = self._request("get", "/admin/dashboard").json()
                self.analytics = self._request("get", "/admin/analytics", params={"month": self.month_key}).json()
                self.company_policy = self._request("get", "/company/work-policy").json()
            else:
                self.employees = []
            save_state({"month_key": self.month_key})
            self.connection_var.set("● API connected")
            self.startup_note_var.set("")
            self._render_all()
        except Exception as exc:
            self.connection_var.set("● API unavailable")
            self.startup_note_var.set(f"Could not refresh data: {exc}")

    def _render_all(self) -> None:
        if not self.overview or not self.user:
            return
        self._apply_role_access()
        self.user_label.configure(text=f"{self.user['username']}  ·  {self.user['role']}")
        self.sidebar_user.configure(text=f"{self.user['username']}\n{self.user['email']}")
        self._render_tracker()
        self.show_page(self.current_page, rebuild=True)

    def _apply_role_access(self) -> None:
        if not self.user:
            return
        is_admin = self.user.get("role") == "Admin"
        self.console_label.configure(text="ADMIN CONSOLE" if is_admin else "EMPLOYEE WORKSPACE")
        self.title("WorkHub Admin" if is_admin else "WorkHub Employee")
        allowed = (
            {key for _label, key in self.NAV_ITEMS}
            if is_admin
            else {"dashboard", "calendar", "announcements", "settings"}
        )
        for button in self.nav_buttons.values():
            button.pack_forget()
        for _label, key in self.NAV_ITEMS:
            if key in allowed:
                self.nav_buttons[key].pack(fill="x", before=self.sidebar_spacer)
        if self.current_page not in allowed:
            self.current_page = "dashboard"
        self._highlight_nav()

    def _render_tracker(self) -> None:
        today = self.overview["today"]
        session = today.get("session")
        active_break = session.get("active_break") if session else None
        work = today.get("work_done_minutes", 0)
        used_break = today.get("breaks_used_minutes", 0)
        target = today.get("policy", {}).get("target_work_hours", 0) * 60
        max_break = today.get("policy", {}).get("max_break_minutes", 0)
        self.tracker_values["today"].configure(text=today["calendar_event"]["title"])
        self.tracker_values["work"].configure(text=f"{format_minutes(work)} / {format_minutes(target)}")
        self.tracker_values["break"].configure(text=f"{format_minutes(used_break)} / {format_minutes(max_break)}")
        status = "On break" if active_break else ("Working" if session and session.get("is_active") else "Not started")
        self.tracker_values["status"].configure(text=status, fg=WARNING if active_break else (SUCCESS if session and session.get("is_active") else MUTED))

        for widget in self.tracker_actions.winfo_children():
            widget.pack_forget()
        off_day = today["calendar_event"]["event_type"] in {"HOLIDAY", "COMP_OFF", "LONG_WEEKEND"}
        if not session or not session.get("is_active"):
            if not off_day:
                self.start_work_btn.pack(side="left")
        elif active_break:
            self.stop_break_btn.pack(side="left")
        else:
            self.start_break_btn.pack(side="left", padx=(0, 8))
            self.stop_work_btn.pack(side="left")

    def _update_timer_titles(self) -> None:
        if not self.overview:
            return
        today = self.overview.get("today", {})
        session = today.get("session")
        if not session or not session.get("is_active"):
            return
        start = datetime.fromisoformat(session["start"])
        active_break = session.get("active_break")
        completed_break = float(session.get("break_minutes", 0))
        live_break = 0.0
        if active_break:
            live_break = max(0.0, (datetime.utcnow() - datetime.fromisoformat(active_break["start"])).total_seconds() / 60)
        elapsed_seconds = max(0.0, (datetime.utcnow() - start).total_seconds())
        completed_break_seconds = completed_break * 60
        live_break_seconds = live_break * 60
        work_seconds = max(0.0, elapsed_seconds - completed_break_seconds - live_break_seconds)
        break_seconds = completed_break_seconds + live_break_seconds
        target = today.get("policy", {}).get("target_work_hours", 0) * 60
        max_break = today.get("policy", {}).get("max_break_minutes", 0)
        self.tracker_values["work"].configure(
            text=f"{format_duration_seconds(work_seconds)} / {format_minutes(target)}"
        )
        self.tracker_values["break"].configure(
            text=f"{format_duration_seconds(break_seconds)} / {format_minutes(max_break)}"
        )

    def show_page(self, page: str, rebuild: bool = False) -> None:
        if not rebuild and page == self.current_page and self.page_host.winfo_children():
            return
        self.current_page = page
        labels = {key: label for label, key in self.NAV_ITEMS}
        self.page_title_var.set(labels.get(page, "Dashboard"))
        self._highlight_nav()
        for child in self.page_host.winfo_children():
            child.destroy()
        renderer = getattr(self, f"_page_{page}", self._page_dashboard)
        renderer()

    def _highlight_nav(self) -> None:
        for key, button in self.nav_buttons.items():
            selected = key == self.current_page
            button.configure(bg="#1e293b" if selected else SIDEBAR, fg="white" if selected else "#cbd5e1")

    def _card(self, parent: tk.Misc, title: str, value: str, color: str = TEXT) -> tk.Frame:
        card = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        tk.Label(card, text=title.upper(), bg=SURFACE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(
            anchor="w", padx=14, pady=(12, 2)
        )
        tk.Label(card, text=value, bg=SURFACE, fg=color, font=("Segoe UI", 20, "bold")).pack(
            anchor="w", padx=14, pady=(0, 12)
        )
        return card

    def _section(self, parent: tk.Misc, title: str, subtitle: str = "") -> tuple[tk.Frame, tk.Frame]:
        outer = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        head = tk.Frame(outer, bg=SURFACE)
        head.pack(fill="x", padx=14, pady=(12, 8))
        tk.Label(head, text=title, bg=SURFACE, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(head, text=subtitle, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")
        body = tk.Frame(outer, bg=SURFACE)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        return outer, body

    def _employee_status(self, employee: Dict[str, Any]) -> str:
        if not employee.get("is_active", True):
            return "Inactive"
        session = employee.get("active_session")
        if not session:
            return "Not in"
        if session.get("active_break"):
            return "On break"
        return "Working"

    def _page_dashboard(self) -> None:
        if self.user and self.user.get("role") != "Admin":
            self._page_employee_dashboard()
            return
        statuses = [self._employee_status(employee) for employee in self.employees]
        month_summary = self.overview.get("month_summary", {})
        cards = tk.Frame(self.page_host, bg=BG)
        cards.pack(fill="x")
        values = [
            ("Working", str(statuses.count("Working")), SUCCESS),
            ("On break", str(statuses.count("On break")), WARNING),
            ("Working days", str(month_summary.get("working_days", 0)), PRIMARY),
            ("Days remaining", str(month_summary.get("remaining_working_days", 0)), WARNING),
        ]
        for index, item in enumerate(values):
            card = self._card(cards, *item)
            card.pack(side="left", fill="x", expand=True, padx=(0, 10 if index < 3 else 0))

        columns = tk.Frame(self.page_host, bg=BG)
        columns.pack(fill="both", expand=True, pady=(12, 0))
        left = tk.Frame(columns, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        right = tk.Frame(columns, bg=BG, width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        outer, body = self._section(left, "Live attendance", "Current employee state and elapsed time")
        outer.pack(fill="both", expand=True)
        tree = ttk.Treeview(body, columns=("employee", "status", "work", "break"), show="headings")
        for key, title, width in [("employee", "Employee", 220), ("status", "Status", 110), ("work", "Work", 100), ("break", "Break", 100)]:
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="w")
        for employee in self.employees:
            session = employee.get("active_session") or {}
            tree.insert("", "end", values=(
                employee.get("username"),
                self._employee_status(employee),
                format_minutes(session.get("work_minutes", 0)),
                format_minutes(session.get("break_minutes", 0)),
            ))
        tree.pack(fill="both", expand=True)

        upcoming_outer, upcoming = self._section(right, "Upcoming")
        upcoming_outer.pack(fill="x")
        upcoming_data = self.overview.get("upcoming_events", {})
        for label, key in [("Holiday", "next_holiday"), ("Half day", "next_half_day"), ("Company event", "next_company_event")]:
            item = upcoming_data.get(key)
            text = f"{item.get('date') or item.get('event_date')}  ·  {item.get('title')}" if item else "None scheduled"
            tk.Label(upcoming, text=label.upper(), bg=SURFACE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 0))
            tk.Label(upcoming, text=text, bg=SURFACE, fg=TEXT, wraplength=260, justify="left").pack(anchor="w", pady=(1, 7))

        alerts_outer, alerts = self._section(right, "Exceptions")
        alerts_outer.pack(fill="x", pady=(12, 0))
        alert_rows = self.overview.get("alerts") or ["No attendance exceptions for your account."]
        for item in alert_rows:
            tk.Label(alerts, text=f"• {item}", bg=SURFACE, fg=DANGER if self.overview.get("alerts") else MUTED, wraplength=260, justify="left").pack(anchor="w", pady=3)

    def _page_employee_dashboard(self) -> None:
        summary = self.overview.get("month_summary", {})
        today = self.overview.get("today", {})
        cards = tk.Frame(self.page_host, bg=BG)
        cards.pack(fill="x")
        values = [
            ("Working days", str(summary.get("working_days", 0)), PRIMARY),
            ("Days elapsed", str(summary.get("elapsed_working_days", 0)), TEXT),
            ("Days remaining", str(summary.get("remaining_working_days", 0)), WARNING),
            ("Completed", str(summary.get("completed", 0)), SUCCESS),
        ]
        for index, item in enumerate(values):
            self._card(cards, *item).pack(side="left", fill="x", expand=True, padx=(0, 10 if index < 3 else 0))

        columns = tk.Frame(self.page_host, bg=BG)
        columns.pack(fill="both", expand=True, pady=(12, 0))
        left = tk.Frame(columns, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        right = tk.Frame(columns, bg=BG, width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        outer, body = self._section(left, "Today", today.get("calendar_event", {}).get("title", ""))
        outer.pack(fill="both", expand=True)
        rows = [
            ("Work completed", format_minutes(today.get("work_done_minutes", 0))),
            ("Work remaining", format_minutes(today.get("remaining_minutes", 0))),
            ("Break used", format_minutes(today.get("breaks_used_minutes", 0))),
            ("Break remaining", format_minutes(today.get("break_remaining_minutes", 0))),
            ("Estimated completion", today.get("estimated_completion") or "—"),
        ]
        for label, value in rows:
            row = tk.Frame(body, bg=SURFACE)
            row.pack(fill="x", pady=8)
            tk.Label(row, text=label, bg=SURFACE, fg=MUTED).pack(side="left")
            tk.Label(row, text=value, bg=SURFACE, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(side="right")

        upcoming_outer, upcoming = self._section(right, "Upcoming")
        upcoming_outer.pack(fill="x")
        for label, key in [("Holiday", "next_holiday"), ("Half day", "next_half_day"), ("Event", "next_company_event")]:
            item = self.overview.get("upcoming_events", {}).get(key)
            text = f"{item.get('date') or item.get('event_date')} · {item.get('title')}" if item else "None scheduled"
            tk.Label(upcoming, text=label.upper(), bg=SURFACE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 0))
            tk.Label(upcoming, text=text, bg=SURFACE, fg=TEXT, wraplength=255, justify="left").pack(anchor="w", pady=(1, 8))

    def _page_calendar(self) -> None:
        toolbar = tk.Frame(self.page_host, bg=BG)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="‹", command=self.prev_month).pack(side="left")
        self.month_label = tk.Label(toolbar, text=month_title(self.month_key), bg=BG, fg=TEXT, font=("Segoe UI", 15, "bold"))
        self.month_label.pack(side="left", padx=12)
        ttk.Button(toolbar, text="›", command=self.next_month).pack(side="left")
        ttk.Button(toolbar, text="Today", command=self.go_today).pack(side="left", padx=(10, 0))
        if self.user and self.user.get("role") == "Admin":
            ttk.Button(toolbar, text="+ Add Event", style="Primary.TButton", command=self.add_calendar_event).pack(side="right")

        split = tk.Frame(self.page_host, bg=BG)
        split.pack(fill="both", expand=True)
        calendar_box = tk.Frame(split, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        calendar_box.pack(side="left", fill="both", expand=True, padx=(0, 12))
        details = tk.Frame(split, bg=SURFACE, width=290, highlightbackground=BORDER, highlightthickness=1)
        details.pack(side="right", fill="y")
        details.pack_propagate(False)

        names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        for col, name in enumerate(names):
            tk.Label(calendar_box, text=name, bg=SURFACE, fg=MUTED, font=("Segoe UI", 8, "bold")).grid(
                row=0, column=col, sticky="ew", padx=3, pady=8
            )
            calendar_box.grid_columnconfigure(col, weight=1, uniform="day")
        events = {item["date"]: item for item in self.overview.get("calendar_month", [])}
        year, month = map(int, self.month_key.split("-"))
        weeks = pycalendar.Calendar(firstweekday=6).monthdayscalendar(year, month)
        for row, week in enumerate(weeks, start=1):
            calendar_box.grid_rowconfigure(row, weight=1)
            for col, day_num in enumerate(week):
                if not day_num:
                    tk.Frame(calendar_box, bg=SURFACE).grid(row=row, column=col, sticky="nsew", padx=3, pady=3)
                    continue
                date_key = f"{year:04d}-{month:02d}-{day_num:02d}"
                event = events.get(date_key, {"event_type": "WORKING_DAY", "title": "Working Day"})
                event_type = event["event_type"]
                selected = date_key == self.selected_date
                cell = tk.Frame(
                    calendar_box,
                    bg="#eff6ff" if selected else SURFACE,
                    highlightbackground=PRIMARY if selected else BORDER,
                    highlightthickness=2 if selected else 1,
                    cursor="hand2",
                )
                cell.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)
                day_label = tk.Label(cell, text=str(day_num), bg=cell["bg"], fg=TEXT, font=("Segoe UI", 9, "bold"))
                day_label.pack(anchor="nw", padx=7, pady=(6, 1))
                dot = tk.Frame(cell, bg=EVENT_COLORS.get(event_type, MUTED), width=8, height=8)
                dot.pack(anchor="w", padx=7, pady=(3, 2))
                event_label = tk.Label(
                    cell, text=SHORT_LABELS.get(event_type, event_type), bg=cell["bg"], fg=MUTED, font=("Segoe UI", 8)
                )
                event_label.pack(anchor="w", padx=7)
                for widget in (cell, day_label, dot, event_label):
                    widget.bind("<Button-1>", lambda _event, key=date_key: self.select_calendar_date(key))

        selected_event = events.get(self.selected_date)
        tk.Label(details, text="SELECTED DATE", bg=SURFACE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=18, pady=(18, 3))
        tk.Label(details, text=self.selected_date, bg=SURFACE, fg=TEXT, font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18)
        if selected_event:
            tk.Label(details, text=selected_event["title"], bg=SURFACE, fg=TEXT, font=("Segoe UI", 11, "bold"), wraplength=250, justify="left").pack(anchor="w", padx=18, pady=(18, 2))
            tk.Label(details, text=selected_event["event_type"].replace("_", " ").title(), bg=SURFACE, fg=EVENT_COLORS.get(selected_event["event_type"], PRIMARY)).pack(anchor="w", padx=18)
            policy = selected_event.get("policy") or {}
            tk.Label(details, text=f"Minimum work: {format_minutes(policy.get('min_work_hours', 0) * 60)}", bg=SURFACE, fg=MUTED).pack(anchor="w", padx=18, pady=(18, 2))
            tk.Label(details, text=f"Target work: {format_minutes(policy.get('target_work_hours', 0) * 60)}", bg=SURFACE, fg=MUTED).pack(anchor="w", padx=18, pady=2)
            tk.Label(details, text=f"Maximum break: {format_minutes(policy.get('max_break_minutes', 0))}", bg=SURFACE, fg=MUTED).pack(anchor="w", padx=18, pady=2)
        if self.user and self.user.get("role") == "Admin":
            ttk.Button(details, text="Edit date", command=self.edit_selected_event).pack(anchor="w", padx=18, pady=(22, 0))

    def select_calendar_date(self, date_key: str) -> None:
        self.selected_date = date_key
        self.show_page("calendar", rebuild=True)

    def add_calendar_event(self) -> None:
        dialog = CalendarEventDialog(self, self.selected_date)
        self.wait_window(dialog)
        if dialog.result:
            self._save_calendar_event(dialog.result)

    def edit_selected_event(self) -> None:
        event = next((item for item in self.overview.get("calendar_month", []) if item["date"] == self.selected_date), None)
        dialog = CalendarEventDialog(self, self.selected_date, event)
        self.wait_window(dialog)
        if dialog.result:
            self._save_calendar_event(dialog.result)

    def _save_calendar_event(self, payload: Dict[str, Any]) -> None:
        try:
            self._request("post", "/calendar/events", json=payload)
            self.month_key = payload["date"][:7]
            self.selected_date = payload["date"]
            self.refresh_overview()
        except Exception as exc:
            messagebox.showerror("Calendar event", str(exc), parent=self)

    def _page_attendance(self) -> None:
        outer, body = self._section(self.page_host, "Today's attendance", "Live status for all registered employees")
        outer.pack(fill="both", expand=True)
        tree = ttk.Treeview(body, columns=("employee", "status", "checkin", "work", "break", "limit"), show="headings")
        columns = [
            ("employee", "Employee", 200), ("status", "Status", 100), ("checkin", "Check-in", 110),
            ("work", "Work", 100), ("break", "Break", 100), ("limit", "Work limits", 180),
        ]
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        for employee in self.employees:
            session = employee.get("active_session") or {}
            start = session.get("start")
            checkin = datetime.fromisoformat(start).strftime("%H:%M") if start else "—"
            rules = employee.get("rules") or {}
            limits = f"{rules.get('min_work_hours', '—')}–{rules.get('max_work_hours', '—')}h"
            tree.insert("", "end", values=(
                employee.get("username"), self._employee_status(employee), checkin,
                format_minutes(session.get("work_minutes", 0)), format_minutes(session.get("break_minutes", 0)), limits,
            ))
        tree.pack(fill="both", expand=True)

    def _page_employees(self) -> None:
        toolbar = tk.Frame(self.page_host, bg=BG)
        toolbar.pack(fill="x", pady=(0, 10))
        self.employee_search_var = tk.StringVar()
        self.employee_role_filter = tk.StringVar(value="All roles")
        self.employee_status_filter = tk.StringVar(value="All statuses")
        ttk.Entry(toolbar, textvariable=self.employee_search_var, width=30).pack(side="left")
        ttk.Combobox(
            toolbar,
            textvariable=self.employee_role_filter,
            values=["All roles", "User", "Admin"],
            state="readonly",
            width=13,
        ).pack(side="left", padx=(8, 0))
        ttk.Combobox(
            toolbar,
            textvariable=self.employee_status_filter,
            values=["All statuses", "Working", "On break", "Not in", "Inactive"],
            state="readonly",
            width=14,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="+ Add Employee", style="Primary.TButton", command=self.add_employee).pack(side="right")

        split = tk.Frame(self.page_host, bg=BG)
        split.pack(fill="both", expand=True)
        outer, body = self._section(split, "Employees", f"{len(self.employees)} registered accounts")
        outer.pack(side="left", fill="both", expand=True, padx=(0, 12))
        detail = tk.Frame(split, bg=SURFACE, width=300, highlightbackground=BORDER, highlightthickness=1)
        detail.pack(side="right", fill="y")
        detail.pack_propagate(False)

        tree = ttk.Treeview(body, columns=("name", "role", "status", "hours"), show="headings")
        for key, label, width in [
            ("name", "Employee", 190), ("role", "Role", 85), ("status", "Today", 100), ("hours", "Office hours", 130),
        ]:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        tree.pack(fill="both", expand=True)

        def filtered_employees(*_args: Any) -> None:
            for item in tree.get_children():
                tree.delete(item)
            query = self.employee_search_var.get().strip().lower()
            role_filter = self.employee_role_filter.get()
            status_filter = self.employee_status_filter.get()
            for employee in self.employees:
                live_status = "Inactive" if not employee.get("is_active", True) else self._employee_status(employee)
                searchable = f"{employee.get('username', '')} {employee.get('email', '')}".lower()
                if query and query not in searchable:
                    continue
                if role_filter != "All roles" and employee.get("role") != role_filter:
                    continue
                if status_filter != "All statuses" and live_status != status_filter:
                    continue
                office = employee.get("office_hours") or {}
                tree.insert("", "end", iid=employee["id"], values=(
                    employee.get("username"),
                    employee.get("role"),
                    live_status,
                    f"{office.get('start', '—')}–{office.get('end', '—')}",
                ))

        def render_detail(_event: Any = None) -> None:
            for child in detail.winfo_children():
                child.destroy()
            selected = tree.selection()
            if not selected:
                tk.Label(
                    detail,
                    text="Select an employee to view account and attendance details.",
                    bg=SURFACE,
                    fg=MUTED,
                    wraplength=250,
                    justify="left",
                ).pack(anchor="w", padx=18, pady=18)
                return
            employee = next(item for item in self.employees if item["id"] == selected[0])
            active = employee.get("is_active", True)
            session = employee.get("active_session") or {}
            rules = employee.get("rules") or {}
            tk.Label(detail, text=employee.get("username"), bg=SURFACE, fg=TEXT, font=("Segoe UI", 15, "bold")).pack(
                anchor="w", padx=18, pady=(18, 2)
            )
            tk.Label(detail, text=employee.get("email"), bg=SURFACE, fg=MUTED, wraplength=250).pack(anchor="w", padx=18)
            badge_color = SUCCESS if active else DANGER
            tk.Label(
                detail,
                text=f"{employee.get('role')}  ·  {'Active' if active else 'Inactive'}",
                bg=SURFACE,
                fg=badge_color,
                font=("Segoe UI", 9, "bold"),
            ).pack(anchor="w", padx=18, pady=(8, 18))
            detail_rows = [
                ("Today", self._employee_status(employee) if active else "Inactive"),
                ("Work recorded", format_minutes(session.get("work_minutes", 0))),
                ("Break recorded", format_minutes(session.get("break_minutes", 0))),
                ("Work limits", f"{rules.get('min_work_hours', '—')}–{rules.get('max_work_hours', '—')} hours"),
                (
                    "Break limits",
                    f"{format_minutes(rules.get('min_break_minutes', 0))}–{format_minutes(rules.get('max_break_minutes', 0))}",
                ),
            ]
            for label, value in detail_rows:
                tk.Label(detail, text=label.upper(), bg=SURFACE, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(
                    anchor="w", padx=18, pady=(7, 1)
                )
                tk.Label(detail, text=value, bg=SURFACE, fg=TEXT).pack(anchor="w", padx=18)
            ttk.Button(detail, text="Edit employee", command=lambda: self.edit_employee(employee)).pack(
                fill="x", padx=18, pady=(24, 8)
            )
            if self.user and employee["id"] != self.user["id"]:
                ttk.Button(
                    detail,
                    text="Deactivate account" if active else "Activate account",
                    command=lambda: self.toggle_employee_active(employee),
                ).pack(fill="x", padx=18)

        self.employee_search_var.trace_add("write", filtered_employees)
        self.employee_role_filter.trace_add("write", filtered_employees)
        self.employee_status_filter.trace_add("write", filtered_employees)
        tree.bind("<<TreeviewSelect>>", render_detail)
        filtered_employees()
        render_detail()

    def add_employee(self) -> None:
        dialog = EmployeeDialog(self)
        self.wait_window(dialog)
        if not dialog.result:
            return
        try:
            self._request("post", "/admin/users", json=dialog.result)
            self.refresh_overview()
        except Exception as exc:
            messagebox.showerror("Add employee", str(exc), parent=self)

    def edit_employee(self, employee: Dict[str, Any]) -> None:
        dialog = EmployeeDialog(self, employee)
        self.wait_window(dialog)
        if not dialog.result:
            return
        try:
            updated = self._request("patch", f"/admin/users/{employee['id']}", json=dialog.result).json()
            if self.user and employee["id"] == self.user["id"]:
                self.user.update(updated)
            self.refresh_overview()
        except Exception as exc:
            messagebox.showerror("Edit employee", str(exc), parent=self)

    def toggle_employee_active(self, employee: Dict[str, Any]) -> None:
        new_state = not employee.get("is_active", True)
        action = "activate" if new_state else "deactivate"
        if not messagebox.askyesno(
            f"{action.title()} employee",
            f"Are you sure you want to {action} {employee.get('username')}?",
            parent=self,
        ):
            return
        try:
            self._request("patch", f"/admin/users/{employee['id']}", json={"is_active": new_state})
            self.refresh_overview()
        except Exception as exc:
            messagebox.showerror("Employee account", str(exc), parent=self)

    def _page_policies(self) -> None:
        heading = tk.Frame(self.page_host, bg=BG)
        heading.pack(fill="x", pady=(0, 10))
        tk.Label(
            heading,
            text="One office schedule and one set of acceptable limits applies to every employee.",
            bg=BG,
            fg=MUTED,
        ).pack(side="left")
        ttk.Button(heading, text="Edit company policy", style="Primary.TButton", command=self.edit_company_policy).pack(side="right")

        office = self.company_policy.get("office_hours") or {"start": "Not set", "end": "Not set"}
        rules = self.company_policy.get("rules") or {}
        card = tk.Frame(self.page_host, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x")
        tk.Label(card, text="COMPANY DEFAULT", bg=SURFACE, fg=PRIMARY, font=("Segoe UI", 8, "bold")).pack(
            anchor="w", padx=18, pady=(18, 3)
        )
        tk.Label(card, text="Universal Work Policy", bg=SURFACE, fg=TEXT, font=("Segoe UI", 15, "bold")).pack(
            anchor="w", padx=18
        )
        details = [
            ("Applies to", f"All {len(self.employees)} registered employees"),
            ("Office timing", f"{office.get('start')} – {office.get('end')}"),
            ("Acceptable work time", f"{rules.get('min_work_hours', '—')} – {rules.get('max_work_hours', '—')} hours"),
            (
                "Acceptable break time",
                f"{format_minutes(rules.get('min_break_minutes', 0))} – {format_minutes(rules.get('max_break_minutes', 0))}",
            ),
        ]
        for label, value in details:
            row = tk.Frame(card, bg=SURFACE)
            row.pack(fill="x", padx=18, pady=8)
            tk.Label(row, text=label, bg=SURFACE, fg=MUTED, width=24, anchor="w").pack(side="left")
            tk.Label(row, text=value, bg=SURFACE, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(
            card,
            text="Calendar events can still override attendance targets for half-days, holidays, and special working days.",
            bg=SURFACE,
            fg=MUTED,
            wraplength=850,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(12, 18))

    def edit_company_policy(self) -> None:
        policy = {
            "username": "Universal Work Policy",
            "office_hours": self.company_policy.get("office_hours"),
            "rules": self.company_policy.get("rules"),
        }
        dialog = PolicyDialog(self, policy)
        self.wait_window(dialog)
        if not dialog.result:
            return
        try:
            self._request("post", "/company/work-policy", json=dialog.result)
            self.company_policy = dialog.result
            if self.user:
                self.user.update(dialog.result)
            self.refresh_overview()
        except Exception as exc:
            messagebox.showerror("Work policy", str(exc), parent=self)

    def _page_announcements(self) -> None:
        toolbar = tk.Frame(self.page_host, bg=BG)
        toolbar.pack(fill="x", pady=(0, 10))
        tk.Label(toolbar, text="Updates sent to the full team", bg=BG, fg=MUTED).pack(side="left")
        if self.user and self.user.get("role") == "Admin":
            ttk.Button(toolbar, text="+ New announcement", style="Primary.TButton", command=self.post_announcement).pack(side="right")
        announcements = self.overview.get("announcements", [])
        if not announcements:
            self._card(self.page_host, "Announcements", "No announcements yet").pack(fill="x")
        for item in announcements:
            card = tk.Frame(self.page_host, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill="x", pady=(0, 8))
            tk.Label(card, text=item["title"], bg=SURFACE, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 2))
            tk.Label(card, text=item["content"], bg=SURFACE, fg=MUTED, wraplength=900, justify="left").pack(anchor="w", padx=14)
            tk.Label(card, text=f"Effective {item['effective_date']}  ·  Created {item['created_at'][:10]}", bg=SURFACE, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(5, 12))

    def _page_reports(self) -> None:
        toolbar = tk.Frame(self.page_host, bg=BG)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="‹", command=self.prev_month).pack(side="left")
        tk.Label(
            toolbar,
            text=month_title(self.month_key),
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 15, "bold"),
        ).pack(side="left", padx=12)
        ttk.Button(toolbar, text="›", command=self.next_month).pack(side="left")
        ttk.Button(toolbar, text="Current month", command=self.go_today).pack(side="left", padx=(10, 0))
        tk.Label(
            toolbar,
            text="Analytics and exports use the selected month",
            bg=BG,
            fg=MUTED,
        ).pack(side="right")

        summary = self.analytics.get("summary", {})
        cards = tk.Frame(self.page_host, bg=BG)
        cards.pack(fill="x")
        for index, item in enumerate([
            ("Active employees", str(summary.get("active_employees", 0)), PRIMARY),
            ("Avg work / day", format_minutes(summary.get("average_work_minutes", 0)), SUCCESS),
            ("Avg break / day", format_minutes(summary.get("average_break_minutes", 0)), WARNING),
            ("Team work total", format_minutes(summary.get("total_work_minutes", 0)), TEXT),
        ]):
            card = self._card(cards, *item)
            card.pack(side="left", fill="x", expand=True, padx=(0, 10 if index < 3 else 0))
        outer, body = self._section(
            self.page_host,
            f"Employee analytics · {month_title(self.month_key)}",
            "Averages are calculated across days where the employee recorded work.",
        )
        outer.pack(fill="both", expand=True, pady=(12, 0))
        tree = ttk.Treeview(
            body,
            columns=("employee", "days", "avg_work", "avg_break", "total_work", "total_break", "completion"),
            show="headings",
        )
        report_columns = [
            ("employee", "Employee", 160),
            ("days", "Days worked", 90),
            ("avg_work", "Avg work/day", 110),
            ("avg_break", "Avg break/day", 110),
            ("total_work", "Total work", 100),
            ("total_break", "Total break", 100),
            ("completion", "Target completion", 120),
        ]
        for key, label, width in report_columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        for employee in self.analytics.get("employees", []):
            tree.insert("", "end", values=(
                employee.get("username"),
                employee.get("days_worked", 0),
                format_minutes(employee.get("average_work_minutes", 0)),
                format_minutes(employee.get("average_break_minutes", 0)),
                format_minutes(employee.get("total_work_minutes", 0)),
                format_minutes(employee.get("total_break_minutes", 0)),
                f"{employee.get('completion_rate', 0):.1f}%",
            ))
        tree.pack(fill="both", expand=True)
        ttk.Button(body, text="Export CSV", command=self.export_report).pack(anchor="e", pady=(10, 0))

    def export_report(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export report",
            initialfile=f"workhub-analytics-{self.month_key}.csv",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        with Path(path).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Month", self.month_key])
            writer.writerow(["Working days", self.analytics.get("working_days", 0)])
            writer.writerow([])
            writer.writerow([
                "Employee", "Role", "Days worked", "Completed days", "Average work minutes",
                "Average break minutes", "Total work minutes", "Total break minutes", "Completion rate",
            ])
            for employee in self.analytics.get("employees", []):
                writer.writerow([
                    employee.get("username"),
                    employee.get("role"),
                    employee.get("days_worked"),
                    employee.get("completed_days"),
                    employee.get("average_work_minutes"),
                    employee.get("average_break_minutes"),
                    employee.get("total_work_minutes"),
                    employee.get("total_break_minutes"),
                    employee.get("completion_rate"),
                ])
        messagebox.showinfo("Reports", "Report exported.", parent=self)

    def _page_settings(self) -> None:
        outer, body = self._section(self.page_host, "Desktop settings", "System behavior and connection information")
        outer.pack(fill="x")
        rows = [
            ("API endpoint", "Connected to the configured WorkHub backend"),
            ("Close button", "Minimizes WorkHub to the background"),
            ("Office-hours visibility", "Restores the window during the signed-in user's office hours"),
            ("Startup", "Use --install-startup to launch WorkHub with Windows"),
        ]
        for label, value in rows:
            row = tk.Frame(body, bg=SURFACE)
            row.pack(fill="x", pady=7)
            tk.Label(row, text=label, bg=SURFACE, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(side="left")
            tk.Label(row, text=value, bg=SURFACE, fg=MUTED).pack(side="right")
        actions = tk.Frame(body, bg=SURFACE)
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="Sign out", command=self.logout).pack(side="right", padx=(8, 0))
        ttk.Button(actions, text="Exit WorkHub", command=self.quit_app).pack(side="right")
