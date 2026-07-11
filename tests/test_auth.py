from sqlalchemy import select

from app.db import SessionLocal
from app.models import User


def test_login_returns_token_pair(client, auth_headers):
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "admin@oxyn.test"


def test_refresh_issues_new_access_token(client):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@oxyn.test", "password": "StrongPass123!"},
    )
    refresh_token = login.json()["refresh_token"]
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()


def test_logout_invalidates_previous_tokens(client):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@oxyn.test", "password": "StrongPass123!"},
    )
    old_access = login.json()["access_token"]
    old_refresh = login.json()["refresh_token"]

    logout = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {old_access}"})
    assert logout.status_code == 204

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"})
    assert me.status_code == 401

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 401


def test_lockout_after_max_failed_attempts(client):
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "admin@oxyn.test", "password": "wrong-password"},
        )
        assert response.status_code == 401

    locked = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@oxyn.test", "password": "StrongPass123!"},
    )
    assert locked.status_code == 423


def test_successful_login_resets_failed_attempts(client):
    for _ in range(3):
        client.post(
            "/api/v1/auth/login",
            data={"username": "admin@oxyn.test", "password": "wrong-password"},
        )
    ok = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@oxyn.test", "password": "StrongPass123!"},
    )
    assert ok.status_code == 200

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "admin@oxyn.test"))
        assert user.failed_login_attempts == 0


def test_login_rate_limited_by_ip(client):
    from app.config import settings

    for _ in range(settings.login_rate_limit_per_minute):
        client.post(
            "/api/v1/auth/login",
            data={"username": "admin@oxyn.test", "password": "wrong-password"},
        )
    blocked = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@oxyn.test", "password": "wrong-password"},
    )
    assert blocked.status_code == 429
