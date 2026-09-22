from __future__ import annotations

import os
import uuid

os.environ["WORKHUB_ENV"] = "production"
os.environ["WORKHUB_JWT_SECRET"] = "postgres-smoke-test-secret-not-for-production"
os.environ["WORKHUB_BOOTSTRAP_SECRET"] = "postgres-bootstrap-secret"
os.environ["WORKHUB_ALLOW_SELF_REGISTRATION"] = "true"
os.environ["WORKHUB_EMAIL_DOMAIN"] = "postgres.test"

from fastapi.testclient import TestClient

import app
import storage


def expect(response, status: int = 200):
    assert response.status_code == status, f"{response.status_code}: {response.text}"
    return response.json()


def headers(auth: dict) -> dict:
    return {"Authorization": f"Bearer {auth['access_token']}"}


def main() -> None:
    assert storage.storage_backend() == "postgres"
    client = TestClient(app.app)
    suffix = uuid.uuid4().hex[:8]
    try:
        admin = expect(
            client.post(
                "/register",
                json={
                    "username": "Postgres Admin",
                    "email": f"admin+{suffix}@postgres.test",
                    "password": "secret1",
                    "role": "Manager",
                    "bootstrap_secret": "postgres-bootstrap-secret",
                },
            )
        )
        employee = expect(
            client.post(
                "/register",
                json={
                    "username": "Postgres Employee",
                    "email": f"employee+{suffix}@postgres.test",
                    "password": "secret2",
                },
            )
        )
        admin_headers = headers(admin)
        employee_headers = headers(employee)

        expect(
            client.patch(
                f"/admin/users/{employee['user']['id']}",
                headers=admin_headers,
                json={"username": "Postgres Employee Updated"},
            )
        )
        session = expect(
            client.post(
                f"/sessions/{employee['user']['id']}/start",
                headers=employee_headers,
            )
        )
        users = expect(client.get("/admin/users", headers=admin_headers))
        assert any(row["username"] == "Postgres Employee Updated" for row in users)
        assert expect(client.get("/sessions", headers=employee_headers))[0]["id"] == session["id"]
        health = expect(client.get("/health"))
        assert health["storage"]["backend"] == "postgres"
        assert health["storage"]["connected"] is True
        print("PASS: JWT and document-level writes against Postgres")
    finally:
        conn = storage._STORAGE.conn
        conn.execute(
            "DELETE FROM breaks WHERE data ->> 'session_id' IN ("
            "SELECT data ->> 'id' FROM sessions WHERE data ->> 'user_id' IN ("
            "SELECT data ->> 'id' FROM users WHERE data ->> 'email' LIKE %s))",
            (f"%+{suffix}@postgres.test",),
        )
        conn.execute(
            "DELETE FROM sessions WHERE data ->> 'user_id' IN ("
            "SELECT data ->> 'id' FROM users WHERE data ->> 'email' LIKE %s)",
            (f"%+{suffix}@postgres.test",),
        )
        conn.execute(
            "DELETE FROM users WHERE data ->> 'email' LIKE %s", (f"%+{suffix}@postgres.test",)
        )


if __name__ == "__main__":
    main()
