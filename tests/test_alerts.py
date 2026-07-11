def test_resolving_already_resolved_alert_is_rejected(client, auth_headers):
    alert = client.post(
        "/api/v1/alerts",
        headers=auth_headers,
        json={"level": "warning", "title": "Falta de gás anestésico", "detail": "Estoque baixo na sala 2"},
    )
    alert_id = alert.json()["id"]

    first = client.post(f"/api/v1/alerts/{alert_id}/resolve", headers=auth_headers)
    assert first.status_code == 200

    second = client.post(f"/api/v1/alerts/{alert_id}/resolve", headers=auth_headers)
    assert second.status_code == 409
