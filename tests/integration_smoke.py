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
    "AUDIT_LOG_FILE",
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
        app._refresh_cache(force=True)
        selected_month = app._current_month_label()
        event_date = app._ist_today().isoformat()

        client = TestClient(app.app)
        web_home = client.get("/")
        assert web_home.status_code == 200
        if app.WEB_INDEX_FILE.is_file():
            assert "text/html" in web_home.headers["content-type"]
            assert client.get("/calendar").status_code == 200
            asset = next((app.WEB_DIST_DIR / "assets").glob("*.js"))
            asset_response = client.get(f"/assets/{asset.name}")
            assert asset_response.status_code == 200
            assert "immutable" in asset_response.headers.get("cache-control", "")
            logo_response = client.get("/med360-logo.png")
            assert logo_response.status_code == 200
            assert logo_response.headers["content-type"] == "image/png"
            launcher_response = client.get("/med360-launcher.svg")
            assert launcher_response.status_code == 200
            assert "image/svg+xml" in launcher_response.headers["content-type"]
        assert client.get("/docs").status_code == 200
        health = expect(client.get("/health"))
        assert health["status"] == "ok"
        assert health["storage"]["connected"] is True
        expect(client.get("/me", headers={"Authorization": "Bearer invalid-token"}), 401)

        admin_auth = expect(
            client.post(
                "/register",
                json={
                    "username": "Integration Admin",
                    "email": "admin@sims.healthcare",
                    "password": "admin123",
                    "role": "Manager",
                    "security_question": "Test question",
                    "security_answer": "test answer",
                },
            )
        )
        admin = admin_auth["user"]
        admin_headers = auth_headers(admin_auth)
        assert admin["role"] == "Manager"
        assert "password" not in admin
        expect(
            client.post(
                "/register",
                json={
                    "username": "External Employee",
                    "email": "external@example.com",
                    "password": "secret1",
                    "security_question": "Test question",
                    "security_answer": "test answer",
                },
            ),
            403,
        )
        expect(
            client.post(
                "/login",
                json={"email": "external@example.com", "password": "secret1"},
            ),
            403,
        )

        employee_auth = expect(
            client.post(
                "/register",
                json={"username": "Integration Employee", "email": "integration@sims.healthcare", "password": "secret1", "security_question": "Test question", "security_answer": "test answer"},
            )
        )
        employee = employee_auth["user"]
        employee_headers = auth_headers(employee_auth)
        assert employee["role"] == "User"
        assert "password" not in employee
        login_response = client.post("/login", json={"email": employee["email"], "password": "secret1"})
        login_auth = expect(login_response)
        assert login_auth["user"]["id"] == employee["id"]
        assert "workhub_session" in client.cookies
        assert expect(client.get("/me"))["id"] == employee["id"]
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
                json={"username": "Managed Employee", "email": "managed@sims.healthcare", "password": "secret2", "role": "User", "security_question": "Test question", "security_answer": "test answer"},
            )
        )
        assert created["office_hours"] == policy["office_hours"]
        expect(
            client.post(
                "/admin/users",
                headers=admin_headers,
                json={"username": "External User", "email": "external@example.com", "password": "secret2", "security_question": "Test question", "security_answer": "test answer"},
            ),
            403,
        )
        updated = expect(
            client.patch(
                f"/admin/users/{created['id']}",
                headers=admin_headers,
                json={"username": "Managed Employee Updated", "role": "Manager"},
            )
        )
        assert updated["username"] == "Managed Employee Updated" and updated["role"] == "Manager"

        event = expect(
            client.post(
                "/calendar/events",
                headers=admin_headers,
                json={
                    "event_type": "WORKING_DAY",
                    "date": event_date,
                    "title": "Integration Working Day",
                    "description": "Smoke test",
                },
            )
        )
        assert event["calendar_event"]["date"] == event_date
        assert any(
            item["date"] == event_date
            for item in expect(client.get("/calendar/events", headers=employee_headers, params={"month": selected_month}))
        )

        session = expect(client.post(f"/sessions/{employee['id']}/start", headers=employee_headers))
        session_id = session["id"]
        expect(client.post(f"/sessions/{session_id}/break/start", headers=employee_headers))
        expect(client.post(f"/sessions/{session_id}/break/stop", headers=employee_headers))
        expect(client.post(f"/sessions/{session_id}/stop", headers=employee_headers))
        assert expect(client.get("/sessions", headers=employee_headers))[0]["is_active"] is False
        dashboard = expect(client.get("/admin/dashboard", headers=admin_headers))
        assert dashboard[employee["username"]]["work_hours"] >= 0

        announcement = expect(
            client.post(
                "/announcements",
                headers=admin_headers,
                json={"title": "Integration update", "content": "Connected", "effective_date": event_date},
            )
        )
        listed = expect(client.get("/announcements", headers=employee_headers))
        assert any(item["id"] == announcement["id"] for item in listed)
        expect(client.post(f"/announcements/{announcement['id']}/read", headers=employee_headers))

        overview = expect(client.get("/dashboard/overview", headers=employee_headers, params={"month": selected_month}))
        assert "remaining_working_days" in overview["month_summary"]
        analytics = expect(client.get("/admin/analytics", headers=admin_headers, params={"month": selected_month}))
        employee_analytics = next(row for row in analytics["employees"] if row["user_id"] == employee["id"])
        assert employee_analytics["days_worked"] == 1
        workspace = expect(client.get("/web/bootstrap", headers=admin_headers, params={"month": selected_month}))
        assert workspace["overview"]["month"] == selected_month
        assert workspace["analytics"] is None
        assert workspace["employees"] == []
        assert workspace["sessions"] == []
        web_attendance = expect(client.get("/web/attendance", headers=employee_headers, params={"month": selected_month}))
        assert any(row["id"] == session_id for row in web_attendance["sessions"])
        web_announcements = expect(client.get("/web/announcements?limit=50", headers=employee_headers))
        assert any(row["id"] == announcement["id"] for row in web_announcements["announcements"])
        expect(client.post("/logout", headers=admin_headers))

        expect(client.patch(f"/admin/users/{employee['id']}", headers=admin_headers, json={"is_active": False}))
        expect(client.post("/login", json={"email": employee["email"], "password": "secret1"}), 403)
        expect(client.get("/me", headers=employee_headers), 403)

        # Official holidays are seeded, and the reminder app's public endpoint works.
        assert any(row["date"] == "2026-10-02" for row in storage.load_rows(app.HOLIDAY_MASTER_FILE))
        public_today = expect(client.get("/calendar/public/today"))
        assert public_today["date"] == event_date and public_today["event_type"] == "WORKING_DAY"

        # A user written by "another instance" is visible without a restart.
        other = app.User(username="Other Instance", email="other@sims.healthcare", password="x")
        storage.upsert_rows(app.USERS_FILE, [other.dict()])
        assert any(u["email"] == "other@sims.healthcare" for u in expect(client.get("/admin/users", headers=admin_headers)))

        # A holiday added elsewhere shows on the calendar without a restart.
        storage.upsert_rows(
            app.HOLIDAY_MASTER_FILE,
            [{"id": "x1", "date": "2026-12-30", "title": "Extra Holiday", "description": None, "event_type": "HOLIDAY", "source": "t", "updated_at": app._iso_now()}],
        )
        app._calendar_refreshed_at = 0.0
        extra = expect(client.get("/calendar/events/2026-12-30", headers=admin_headers))
        assert extra["event_type"] == "HOLIDAY" and extra["title"] == "Extra Holiday"

        # Re-seeding (every cold start) must not overwrite a manager's changes.
        app._seed_initial_data()
        assert app._company_work_policy()["office_hours"] == policy["office_hours"]
        assert sum(1 for r in storage.load_rows(app.HOLIDAY_MASTER_FILE) if r["date"] == "2026-10-02") == 1

        print("PASS: authentication, registration, roles, policy, employees, calendar, sessions, breaks, announcements, dashboard, analytics")


if __name__ == "__main__":
    run()
