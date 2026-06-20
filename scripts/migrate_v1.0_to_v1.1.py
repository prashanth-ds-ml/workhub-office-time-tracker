import json
from datetime import datetime
from pathlib import Path
import sys

DATA_DIR = Path("data")

def load_json(path):
    if not path.exists():
        return []
    return json.loads(path.read_text())

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))

def create_empty_file(filename, initial_data=None):
    file = DATA_DIR / filename
    if initial_data is None:
        initial_data = []
    if not file.exists():
        save_json(file, initial_data)
        print(f"[OK] Created {filename}")
    else:
        print(f"[OK] {filename} already exists")

# Default 2026 holidays
DEFAULT_HOLIDAYS = [
    {"id": "h001", "event_type": "HOLIDAY", "date": "2026-01-01", "title": "New Year", "description": "New Year Holiday", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()},
    {"id": "h002", "event_type": "HOLIDAY", "date": "2026-01-15", "title": "Makara Sankranti", "description": "Harvest Festival", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()},
    {"id": "h003", "event_type": "HOLIDAY", "date": "2026-01-26", "title": "Republic Day", "description": "India Republic Day", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()},
    {"id": "h004", "event_type": "HOLIDAY", "date": "2026-03-03", "title": "Holi", "description": "Festival of Colors", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()},
    {"id": "h005", "event_type": "HOLIDAY", "date": "2026-03-19", "title": "Ugadi", "description": "New Year (Karnataka)", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()},
    {"id": "h006", "event_type": "HOLIDAY", "date": "2026-03-20", "title": "Ramzan", "description": " Eid-ul-Fitr", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()},
    {"id": "h007", "event_type": "HOLIDAY", "date": "2026-08-15", "title": "Independence Day", "description": "India Independence Day", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()},
    {"id": "h008", "event_type": "HOLIDAY", "date": "2026-09-14", "title": "Vinayaka Chavithi", "description": "Ganesh Festival", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()},
    {"id": "h009", "event_type": "HOLIDAY", "date": "2026-10-02", "title": "Gandhi Jayanthi", "description": "Mahatma Gandhi's birthday", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()},
    {"id": "h010", "event_type": "HOLIDAY", "date": "2026-10-20", "title": "Vijaya Dasami", "description": "Dussehra", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()},
    {"id": "h011", "event_type": "HOLIDAY", "date": "2026-11-07", "title": "Diwali", "description": "Festival of Lights", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()},
    {"id": "h012", "event_type": "HOLIDAY", "date": "2026-12-25", "title": "Christmas", "description": "Christmas Day", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()},
]

# Default attendance policies
DEFAULT_POLICIES = [
    {"id": "p001", "event_type": "WORKING_DAY", "min_work_hours": 6, "target_work_hours": 6.5, "max_break_minutes": 90, "created_at": datetime.utcnow().isoformat()},
    {"id": "p002", "event_type": "HALF_DAY", "min_work_hours": 3.5, "target_work_hours": 4, "max_break_minutes": 30, "created_at": datetime.utcnow().isoformat()},
    {"id": "p003", "event_type": "FULL_DAY_SATURDAY", "min_work_hours": 6, "target_work_hours": 6.5, "max_break_minutes": 90, "created_at": datetime.utcnow().isoformat()},
]

def main():
    print("Running migration to v1.1 database schema...")
    print()
    
    # Create empty JSON files
    create_empty_file("calendar_events.json", DEFAULT_HOLIDAYS)
    create_empty_file("attendance_policies.json", DEFAULT_POLICIES)
    create_empty_file("announcements.json", [])
    create_empty_file("company_events.json", [])
    create_empty_file("announcement_reads.json", [])
    create_empty_file("alert_acknowledgements.json", [])
    
    print()
    print("Migration complete!")
    print()
    print("Attendance Policies Created:")
    for p in DEFAULT_POLICIES:
        print(f"  - {p['event_type']}: {p['min_work_hours']}h min, {p['target_work_hours']}h target, {p['max_break_minutes']}m max break")
    print()
    print(f"Holidays Created: {len(DEFAULT_HOLIDAYS)} events for 2026")
    print()

if __name__ == "__main__":
    main()