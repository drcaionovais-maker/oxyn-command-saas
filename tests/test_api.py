def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_hospital_room_and_dashboard(client, auth_headers):
    hospital = client.post(
        "/api/v1/hospitals",
        headers=auth_headers,
        json={"name": "Hospital Platinum", "city": "São Paulo"},
    )
    assert hospital.status_code == 201
    hospital_id = hospital.json()["id"]

    room = client.post(
        f"/api/v1/hospitals/{hospital_id}/rooms",
        headers=auth_headers,
        json={"code": "01", "name": "Sala 01", "specialty": "Ortopedia"},
    )
    assert room.status_code == 201
    room_id = room.json()["id"]

    updated = client.patch(
        f"/api/v1/hospitals/{hospital_id}/rooms/{room_id}",
        headers=auth_headers,
        json={"status": "surgery", "current_procedure": "Artroplastia total de joelho"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "surgery"

    summary = client.get(f"/api/v1/dashboard/{hospital_id}", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["rooms_in_surgery"] == 1


def test_protected_route_requires_token(client):
    response = client.get("/api/v1/hospitals")
    assert response.status_code == 401
