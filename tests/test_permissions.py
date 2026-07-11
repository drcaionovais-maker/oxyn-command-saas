def test_nurse_cannot_create_hospital(client, user_factory):
    nurse_headers = user_factory("enfermeira@example.com", "nurse")
    response = client.post(
        "/api/v1/hospitals",
        headers=nurse_headers,
        json={"name": "Hospital Sem Permissão"},
    )
    assert response.status_code == 403


def test_viewer_cannot_create_user(client, user_factory):
    viewer_headers = user_factory("visualizador@example.com", "viewer")
    response = client.post(
        "/api/v1/users",
        headers=viewer_headers,
        json={"email": "novo@example.com", "full_name": "Novo", "password": "StrongPass123!", "role": "viewer"},
    )
    assert response.status_code == 403


def test_coordinator_can_create_room_but_not_hospital(client, user_factory, auth_headers):
    hospital = client.post(
        "/api/v1/hospitals",
        headers=auth_headers,
        json={"name": "Hospital Central"},
    )
    hospital_id = hospital.json()["id"]
    coordinator_headers = user_factory("coordenador@example.com", "coordinator")

    forbidden = client.post(
        "/api/v1/hospitals",
        headers=coordinator_headers,
        json={"name": "Hospital Extra"},
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        f"/api/v1/hospitals/{hospital_id}/rooms",
        headers=coordinator_headers,
        json={"code": "01", "name": "Sala 01"},
    )
    assert allowed.status_code == 201


def test_cannot_access_hospital_from_other_tenant(client, auth_headers, other_tenant_auth_headers):
    hospital = client.post(
        "/api/v1/hospitals",
        headers=auth_headers,
        json={"name": "Hospital Privado"},
    )
    hospital_id = hospital.json()["id"]

    response = client.get(f"/api/v1/hospitals/{hospital_id}/rooms", headers=other_tenant_auth_headers)
    assert response.status_code == 404


def test_users_are_isolated_by_tenant(client, auth_headers, other_tenant_auth_headers):
    response = client.get("/api/v1/users", headers=other_tenant_auth_headers)
    assert response.status_code == 200
    emails = [user["email"] for user in response.json()]
    assert "admin@oxyn.test" not in emails
