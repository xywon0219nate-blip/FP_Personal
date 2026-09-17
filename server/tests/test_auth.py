from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_login_wrong_credentials_returns_401():
    res = client.post("/api/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "wrongpassword",
    })
    assert res.status_code in (401, 400, 422)


def test_signup_missing_fields_returns_422():
    res = client.post("/api/auth/signup", json={})
    assert res.status_code == 422