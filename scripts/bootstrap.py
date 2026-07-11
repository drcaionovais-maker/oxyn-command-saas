import re

from sqlalchemy import select

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Role, Tenant, User
from app.security import hash_password


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == slugify(settings.bootstrap_tenant_name)))
        if not tenant:
            tenant = Tenant(name=settings.bootstrap_tenant_name, slug=slugify(settings.bootstrap_tenant_name))
            db.add(tenant)
            db.flush()
        admin = db.scalar(
            select(User).where(User.tenant_id == tenant.id, User.email == settings.bootstrap_admin_email.lower())
        )
        if not admin:
            db.add(
                User(
                    tenant_id=tenant.id,
                    email=settings.bootstrap_admin_email.lower(),
                    full_name="Administrador OXYN",
                    hashed_password=hash_password(settings.bootstrap_admin_password),
                    role=Role.owner,
                )
            )
        db.commit()


if __name__ == "__main__":
    main()
