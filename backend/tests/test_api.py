from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


client = TestClient(app)


def test_health():
    data = client.get("/api/health").json()
    assert data["status"] == "ok"
    assert data["app"] == "Clinical AI Webapp"


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
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    logout = client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 200


def test_auth_role_restrictions():
    suffix = uuid4().hex
    password = "long-password"
    client.post("/api/auth/register", json={"email": f"provider-{suffix}@example.com", "password": password, "role": "PROVIDER"})
    login = client.post("/api/auth/login", json={"email": f"provider-{suffix}@example.com", "password": password})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post("/api/patients", json={"name": "Blocked", "drive_folder_id": f"folder-{suffix}"}, headers=headers)
    assert response.status_code == 403
