import os
os.environ["DATABASE_URL"] = "sqlite:////tmp/oxyn_saas_test.db"
os.environ["SECRET_KEY"] = "test-secret-key-with-at-least-thirty-two-characters"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Role, Tenant, User
from app.routers.auth import login_rate_limiter
from app.security import hash_password


@pytest.fixture(autouse=True)
def database():
    login_rate_limiter.reset()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        tenant = Tenant(name="OXYN Test", slug="oxyn-test")
        db.add(tenant)
        db.flush()
        db.add(
            User(
                tenant_id=tenant.id,
                email="admin@oxyn.test",
                full_name="Admin Teste",
                hashed_password=hash_password("StrongPass123!"),
                role=Role.owner,
            )
        )
        db.commit()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@oxyn.test", "password": "StrongPass123!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def other_tenant_auth_headers(client):
    with SessionLocal() as db:
        tenant = Tenant(name="OXYN Outro", slug="oxyn-outro")
        db.add(tenant)
        db.flush()
        db.add(
            User(
                tenant_id=tenant.id,
                email="admin@outro.test",
                full_name="Admin Outro",
                hashed_password=hash_password("StrongPass123!"),
                role=Role.owner,
            )
        )
        db.commit()
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@outro.test", "password": "StrongPass123!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def user_factory(client, auth_headers):
    def _create(email: str, role: str, password: str = "StrongPass123!"):
        response = client.post(
            "/api/v1/users",
            headers=auth_headers,
            json={"email": email, "full_name": "Usuário Teste", "password": password, "role": role},
        )
        assert response.status_code == 201
        login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
        assert login.status_code == 200
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    return _create
