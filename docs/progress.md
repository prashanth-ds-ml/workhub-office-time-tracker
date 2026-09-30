# Progress Log

| Date | Milestone | Status | Notes |
|------|-----------|--------|-------|
| 2026‑06‑19 | PRD created | ✅ | v1.0 scope defined, features listed. |
| 2026‑06‑19 | File structure set up | ✅ | Directories and initial docs added. |
| 2026‑06‑19 | PRD added | ✅ | Full PRD document committed. |
| 2026‑06‑19 | Prepare JSON data stores | ✅ | `users.json`, `sessions.json`, `breaks.json` created. |
| 2026‑06‑19 | v1.0 backend & desktop app | ✅ | FastAPI + Tkinter MVP working. |
| 2026‑06‑19 | AGENTS.md created | ✅ | OpenCode quick reference. |
| 2026‑06‑19 | BUILD_ORDER.md created | ✅ | v1.1 build instructions. |
| 2026‑06‑19 | PRD v1.1 created | ✅ | Complete v1.1 requirements with Calendar Engine. |
| 2026‑06‑19 | home.md updated | ✅ | New document structure. |
| 2026‑06‑20 | Docs refreshed | ✅ | README and command reference updated to match the desktop/background workflow. |
| 2026‑06‑24 | Web app promoted | ✅ | React app became the primary product surface; FastAPI now serves the built SPA. |
| 2026‑07‑02 | Web config parity | ✅ | React auth/admin forms now read email domain and reset timing from backend config. |
| 2026‑07‑02 | Policy persistence fixed | ✅ | Company work policy now persists correctly in MongoDB. |
| 2026‑07‑02 | Password recovery gating | ✅ | Web auth hides self-service reset when production email delivery is unavailable. |
| 2026‑07‑02 | Smoke checks repaired | ✅ | JSON and Mongo smoke scripts updated to match current web/backend behavior. |
| 2026‑07‑02 | Web session state tightened | ✅ | React auth/workspace state moved to a session-scoped storage model. |
| 2026‑07‑02 | Reports CSV export added | ✅ | Admin analytics now export a real CSV artifact from the web app. |
| 2026‑07‑03 | Beta readiness pass | ✅ | Web app audited for rollout, docs updated, and current verification rerun for employee beta. |
| 2026‑07‑03 | Recovery and date fixes | ✅ | Browser forgot-password entry restored and admin calendar dates now normalize common formats before save. |
| 2026‑09‑29 | Reports → Employee card page | ✅ | Clicking an employee in Reports now opens a dedicated card view (stats + attendance) instead of the shared Attendance page. |
| 2026‑09‑29 | UI/UX polish pass | ✅ | Focus-visible rings, button press feedback, clickable-row affordance, styled scrollbars. |
| 2026‑09‑30 | Standalone reminder app | ✅ | Self-installing `.exe` (see `docs/REMINDER_APP.md`) replaces the browser-extension reminder popup; fixed a Task Scheduler battery-power gotcha that silently blocked the sleep/wake trigger. |
| 2026‑09‑30 | Calendar-aware reminders | ✅ | Reminder app now skips holidays/Sundays and adds a half-day punch-out window, backed by new unauthenticated `GET /calendar/public/today`; deployed to production and verified live. |
| 2026‑09‑30 | Distribution folder | ✅ | All employee-facing packages (`WorkHubReminder.zip`, the browser-extension zips and source) consolidated into `distribution/`. |
