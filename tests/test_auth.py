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
