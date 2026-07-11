from fastapi.testclient import TestClient

from app.main import app


def test_validation_error_has_structured_body(client, auth_headers):
    response = client.post(
        "/api/v1/hospitals",
        headers=auth_headers,
        json={"name": "A"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "validation_error"
    assert body["errors"][0]["field"] == "name"
    assert "X-Request-ID" in response.headers


def test_unhandled_exception_returns_generic_500(auth_headers, monkeypatch):
    from app.routers import hospitals

    def boom(*args, **kwargs):
        raise RuntimeError("falha simulada")

    # patches the name as looked up inside hospitals.py at call time,
    # not app.audit.log_action itself
    monkeypatch.setattr(hospitals, "log_action", boom)

    local_client = TestClient(app, raise_server_exceptions=False)
    response = local_client.post(
        "/api/v1/hospitals",
        headers=auth_headers,
        json={"name": "Hospital Instável"},
    )
    assert response.status_code == 500
    assert response.json()["error_code"] == "internal_error"
    assert "X-Request-ID" in response.headers
