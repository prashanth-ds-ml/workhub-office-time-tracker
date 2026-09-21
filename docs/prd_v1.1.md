# WorkHub v1.1 PRD

## Updated Product Scope

### Core Philosophy

Employees should never wonder:

* Is tomorrow a holiday?
* Is Saturday a half day?
* Is Monday a compensatory leave?
* How many working days are left this month?
* How many hours do I still need to work today?

WorkHub should answer all of these immediately.

---

# New Core Module: Company Calendar Engine

This becomes the source of truth for the entire application.

Attendance rules are derived from calendar events.

Managers can modify the calendar without requiring code changes.

---

# Calendar Event Types

## WORKING_DAY

Normal weekday.

Policy:

Work Min: 6h

Work Target: 6h 30m

Break Max: 1h 30m

---

## HALF_DAY

Odd Saturdays.

Policy:

Work Min: 3h 30m

Work Target: 4h

Break Max: 30m

---

## FULL_DAY_SATURDAY

Manager override.

Example:

Saturday becomes a full working day.

Policy:

Work Min: 6h

Work Target: 6h 30m

Break Max: 1h 30m

---

## HOLIDAY

Examples:

* Republic Day
* Ugadi
* Ramzan
* Diwali

Attendance not required.

---

## COMP_OFF

Compensatory holiday.

Example:

Worked Saturday.

Monday declared off.

Attendance not required.

---

## LONG_WEEKEND

Special company leave.

Example:

Friday off.

Saturday off.

Sunday off.

Attendance not required.

---

## COMPANY_EVENT

Examples:

* Annual Meeting
* Team Outing
* Company Celebration

Shown in calendar.

---

# Company Holiday List 2026

Configured from company circular.

## Holidays

01-Jan-2026 – New Year

15-Jan-2026 – Makara Sankranti

26-Jan-2026 – Republic Day

03-Mar-2026 – Holi

19-Mar-2026 – Ugadi

20-Mar-2026 – Ramzan

15-Aug-2026 – Independence Day

14-Sep-2026 – Vinayaka Chavithi

02-Oct-2026 – Gandhi Jayanthi

20-Oct-2026 – Vijaya Dasami

07-Nov-2026 – Diwali

25-Dec-2026 – Christmas

Manager can update dates if festival dates change.

---

# New Dashboard Layout

## Section 1

Today's Status

Example:

Today: Working Day

Office Window:

10:00 AM - 05:30 PM

Target:

6h 30m

---

## Section 2

Today's Progress

Work Done:

4h 25m

Remaining:

2h 05m

Break Used:

35m

Break Remaining:

55m

Estimated Completion:

04:42 PM

---

## Section 3

Monthly Summary

Month: June 2026

Working Days: 22

Completed: 12

Remaining: 10

Holidays: 1

Comp Offs: 1

---

## Section 4

Upcoming Calendar Events

Next Holiday:

Ugadi

19-Mar-2026

Next Half Day:

21-Mar-2026

Next Company Event:

Monthly Review Meeting

---

## Section 5

Announcements

Company announcements feed.

---

## Section 6

Team Announcements

Short team-wide notices and meeting updates.

---

# New Calendar Dashboard

## Calendar View

Legend:

🟢 Working Day

🟡 Half Day

🟠 Full Saturday

🔵 Holiday

🟣 Comp Off

🔴 Weekend

---

## Monthly Statistics

Example:

March 2026

Total Days: 31

Working Days: 22

Half Days: 2

Holidays: 2

Comp Offs: 1

Weekends: 4

---

## Long Weekend Planner

Automatically detect upcoming long weekends.

Example:

19-Mar to 22-Mar

4-Day Weekend

---

# Manager Features

## Calendar Management

Managers can:

* Create Holiday
* Create Comp Off
* Create Long Weekend
* Convert Half Day to Full Day
* Convert Working Day to Holiday

---

## Auto Announcement Generation

Calendar changes automatically generate announcements.

Example:

"June 27 marked as Full Working Saturday."

"June 29 marked as Compensatory Holiday."

---

# Attendance Calculation

Attendance should be calculated from the calendar event assigned to the day.

Example:

Holiday

→ Attendance not required

Half Day

→ Half-day work policy applied

Working Day

→ Normal work policy applied

This removes hardcoded attendance rules.

---

# New Database Tables

calendar_events

holiday_master

attendance_policies

company_events

announcement_reads

alert_acknowledgements

---

# MVP Scope

## Employee

* Login
* Clock In
* Break Tracking
* Clock Out
* Daily Timeline
* Monthly Calendar
* Working Day Counter
* Holiday Calendar
* Announcements
* Work Alerts
* System Tray

---

## Manager

* Team Dashboard
* Calendar Management
* Announcements
* Work Alerts
* Attendance Reports

---

## Admin

* User Management
* Policy Management
* Holiday Management
* Calendar Overrides
* CSV/Excel Export

---

# Future Enhancements

V2

* Leave Management
* WhatsApp Notifications
* Mobile App

V3

* Payroll Integration
* SSO Login
* Teams/Slack Integration
