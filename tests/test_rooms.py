def _create_hospital_and_room(client, auth_headers):
    hospital = client.post(
        "/api/v1/hospitals",
        headers=auth_headers,
        json={"name": "Hospital Central", "city": "São Paulo"},
    )
    hospital_id = hospital.json()["id"]
    room = client.post(
        f"/api/v1/hospitals/{hospital_id}/rooms",
        headers=auth_headers,
        json={"code": "01", "name": "Sala 01"},
    )
    return hospital_id, room.json()["id"]


def test_valid_room_status_transition_chain(client, auth_headers):
    hospital_id, room_id = _create_hospital_and_room(client, auth_headers)
    for status in ("preparation", "surgery", "recovery", "free"):
        response = client.patch(
            f"/api/v1/hospitals/{hospital_id}/rooms/{room_id}",
            headers=auth_headers,
            json={"status": status},
        )
        assert response.status_code == 200
        assert response.json()["status"] == status


def test_invalid_room_status_transition_is_rejected(client, auth_headers):
    hospital_id, room_id = _create_hospital_and_room(client, auth_headers)
    response = client.patch(
        f"/api/v1/hospitals/{hospital_id}/rooms/{room_id}",
        headers=auth_headers,
        json={"status": "recovery"},
    )
    assert response.status_code == 409
