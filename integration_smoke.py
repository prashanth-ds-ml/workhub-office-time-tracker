from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import app
import storage


DATA_FILES = [
    "USERS_FILE",
    "SESSIONS_FILE",
    "BREAKS_FILE",
    "CALENDAR_EVENTS_FILE",
    "HOLIDAY_MASTER_FILE",
    "ATTENDANCE_POLICIES_FILE",
    "COMPANY_WORK_POLICY_FILE",
    "ANNOUNCEMENTS_FILE",
    "COMPANY_EVENTS_FILE",
    "ANNOUNCEMENT_READS_FILE",
    "ALERT_ACK_FILE",
]


def expect(response, status: int = 200):
    assert response.status_code == status, f"{response.request.method} {response.request.url}: {response.status_code} {response.text}"
    return response.json()


def auth_headers(auth: dict) -> dict:
    return {"Authorization": f"Bearer {auth['access_token']}"}


def run() -> None:
    with tempfile.TemporaryDirectory(prefix="workhub-smoke-") as temporary:
        root = Path(temporary)
        storage._STORAGE = storage._JsonStorage()
        for name in DATA_FILES:
            current = Path(getattr(app, name))
            setattr(app, name, root / current.name)
        app._seed_initial_data()
        app._refresh_cache()

        client = TestClient(app.app)
        health = expect(client.get("/health"))
        assert health["status"] == "ok"
        assert health["storage"]["connected"] is True
        expect(client.get("/me", headers={"Authorization": "Bearer invalid-token"}), 401)

        admin_auth = expect(
            client.post(
                "/register",
                json={
                    "username": "Integration Admin",
                    "email": "admin@example.com",
                    "password": "admin123",
                    "role": "Admin",
                },
            )
        )
        admin = admin_auth["user"]
        admin_headers = auth_headers(admin_auth)
        assert admin["role"] == "Admin"
        assert "password" not in admin

        employee_auth = expect(
            client.post(
                "/register",
                json={"username": "Integration Employee", "email": "integration@example.com", "password": "secret1"},
            )
        )
        employee = employee_auth["user"]
        employee_headers = auth_headers(employee_auth)
        assert employee["role"] == "User"
        assert "password" not in employee
        login_auth = expect(client.post("/login", json={"email": employee["email"], "password": "secret1"}))
        assert login_auth["user"]["id"] == employee["id"]
        expect(client.get("/admin/users", headers=employee_headers), 403)

        policy = {
            "office_hours": {"start": "08:30", "end": "17:30"},
            "rules": {
                "min_work_hours": 6,
                "max_work_hours": 9,
                "min_break_minutes": 20,
                "max_break_minutes": 75,
            },
        }
        expect(client.post("/company/work-policy", headers=admin_headers, json=policy))
        users = expect(client.get("/admin/users", headers=admin_headers))
        assert all(user["office_hours"] == policy["office_hours"] for user in users)
        assert all(user["rules"] == policy["rules"] for user in users)

        created = expect(
            client.post(
                "/admin/users",
                headers=admin_headers,
                json={"username": "Managed Employee", "email": "managed@example.com", "password": "secret2", "role": "User"},
            )
        )
        assert created["office_hours"] == policy["office_hours"]
        updated = expect(
            client.patch(
                f"/admin/users/{created['id']}",
                headers=admin_headers,
                json={"username": "Managed Employee Updated", "role": "Admin"},
            )
        )
        assert updated["username"] == "Managed Employee Updated" and updated["role"] == "Admin"

        event = expect(
            client.post(
                "/calendar/events",
                headers=admin_headers,
                json={
                    "event_type": "WORKING_DAY",
                    "date": "2026-06-22",
                    "title": "Integration Working Day",
                    "description": "Smoke test",
                },
            )
        )
        assert event["calendar_event"]["date"] == "2026-06-22"
        assert any(
            item["date"] == "2026-06-22"
            for item in expect(client.get("/calendar/events", headers=employee_headers, params={"month": "2026-06"}))
        )

        session = expect(client.post(f"/sessions/{employee['id']}/start", headers=employee_headers))
        session_id = session["id"]
        expect(client.post(f"/sessions/{session_id}/break/start", headers=employee_headers))
        expect(client.post(f"/sessions/{session_id}/break/stop", headers=employee_headers))
        expect(client.post(f"/sessions/{session_id}/stop", headers=employee_headers))
        assert expect(client.get("/sessions", headers=employee_headers))[0]["is_active"] is False

        announcement = expect(
            client.post(
                "/announcements",
                headers=admin_headers,
                json={"title": "Integration update", "content": "Connected", "effective_date": "2026-06-20"},
            )
        )
        listed = expect(client.get("/announcements", headers=employee_headers))
        assert any(item["id"] == announcement["id"] for item in listed)
        expect(client.post(f"/announcements/{announcement['id']}/read", headers=employee_headers))

        overview = expect(client.get("/dashboard/overview", headers=employee_headers, params={"month": "2026-06"}))
        assert "remaining_working_days" in overview["month_summary"]
        analytics = expect(client.get("/admin/analytics", headers=admin_headers, params={"month": "2026-06"}))
        assert any(row["user_id"] == employee["id"] for row in analytics["employees"])

        expect(client.patch(f"/admin/users/{employee['id']}", headers=admin_headers, json={"is_active": False}))
        expect(client.post("/login", json={"email": employee["email"], "password": "secret1"}), 403)
        expect(client.get("/me", headers=employee_headers), 403)

        print("PASS: authentication, registration, roles, policy, employees, calendar, sessions, breaks, announcements, dashboard, analytics")


if __name__ == "__main__":
    run()
