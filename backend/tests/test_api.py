from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_auth_patient_flow():
    suffix = uuid4().hex
    email = f"admin-{suffix}@example.com"
    password = "long-password"
    register = client.post("/api/auth/register", json={"email": email, "password": password, "role": "ADMIN"})
    assert register.status_code == 201
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/patients", json={"name": "Jane Doe", "drive_folder_id": f"folder-{suffix}"}, headers=headers)
    assert created.status_code == 201
    patients = client.get("/api/patients", headers=headers)
    assert patients.status_code == 200
