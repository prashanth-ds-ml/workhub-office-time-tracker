# Attendance Policy Configuration – WorkHub v1.1

## Overview

Attendance policies define the work requirements for each calendar event type. These policies are derived from the `calendar_events` table, not hardcoded in the application.

## Default Policies

| Event Type | Min Hours | Target Hours | Max Break | Notes |
|------------|-----------|--------------|-----------|-------|
| WORKING_DAY | 6 | 6.5 | 90 min | Normal weekday |
| HALF_DAY | 3.5 | 4 | 30 min | Odd Saturdays |
| FULL_DAY_SATURDAY | 6 | 6.5 | 90 min | Manager override of half-day |
| HOLIDAY | 0 | 0 | 0 | No attendance required |
| COMP_OFF | 0 | 0 | 0 | Compensatory leave |
| LONG_WEEKEND | 0 | 0 | 0 | Extended leave period |
| COMPANY_EVENT | 0 | 0 | 0 | Events (meetings, outings) |

## Policy Structure

```json
{
  "id": "string (UUID)",
  "event_type": "enum(WORKING_DAY, HALF_DAY, FULL_DAY_SATURDAY, HOLIDAY, COMP_OFF, LONG_WEEKEND, COMPANY_EVENT)",
  "min_work_hours": "number (minimum required, e.g., 6 for WORKING_DAY)",
  "target_work_hours": "number (target goal, e.g., 6.5 for WORKING_DAY)",
  "max_break_minutes": "number (maximum break time, e.g., 90)",
  "created_at": "ISO8601"
}
```

## How Policies Drive Attendance

### 1. Calendar Event → Policy Lookup

When an employee opens the dashboard, the system:

1. Gets today's calendar event (e.g., `WORKING_DAY`)
2. Loads the corresponding policy (e.g., 6h min, 6.5h target, 90m max break)
3. Calculates current work duration
4. Shows remaining time and estimated completion

### 2. Calculation Formula

```python
target_hours = policy.target_work_hours
work_done = calculate_work_duration()
break_minutes = calculate_break_duration()

remaining_hours = target_hours - work_done
estimated_completion = current_time + remaining_hours

if estimated_completion > office_end_time:
    alert = "Warning: Will exceed office hours"
```

### 3. Example: Working Day

**Calendar Event:**
```json
{
  "event_type": "WORKING_DAY",
  "date": "2026-06-19",
  "title": "Normal Working Day"
}
```

**Policy:**
```json
{
  "min_work_hours": 6,
  "target_work_hours": 6.5,
  "max_break_minutes": 90
}
```

**Dashboard Display:**
```
Today: WORKING_DAY
Target: 6h 30m
Work Done: 4h 25m
Remaining: 2h 05m
Break Used: 35m
Break Remaining: 55m
Estimated Completion: 04:42 PM
```

### 4. Example: Half Day

**Calendar Event:**
```json
{
  "event_type": "HALF_DAY",
  "date": "2026-06-21",
  "title": "Half Day Saturday"
}
```

**Policy:**
```json
{
  "min_work_hours": 3.5,
  "target_work_hours": 4,
  "max_break_minutes": 30
}
```

**Dashboard Display:**
```
Today: HALF_DAY
Target: 4h
Work Done: 3h 20m
Remaining: 0h 40m
Break Used: 15m
Break Remaining: 15m
Estimated Completion: 01:30 PM
```

### 5. Example: Holiday

**Calendar Event:**
```json
{
  "event_type": "HOLIDAY",
  "date": "2026-06-27",
  "title": "Special Holiday"
}
```

**Policy:**
```json
{
  "min_work_hours": 0,
  "target_work_hours": 0,
  "max_break_minutes": 0
}
```

**Dashboard Display:**
```
Today: HOLIDAY
Attendance not required
```

## Customizing Policies

### Via Code (Not Recommended)

Edit `data/attendance_policies.json`:

```json
{
  "id": "p001",
  "event_type": "WORKING_DAY",
  "min_work_hours": 7,  // Changed from 6 to 7
  "target_work_hours": 7.5,  // Changed from 6.5 to 7.5
  "max_break_minutes": 100,  // Changed from 90 to 100
  "created_at": "2026-06-19T10:00:00"
}
```

**Restart backend for changes to take effect.**

### Via API (Recommended)

 Managers should use the calendar UI to modify calendar events, which automatically uses the correct policy.

## Policy Types and Their Implications

| Policy Type | Work Required | Break Allowed | Notes |
|-------------|---------------|---------------|-------|
| WORKING_DAY | Yes (6-6.5h) | Yes (max 90m) | Normal Monday-Friday |
| HALF_DAY | Reduced (3.5-4h) | Reduced (max 30m) | Saturdays typically |
| FULL_DAY_SATURDAY | Yes (6-6.5h) | Yes (max 90m) | Manager override Saturday |
| HOLIDAY | No | No | No attendance |
| COMP_OFF | No | No | Make-up for worked day |
| LONG_WEEKEND | No | No | Extended leave |
| COMPANY_EVENT | Variable | Variable | Often optional |

## Manager Configuration

### Creating a Calendar Event

```json
POST /api/v1/calendar/events
{
  "event_type": "HOLIDAY",
  "date": "2026-07-01",
  "title": "Special Holiday",
  "description": "Company closing for event",
  "manager_id": "admin123"
}
```

The system automatically applies the policy for `HOLIDAY` (no work required).

### Modifying Policy

Managers should not modify policies directly. Instead, create a custom calendar event with desired behavior.

### Creating Custom Policy (Admin Only)

If a unique scenario requires different rules:

1. Create new calendar event type (e.g., `WORKSHOP_DAY`)
2. Create corresponding policy
3. Update attendance engine to handle new type

```json
POST /api/v1/calendar/policies
{
  "event_type": "WORKSHOP_DAY",
  "min_work_hours": 5,
  "target_work_hours": 6,
  "max_break_minutes": 60
}
```

## Attendance Calculations

### Work Duration Calculation

```python
def calculate_work_duration(session_start, session_end, breaks):
    total_session = session_end - session_start
    total_break = sum(break_duration for break_duration in breaks)
    return total_session - total_break
```

### Compliance Check

```python
def check_compliance(work_duration, policy):
    if work_duration < policy.min_work_hours:
        return " warning", f"Work duration ({work_duration:.1f}h) below minimum ({policy.min_work_hours}h)"
    elif work_duration >= policy.target_work_hours:
        return "达标", "Work target reached"
    else:
        return "in_progress", f"Working towards target ({policy.target_work_hours}h)"
```

### Attendance Reporting

```python
def calculate_monthly_attendance(events, sessions, policy):
    # Group by calendar event type
    working_days = [e for e in events if e.event_type == "WORKING_DAY"]
    half_days = [e for e in events if e.event_type == "HALF_DAY"]
    holidays = [e for e in events if e.event_type == "HOLIDAY"]
    
    # Sum work durations
    total_work = sum(calculate_work_duration(s) for s in sessions)
    total_breaks = sum(calculate_break_duration(s) for s in sessions)
    
    return {
        "working_days": len(working_days),
        "half_days": len(half_days),
        "holidays": len(holidays),
        "total_work_hours": total_work,
        "total_break_minutes": total_breaks,
        "compliance_rate": calculate_compliance_rate(working_days, total_work, policy)
    }
```

## Auto-Announcements

When a manager creates/modifies a calendar event:

```python
def generate_announcement(event):
    if event.event_type == "HOLIDAY":
        return f"{event.title} on {event.date}. Attendance not required."
    elif event.event_type == "COMP_OFF":
        return f"Compensatory holiday declared for {event.date}."
    elif event.event_type == "FULL_DAY_SATURDAY":
        return f"Saturday, {event.date} marked as full working day."
    else:
        return f"{event.title} on {event.date}."
```

## Testing Policies

### Test Case 1: Normal Working Day

**Input:** `WORKING_DAY` event, `4h` work done, `30m` break  
**Expected:** 
- Remaining: `2h 30m`
- Break remaining: `60m`
- Status: `in_progress`

### Test Case 2: Half Day

**Input:** `HALF_DAY` event, `3h` work done, `20m` break  
**Expected:**
- Remaining: `1h`
- Break remaining: `10m`
- Status: `in_progress`

### Test Case 3: Holiday

**Input:** `HOLIDAY` event, `0h` work  
**Expected:**
- Remaining: `0h`
- Status: `completed` (no work required)

### Test Case 4: Exceeded Target

**Input:** `WORKING_DAY` event, `7h` work done, `90m` break  
**Expected:**
- Remaining: `0h` (target met)
- Alert: "Target exceeded"