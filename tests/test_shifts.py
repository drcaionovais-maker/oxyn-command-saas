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


def test_shift_end_before_start_is_rejected(client, auth_headers):
    hospital_id, room_id = _create_hospital_and_room(client, auth_headers)
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    response = client.post(
        "/api/v1/shifts",
        headers=auth_headers,
        json={
            "hospital_id": hospital_id,
            "user_id": me["id"],
            "room_id": room_id,
            "shift_date": "2026-07-20",
            "starts_at": "2026-07-20T14:00:00Z",
            "ends_at": "2026-07-20T10:00:00Z",
        },
    )
    assert response.status_code == 422


def test_check_in_then_check_out_flow(client, auth_headers):
    hospital_id, room_id = _create_hospital_and_room(client, auth_headers)
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    shift = client.post(
        "/api/v1/shifts",
        headers=auth_headers,
        json={
            "hospital_id": hospital_id,
            "user_id": me["id"],
            "room_id": room_id,
            "shift_date": "2026-07-20",
            "starts_at": "2026-07-20T07:00:00Z",
            "ends_at": "2026-07-20T19:00:00Z",
        },
    )
    shift_id = shift.json()["id"]

    check_out_early = client.post(f"/api/v1/shifts/{shift_id}/check-out", headers=auth_headers)
    assert check_out_early.status_code == 409

    check_in = client.post(f"/api/v1/shifts/{shift_id}/check-in", headers=auth_headers)
    assert check_in.status_code == 200
    assert check_in.json()["check_in_at"] is not None

    check_out = client.post(f"/api/v1/shifts/{shift_id}/check-out", headers=auth_headers)
    assert check_out.status_code == 200
    assert check_out.json()["check_out_at"] is not None
