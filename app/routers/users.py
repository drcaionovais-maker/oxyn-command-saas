from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db import get_db
from app.dependencies import require_roles
from app.models import Role, User
from app.schemas import UserCreate, UserOut
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(Role.owner, Role.admin, Role.coordinator)),
):
    return db.scalars(select(User).where(User.tenant_id == current.tenant_id).order_by(User.full_name)).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(Role.owner, Role.admin)),
):
    email = body.email.lower()
    exists = db.scalar(select(User.id).where(User.tenant_id == current.tenant_id, User.email == email))
    if exists:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    user = User(
        tenant_id=current.tenant_id,
        email=email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role,
        crm=body.crm,
    )
    db.add(user)
    db.flush()
    log_action(db, current, "create", "user", user.id, {"role": body.role.value})
    db.commit()
    db.refresh(user)
    return user
