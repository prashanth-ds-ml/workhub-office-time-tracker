# Build Order – WorkHub v1.1

This project is Tkinter-first. There is no separate web frontend in scope.

## Phase 0: Setup

### 0.1 Python environment
```bash
.\create_venv.bat
```

Or manually:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 0.2 Optional MongoDB
- Start a local MongoDB service, or
- Set `MONGO_URI` for a hosted instance

## Phase 1: Verify Current Baseline

### 1.1 Desktop app
```bash
python desktop_app.py
```

Expected result:
- login window opens
- the app can auto-start the local backend if needed
- close action minimizes to tray/background when tray support is available

### 1.2 Backend API
```bash
uvicorn app:app --reload
curl http://127.0.0.1:8000/health
```

### 1.3 Storage fallback
```bash
python -c "import storage; print(storage.storage_backend())"
```

## Phase 2: Calendar Engine

### 2.1 Keep calendar events as the source of truth
- `WORKING_DAY`
- `HALF_DAY`
- `FULL_DAY_SATURDAY`
- `HOLIDAY`
- `COMP_OFF`
- `LONG_WEEKEND`
- `COMPANY_EVENT`

### 2.2 Verify policy derivation
- attendance rules should come from event type mappings
- avoid hardcoded day rules in the desktop UI
- manager changes should be visible without code edits

## Phase 3: Desktop UX

### 3.1 Keep the calendar compact
- month grid stays easy to scan
- event colors remain consistent
- today, targets, and announcements stay visible without extra navigation

### 3.2 Keep the desktop flow simple
- desktop app remains the main entry point
- backend stays local and support-only
- startup installation is handled from `desktop_app.py`

## Phase 4: Validation

### 4.1 Python smoke checks
```bash
python -m py_compile app.py storage.py desktop_app.py
python -c "import desktop_app; print('desktop import ok')"
python -c "import app; print('api import ok')"
```

### 4.2 Functional checks
- register an Administrator with the configured bootstrap key, then log in
- start and stop a work session
- start and stop a break
- browse the month calendar
- confirm announcements load

# Create default attendance policies
policies = [
    {"id": "p001", "event_type": "WORKING_DAY", "min_work_hours": 6, "target_work_hours": 6.5, "max_break_minutes": 90},
    {"id": "p002", "event_type": "HALF_DAY", "min_work_hours": 3.5, "target_work_hours": 4, "max_break_minutes": 30},
]

file = DATA_DIR / "attendance_policies.json"
file.write_text(json.dumps(policies, indent=2))

print("Migration complete!")
```

### 2.3 Verify Database Structure
```bash
python scripts/migrate_v1.0_to_v1.1.py
python -c "import json; print(json.load(open('data/calendar_events.json'))[:2])"
```

---

## Phase 3: Calendar Engine Backend (v1.1)

### 3.1 Calendar API Endpoints

**File: `app/routes/calendar.py` (NEW)**
```python
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])

@router.post("/events")
async def create_event(event: dict, current_user: User = Depends(get_current_user)):
    # Validate manager role
    # Save to calendar_events.json
    pass

@router.get("/events/{date}")
async def get_calendar_event(date: str):
    # Load calendar_events.json
    # Filter by date
    pass

@router.get("/events/types")
async def get_event_types():
    return ["WORKING_DAY", "HALF_DAY", "HOLIDAY", "COMP_OFF", "LONG_WEEKEND", "FULL_DAY_SATURDAY", "COMPANY_EVENT"]
```

### 3.2 Attendance Policy Engine

**File: `app/services/attendance_engine.py` (NEW)**
```python
from datetime import datetime, timedelta
import json
from pathlib import Path

def get_attendance_policy(event_type: str) -> dict:
    policies_file = Path("data/attendance_policies.json")
    policies = json.loads(policies_file.read_text())
    for p in policies:
        if p["event_type"] == event_type:
            return p
    raise ValueError(f"Unknown event type: {event_type}")

def calculate_work_target(date: str) -> dict:
    # Load calendar event for date
    # Get policy for event type
    # Calculate target hours, remaining time, etc.
    pass

def calculate_attendance(events: list, user_sessions: list) -> dict:
    # Process all events and sessions
    # Calculate total work, breaks, compliance
    pass
```

### 3.3 Update Existing Endpoints

**File: `app/app.py` (UPDATE)**
- Register new calendar router
- Update `/sessions` to use calendar engine for logic
- Update `/me` to include today's calendar info

### 3.4 Calendar API Tests
```bash
curl -X POST http://127.0.0.1:8000/api/v1/calendar/events -H "Content-Type: application/json" -d '{
  "event_type": "HOLIDAY",
  "date": "2026-06-27",
  "title": "Special Holiday",
  "manager_id": "admin123"
}'

curl http://127.0.0.1:8000/api/v1/calendar/events/2026-06-27
```

---

## Phase 4: Calendar UI Updates (v1.1)

### 4.1 Calendar Service (Frontend)

**File: `ui/src/services/calendar.js` (NEW)**
```javascript
import api from "./api";

export const calendarService = {
  async getEvents(date) {
    const response = await api.get(`/calendar/events/${date}`);
    return response.data;
  },
  
  async createEvent(event) {
    const response = await api.post("/calendar/events", event);
    return response.data;
  },
  
  async getAttendancePolicy(eventType) {
    const response = await api.get(`/calendar/policy/${eventType}`);
    return response.data;
  }
};
```

### 4.2 Updated Dashboard Component

**File: `ui/src/pages/Dashboard.jsx` (UPDATE)**
- Add "Today's Status" section
- Add "Today's Progress" section with work time/remaining
- Add "Monthly Summary" section
- Add "Upcoming Events" section
- Load today's calendar event on mount
- Calculate remaining work time from policy

### 4.3 New Calendar View Component

**File: `ui/src/pages/CalendarView.jsx` (NEW)**
```javascript
import { useMemo } from "react";
import { Grid, Typography, Paper, Box } from "@mui/material";
import { calendarService } from "../services/calendar";

export default function CalendarView() {
  const [year, setYear] = useState(2026);
  const [month, setMonth] = useState(5); // June
  const [events, setEvents] = useState([]);
  
  useEffect(() => {
    loadCalendarEvents();
  }, [year, month]);
  
  async function loadCalendarEvents() {
    // Load all events for the month
  }
  
  function getEventColor(eventType) {
    switch(eventType) {
      case "HOLIDAY": return "#ff5252";  // red
      case "WORKING_DAY": return "#4caf50";  // green
      case "HALF_DAY": return "#ffeb3b";  // yellow
      default: return "#9e9e9e";
    }
  }
  
  return (
    <Grid container spacing={2}>
      {renderDaysGrid()}
      {renderStatistics()}
    </Grid>
  );
}
```

### 4.4 Manager Calendar Management UI

**File: `ui/src/pages/ManagerCalendar.jsx` (NEW)**
```javascript
import { useState } from "react";
import { Button, TextField, Dialog, DialogContent, DialogActions } from "@mui/material";

export default function ManagerCalendar() {
  const [open, setOpen] = useState(false);
  const [eventType, setEventType] = useState("HOLIDAY");
  const [date, setDate] = useState("");
  const [title, setTitle] = useState("");
  
  async function handleCreateEvent() {
    await calendarService.createEvent({
      event_type: eventType,
      date: date,
      title: title
    });
    setOpen(false);
    // Reload calendar view
  }
  
  return (
    <div>
      <Button onClick={() => setOpen(true)}>+ Add Event</Button>
      <Dialog open={open}>
        <DialogContent>
          <TextField select label="Event Type" value={eventType} onChange={...}>
            <MenuItem value="HOLIDAY">Holiday</MenuItem>
            <MenuItem value="COMP_OFF">Comp Off</MenuItem>
            <MenuItem value="HALF_DAY">Half Day</MenuItem>
          </TextField>
          <TextField type="date" label="Date" value={date} onChange={...} />
          <TextField label="Title" value={title} onChange={...} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateEvent}>Create</Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}
```

---

## Phase 5: Announcement System (v1.1)

### 5.1 Announcement API

**File: `app/routes/announcements.py` (NEW)**
```python
@router.post("/announcements")
async def create_announcement(announcement: dict):
    # Generate announcement text automatically
    # Save to announcements.json
    pass

@router.get("/announcements")
async def get_announcements():
    # Return all announcements
    pass

@router.post("/announcements/{id}/read")
async def mark_announcement_read(id: str, current_user: User = Depends(get_current_user)):
    # Record user read status
    pass
```

### 5.2 Auto-Announcement Generator

**File: `app/services/auto_announcements.py` (NEW)**
```python
def generate_announcement_for_event(event: dict) -> str:
    if event["event_type"] == "HOLIDAY":
        return f"{event['title']} on {event['date']}. Attendance not required."
    elif event["event_type"] == "COMP_OFF":
        return f"Compensatory holiday declared for {event['date']}."
    elif event["event_type"] == "FULL_DAY_SATURDAY":
        return f"Saturday, {event['date']} marked as full working day."
    elif event["event_type"] == "WORKING_DAY":
        return f"Working day on {event['date']}. Target: 6h 30m."
```

### 5.3 Announcement UI

**File: `ui/src/components/AnnouncementsFeed.jsx` (NEW)**
```javascript
export default function AnnouncementsFeed() {
  const [announcements, setAnnouncements] = useState([]);
  
  useEffect(() => {
    api.get("/announcements").then(res => setAnnouncements(res.data));
  }, []);
  
  return (
    <Box>
      {announcements.map(ann => (
        <Paper sx={{ p: 2, mb: 1 }}>
          <Typography variant="h6">{ann.title}</Typography>
          <Typography>{ann.content}</Typography>
          <Typography variant="caption">{ann.created_at}</Typography>
        </Paper>
      ))}
    </Box>
  );
}
```

---

## Phase 6: Testing & Validation

### 6.1 Integration Test Suite

**File: `tests/test_v1.1_integration.py` (NEW)**
```python
import pytest
import json
from datetime import datetime, timedelta

def test_calendar_event_creation():
    response = client.post("/api/v1/calendar/events", json={
        "event_type": "HOLIDAY",
        "date": "2026-06-27",
        "title": "Test Holiday"
    })
    assert response.status_code == 200

def test_attendance_policy_loading():
    policy = attendance_engine.get_attendance_policy("WORKING_DAY")
    assert policy["min_work_hours"] == 6

def test_noon_casual_friday():
    # Test that noon on Friday counts toward target
    pass
```

### 6.2 User Acceptance Tests

**Test Scenarios:**
1. User opens app → sees today's calendar event and target hours
2. Manager creates holiday → affects all users' targets
3. User sees updated target hours on dashboard
4. User clock-out calculator shows correct estimated completion
5. Monthly summary counts working days correctly
6. Calendar view shows color-coded days

---

## Phase 7: Documentation & Deployment

### 7.1 Update API Documentation

**Endpoints to document:**
- `POST /api/v1/calendar/events` (create event)
- `GET /api/v1/calendar/events/{date}` (get day's event)
- `GET /api/v1/calendar/policy/{type}` (get attendance policy)
- `POST /announcements` (create announcement)
- `GET /announcements` (list announcements)

### 7.2 Update PRD

**PRD Updates (see `prd_v1.1.md`):**
- Add Calendar Engine module
- Add attendance policy derivation rules
- Add calendar event type definitions
- Add MVP scope changes

### 7.3 Release Notes

**File: `RELEASE_NOTES_v1.1.md` (NEW)**
```markdown
# WorkHub v1.1 Release Notes

## New Features
- Calendar Engine: Attendance rules derived from calendar events
- Manager can create holidays, comp-offs, half-days via UI
- Auto-announcement generation for calendar changes
- Enhanced dashboard with today's status and monthly summary
- Calendar view with color-coded event types

## Breaking Changes
- None

## Migration Notes
1. Run `scripts/migrate_v1.0_to_v1.1.py` to create new database tables
2. Restart backend server
3. Frontend automatically loads new data
```

---

## Build Order Summary

| Phase | Action | Duration | Priority |
|-------|--------|----------|----------|
| 0 | Setup environment | 15 min | Critical |
| 1 | Verify v1.0 baseline | 30 min | Critical |
| 2 | Create database schema | 1 hour | High |
| 3 | Calendar engine backend | 3 hours | High |
| 4 | Calendar UI updates | 4 hours | High |
| 5 | Announcement system | 2 hours | Medium |
| 6 | Testing | 2 hours | High |
| 7 | Documentation | 1 hour | Medium |

**Total Estimated Build Time: 14 hours**

---

## Rollback Plan

If v1.1 issues are discovered:
1. Stop backend server
2. Restore `data/` from backup
3. Restart with backup data

---

## Next Steps After v1.1

- V2: Leave management, WhatsApp notifications, mobile app
- V3: Payroll integration, SSO, Teams/Slack integration
