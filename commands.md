# Command Reference

Commands for the Tkinter desktop app and its local Python backend.

## 1. Setup

### 1.1 Create and activate virtual environment
```bash
# Windows
.\create_venv.bat

# Or manually
python -m venv .venv
.venv\Scripts\activate
```

### 1.2 Install Python dependencies
```bash
pip install -r requirements.txt
```

### 1.3 Optional: start MongoDB
Use your local MongoDB service or set `MONGO_URI` to a hosted instance.

## 2. Run

### 2.1 Start the desktop app
```bash
python desktop_app.py
```

The desktop app is the main product surface. It can auto-start a local API instance if the backend is not already running.

### 2.2 Start the backend API separately
```bash
uvicorn app:app --reload
```

API:
- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/docs`

### 2.3 Install auto-start on Windows
```bash
python desktop_app.py --install-startup
```

### 2.4 Remove auto-start
```bash
python desktop_app.py --uninstall-startup
```

## 3. Test

### 3.1 Python smoke checks
```bash
python -m py_compile app.py storage.py desktop_app.py
python -c "import desktop_app; print('desktop import ok')"
python -c "import app; print('api import ok')"
python -c "import storage; print(storage.storage_backend())"
```

### 3.2 Backend health
```bash
curl http://127.0.0.1:8000/health
```

### 3.3 Login test
```bash
curl -X POST http://127.0.0.1:8000/login -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"password\":\"admin123\"}"
```

### 3.4 Calendar test
```bash
curl http://127.0.0.1:8000/calendar/events/2026-06-19
curl http://127.0.0.1:8000/calendar/policy/HALF_DAY
```

### 3.5 Attendance overview test
```bash
curl http://127.0.0.1:8000/attendance/today
```

### 3.6 Announcement test
```bash
curl -X POST http://127.0.0.1:8000/announcements -H "Content-Type: application/json" -H "X-User-Id: 1111-1111-admin" -d "{\"title\":\"Team meeting\",\"content\":\"We have a meeting at 2:00 PM today.\",\"effective_date\":\"2026-06-20\"}"
```

## 4. Reset data

### 4.1 Clear JSON fallback files
```bash
del data\*.json
```

### 4.2 Clear MongoDB
Drop the `office_time_tracker` database or clear its collections.

---

Full local run order:
1. `.\create_venv.bat`
2. `pip install -r requirements.txt`
3. `python desktop_app.py`
