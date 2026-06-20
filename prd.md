# Office Time Tracker – Product Requirements Document (PRD)

## 1. Overview
The **Office Time Tracker** is a desktop application designed for office workers and administrators to monitor, record, and analyze working hours, breaks, and task productivity. The system provides a straightforward interface for starting/finishing work sessions, logging breaks, and creating tasks. Administrators have additional capabilities to set office rules, view aggregated reports, and enforce minimum/maximum work and break durations.

## 2. Objective
Build a robust and user‑friendly office time‑tracking system that:

* Allows users to mark the beginning and end of their work day.
* Supports break logging with configurable minimum & maximum break durations.
* Enforces configurable office hour restrictions, work hour limits, and break limits.
* Provides an admin interface to manage rules and view employee activity.
* Persists data reliably (initially using JSON files, later migrating to MongoDB).
* Offers a clean, responsive desktop UI powered by Python.

## 3. Target Audience
* **Office workers** who need to track time spent on projects and regulate breaks.
* **Team leaders / managers** who require aggregated reports of employee hours.
* **IT/Systems administrators** who must configure office rules and monitor compliance.

## 4. Stakeholders & Roles
| Role | Responsibility |
|------|----------------|
| Product Owner | Define priorities, approve features |
| Development Team | Implement features, write tests |
| QA | Verify correctness against acceptance criteria |
| End Users | Use the application and provide feedback |
| Admin | Manage rules & generate reports |

## 5. Assumptions & Constraints
* The application will run on Windows 10/11.
* Users will have network access to a local database server (MongoDB) after deployment; until then, JSON files will be used.
* All users have unique email addresses; authentication is simplified for demo purposes.
* The application is written in **Python 3.10+** and uses the following libraries:
  * **FastAPI** for the backend HTTP API.
  * **uvicorn** as the ASGI server.
  * **pydantic** for data validation.
  * **motor** for async MongoDB access.
  * **Tkinter** or a lightweight GUI framework for the desktop client.
* Security (e.g., password hashing, HTTPS) will be added in later iterations.

## 6. Success Metrics
* Users can start/work/stop sessions and log breaks with no more than 2 s latency.
* All data is persisted correctly and can be recovered after a reboot.
* Administrators can view a dashboard of total hours and breaks per user.
* No critical bugs reported in the major functionalities (time‑tracking, rule enforcement, admin tools).

## 7. Features (Sorted by Priority)
### 7.1 Core Time‑Tracking
* **Login / Session Management** – User authentication (basic email‑password). Required for all time entries.
* **Start Session** – Records `session_start` timestamp. Future extensions may handle ghost‑in/out.
* **Stop Session** – Calculates `session_end` and updates the running record.
* **Break Start / Stop** – Starts a break; ends a break; records duration.
* **Break Duration Validation** – Enforces min/max break times.
* **Work Duration Validation** – Enforces min/max work hours.

### 7.2 Administrator Tools
* **Office Hours Configuration** – `office_start` and `office_end` times.
* **Rule Settings** – Min/Max work hours and break times.
* **Dashboard** – View aggregated hours per user for a selected period.
* **User Management** – Create, edit, delete users; assign roles.

### 7.3 Task Management (Future Iteration)
* Task tracking will be introduced in a later release.

## 8. Data Model (JSON Schema Prototypes)
### User
```json
{
  "_id": "string (UUID)",
  "username": "string",
  "email": "string",
  "role": "enum(Administrator, User)",
  "office_hours": {
    "start": "ISO8601",
    "end": "ISO8601"
  },
  "rules": {
    "min_work_hours": "number",
    "max_work_hours": "number",
    "min_break_minutes": "number",
    "max_break_minutes": "number"
  }
}
```

### TimeEntry
```json
{
  "_id": "string (UUID)",
  "user_id": "string (UUID)",
  "session_start": "ISO8601",
  "session_end": "ISO8601",
  "breaks": [
    {"start": "ISO8601", "duration": "number (minutes)"}
  ]
}
```

### Task
```json
{
  "_id": "string (UUID)",
  "user_id": "string (UUID)",
  "title": "string",
  "description": "string",
  "state": "enum(todo, in_progress, completed)",
  "time_entries": ["string (UUID)"],
  "start_time": "ISO8601",
  "end_time": "ISO8601"
}
```

## 9. Acceptance Criteria
| Feature | Test Plan | Expected Result |
|---------|-----------|-----------------|
| Start Session | Call `/time_entries/start` with authenticated user | `2026‑06‑19T…` recorded as session_start, and a session record is created |
| Stop Session | Call `/time_entries/stop` after a session is started | Session record gets session_end, duration calculated |
| Enforce Break Limits | Start a break shorter than min_break_minutes | Reject with error 400, “Break too short” |
| Enforce Work Limits | Attempt to start a session exceeding max_work_hours | Reject with error 400, “Work limit exceeded” |
| Admin Dashboard | Request `/admin/dashboard` | JSON containing total hours and breaks per user |

## 10. Roadmap & Releases
| Release | Milestone |
|--------|-----------|
| **1.0** | Core time tracking + admin rule setting + dashboard |
| **1.1** | Persist data to MongoDB, add authentication, improve UI |
| **2.0** | Full task management, reporting, export features |

## 11. Appendices
### 11.1 Glossary
* **Session** – A continuous period of logged work, starting with **Start Session** and ending with **Stop Session**.
* **Break** – A sub‑interval within a session during which the user is not actively working.

### 11.2 Version History
* v0.1 – Draft created June 19, 2026.