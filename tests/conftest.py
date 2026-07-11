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
