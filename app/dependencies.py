from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Role, User
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        token_version = payload.get("tv")
    except jwt.InvalidTokenError as exc:
        raise credentials_error from exc
    user = db.scalar(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id, User.active.is_(True))
    )
    if not user or user.token_version != token_version:
        raise credentials_error
    return user


def require_roles(*roles: Role) -> Callable[..., User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Permissão insuficiente")
        return user

    return dependency


def tenant_object_or_404(db: Session, model: type, object_id: str, tenant_id: str):
    obj = db.scalar(select(model).where(model.id == object_id, model.tenant_id == tenant_id))
    if not obj:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return obj
