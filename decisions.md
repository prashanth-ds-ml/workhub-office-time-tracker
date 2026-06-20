# Decision Log

| Date | Decision | Rationale | Impact |
|------|----------|-----------|--------|
| 2026‑06‑19 | Choose FastAPI for backend | High performance, async, easy to test | Enables future micro‑service growth |
| 2026‑06‑19 | Target Python 3.10+ | Modern language features, ``zoneinfo`` | Requires recent Python distribution |
| 2026‑06‑19 | Use JSON files initially | Simpler testing, lower barrier to entry | Needs later migration hook |
| 2026‑06‑19 | Tkinter for UI | Built‑in, no external deps | Keep the desktop app simple and maintainable |
| 2026‑06‑19 | Calendar Engine as source of truth | Attendance rules must be manager-configurable | Removes hardcoded policies from code |
| 2026‑06‑19 | Auto-announcement generation | Managers need to know about calendar changes | Reduces manual communication overhead |
| 2026‑06-19 | Color-coded calendar view | Users need quick visual recognition | Improves usability significantly |
