from __future__ import annotations

import os
import uuid

os.environ["WORKHUB_ENV"] = "production"
os.environ["WORKHUB_JWT_SECRET"] = "mongo-smoke-test-secret-not-for-production"
os.environ["WORKHUB_BOOTSTRAP_SECRET"] = "mongo-bootstrap-secret"
os.environ["WORKHUB_ALLOW_SELF_REGISTRATION"] = "true"
os.environ["MONGO_DB"] = f"workhub_smoke_{uuid.uuid4().hex}"

from fastapi.testclient import TestClient

import app
import storage


def expect(response, status: int = 200):
    assert response.status_code == status, f"{response.status_code}: {response.text}"
    return response.json()


def headers(auth: dict) -> dict:
    return {"Authorization": f"Bearer {auth['access_token']}"}


def main() -> None:
    assert storage.storage_backend() == "mongo"
    client = TestClient(app.app)
    try:
        admin = expect(
            client.post(
                "/register",
                json={
                    "username": "Mongo Admin",
                    "email": "admin@mongo.test",
                    "password": "secret1",
                    "bootstrap_secret": "mongo-bootstrap-secret",
                },
            )
        )
        employee = expect(
            client.post(
                "/register",
                json={"username": "Mongo Employee", "email": "employee@mongo.test", "password": "secret2"},
            )
        )
        admin_headers = headers(admin)
        employee_headers = headers(employee)

        expect(
            client.patch(
                f"/admin/users/{employee['user']['id']}",
                headers=admin_headers,
                json={"username": "Mongo Employee Updated"},
            )
        )
        session = expect(
            client.post(
                f"/sessions/{employee['user']['id']}/start",
                headers=employee_headers,
            )
        )
        users = expect(client.get("/admin/users", headers=admin_headers))
        assert any(row["username"] == "Mongo Employee Updated" for row in users)
        assert expect(client.get("/sessions", headers=employee_headers))[0]["id"] == session["id"]
        health = expect(client.get("/health"))
        assert health["storage"]["backend"] == "mongo"
        assert health["storage"]["connected"] is True
        print("PASS: JWT and document-level writes against temporary MongoDB")
    finally:
        storage._STORAGE.client.drop_database(os.environ["MONGO_DB"])


if __name__ == "__main__":
    main()
