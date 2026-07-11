from app.db import SessionLocal
from app.models import Role, Tenant, User
from app.security import hash_password


def test_new_user_has_default_security_fields():
    with SessionLocal() as db:
        tenant = Tenant(name="OXYN Modelos", slug="oxyn-modelos")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            email="modelo@oxyn.test",
            full_name="Usuário Modelo",
            hashed_password=hash_password("StrongPass123!"),
            role=Role.viewer,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
        assert user.token_version == 0
