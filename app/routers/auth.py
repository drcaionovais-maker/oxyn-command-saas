import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import RefreshRequest, TokenPair, UserOut
from app.security import create_token, decode_token, verify_password

router = APIRouter(prefix="/auth", tags=["Autenticação"])


def token_pair(user: User) -> TokenPair:
    role = user.role.value
    return TokenPair(
        access_token=create_token(user.id, user.tenant_id, role, "access", user.token_version),
        refresh_token=create_token(user.id, user.tenant_id, role, "refresh", user.token_version),
    )


@router.post("/login", response_model=TokenPair)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower(), User.active.is_(True)))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    return token_pair(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Refresh token inválido") from exc
    user = db.scalar(
        select(User).where(
            User.id == payload["sub"], User.tenant_id == payload["tenant_id"], User.active.is_(True)
        )
    )
    if not user or user.token_version != payload.get("tv"):
        raise HTTPException(status_code=401, detail="Refresh token inválido")
    return token_pair(user)


@router.post("/logout", status_code=204)
def logout(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user.token_version += 1
    db.commit()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
