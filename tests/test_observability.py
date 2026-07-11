import logging


def test_response_includes_request_id_header(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) == 36


def test_login_failure_is_logged(client, caplog):
    with caplog.at_level(logging.INFO, logger="oxyn.auth"):
        client.post(
            "/api/v1/auth/login",
            data={"username": "admin@oxyn.test", "password": "wrong-password"},
        )
    assert any("Falha de login" in record.message for record in caplog.records)
