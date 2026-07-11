# OXYN Command SaaS — Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the freshly-imported OXYN Command SaaS baseline (auth security, error handling, validation, observability) without adding new subsystems, per `docs/superpowers/specs/2026-07-11-oxyn-hardening-design.md`.

**Architecture:** No structural changes. Same FastAPI + SQLAlchemy + Alembic layout (`app/`, routers per resource, Pydantic schemas). New auth fields live on the existing `User` model; new cross-cutting concerns (errors, logging, rate limiting) get their own small modules under `app/`.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, PyJWT, pwdlib (Argon2), pytest, Python stdlib `logging`/`threading`/`contextvars` (no new dependencies).

## Global Constraints

- No new third-party dependencies — rate limiting and logging use Python stdlib only.
- Keep every existing endpoint path, request/response shape, and role permission unchanged except where a task explicitly says otherwise.
- Error/detail strings stay in Portuguese, matching the existing codebase convention.
- Exactly one Alembic migration for this round (`initial schema`) — the repo has no prior migrations to chain onto.
- Run commands from `/home/caiogoes/oxyn` using the existing venv: `./.venv/bin/python`, `./.venv/bin/pytest`, `./.venv/bin/alembic`, `./.venv/bin/ruff`.
- Commit after each task with `git -c user.name="Caio Goes" -c user.email="caiogoes@humanizare.org" commit`.

---

### Task 1: Auth security columns on `User` + first Alembic migration

**Files:**
- Modify: `app/models.py:5` (import), `app/models.py:69` (User fields)
- Modify: `scripts/bootstrap.py:1-16`
- Modify: `Dockerfile`
- Create: `alembic/versions/<rev>_initial_schema.py` (generated)
- Test: `tests/test_models.py` (new)

**Interfaces:**
- Produces: `User.failed_login_attempts: int`, `User.locked_until: datetime | None`, `User.token_version: int` — consumed by Tasks 2 and 3.

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_models.py -v`
Expected: FAIL with `AttributeError` or `TypeError` (fields don't exist on `User` yet).

- [ ] **Step 3: Add the fields to the model**

In `app/models.py:5`, change:

```python
from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint
```

to:

```python
from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
```

In `app/models.py`, in the `User` class, after the `crm` column (currently line 69: `crm: Mapped[str | None] = mapped_column(String(40), nullable=True)`), add:

```python
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit the model change**

```bash
git add app/models.py tests/test_models.py
git commit -m "Add auth security fields to User model"
```

- [ ] **Step 6: Generate the first Alembic migration**

Run:
```bash
rm -f /tmp/oxyn_alembic_scratch.db
DATABASE_URL="sqlite:////tmp/oxyn_alembic_scratch.db" ./.venv/bin/alembic revision --autogenerate -m "initial schema"
```
Expected: output ending with `Generating /home/caiogoes/oxyn/alembic/versions/<hash>_initial_schema.py ... done`

Open the generated file and confirm it contains an `upgrade()` that creates all 8 tables (`tenants`, `users`, `hospitals`, `operating_rooms`, `shifts`, `safety_checklists`, `alerts`, `audit_logs`) and that the `users` table includes `failed_login_attempts`, `locked_until`, `token_version` columns. If any table or column is missing, the model import in `alembic/env.py` isn't picking up recent changes — re-run Step 6 after confirming `app/models.py` is saved.

- [ ] **Step 7: Verify the migration applies and reverts cleanly**

```bash
DATABASE_URL="sqlite:////tmp/oxyn_alembic_scratch.db" ./.venv/bin/alembic upgrade head
DATABASE_URL="sqlite:////tmp/oxyn_alembic_scratch.db" ./.venv/bin/alembic downgrade base
rm -f /tmp/oxyn_alembic_scratch.db
```
Expected: `upgrade` prints `Running upgrade  -> <hash>, initial schema`; `downgrade` prints `Running downgrade <hash> -> , initial schema`. No tracebacks.

- [ ] **Step 8: Stop using `create_all` in the bootstrap script**

In `scripts/bootstrap.py:6`, change:

```python
from app.db import Base, SessionLocal, engine
```

to:

```python
from app.db import SessionLocal
```

In `scripts/bootstrap.py:16`, remove the line:

```python
    Base.metadata.create_all(engine)
```

so `main()` starts directly with `with SessionLocal() as db:`.

- [ ] **Step 9: Make the Docker image run migrations before bootstrap**

Replace the full contents of `Dockerfile` with:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
COPY scripts ./scripts
COPY alembic.ini ./
COPY alembic ./alembic
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.bootstrap && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

(The old Dockerfile never copied `alembic/`/`alembic.ini` into the image, so `alembic upgrade head` would have failed inside the container — this fixes that alongside wiring it into the startup command.)

- [ ] **Step 10: Run the full test suite to confirm nothing else broke**

Run: `./.venv/bin/pytest -q`
Expected: all tests PASS (test fixtures use `Base.metadata.create_all` directly in `tests/conftest.py`, independent of Alembic, so they're unaffected).

- [ ] **Step 11: Commit**

```bash
git add alembic/versions scripts/bootstrap.py Dockerfile
git commit -m "Add initial Alembic migration; drive schema via migrations, not create_all"
```

---

### Task 2: JWT `token_version` enforcement + `/auth/logout`

**Files:**
- Modify: `app/security.py:21-36`
- Modify: `app/dependencies.py:16-33`
- Modify: `app/routers/auth.py` (all)
- Test: `tests/test_auth.py` (new)

**Interfaces:**
- Consumes: `User.token_version` (Task 1).
- Produces: `create_token(subject, tenant_id, role, token_type, token_version)` — signature change consumed nowhere else outside this task; `POST /api/v1/auth/logout` endpoint.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth.py`:

```python
def test_login_returns_token_pair(client, auth_headers):
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "admin@oxyn.test"


def test_refresh_issues_new_access_token(client):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@oxyn.test", "password": "StrongPass123!"},
    )
    refresh_token = login.json()["refresh_token"]
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()


def test_logout_invalidates_previous_tokens(client):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@oxyn.test", "password": "StrongPass123!"},
    )
    old_access = login.json()["access_token"]
    old_refresh = login.json()["refresh_token"]

    logout = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {old_access}"})
    assert logout.status_code == 204

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"})
    assert me.status_code == 401

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/pytest tests/test_auth.py -v`
Expected: `test_login_returns_token_pair` and `test_refresh_issues_new_access_token` PASS already (existing behavior); `test_logout_invalidates_previous_tokens` FAILS with 404 (no `/auth/logout` route yet).

- [ ] **Step 3: Add `token_version` to token creation**

Replace `create_token` in `app/security.py:21-36` with:

```python
def create_token(subject: str, tenant_id: str, role: str, token_type: str, token_version: int) -> str:
    now = datetime.now(timezone.utc)
    delta = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "type": token_type,
        "tv": token_version,
        "iat": now,
        "exp": now + delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
```

- [ ] **Step 4: Enforce `token_version` in `get_current_user`**

Replace `app/dependencies.py:16-33` with:

```python
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
```

- [ ] **Step 5: Rewrite `app/routers/auth.py` to pass/check `token_version` and add `/logout`**

Replace the full contents of `app/routers/auth.py` with:

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/bin/pytest tests/test_auth.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 7: Run the full suite**

Run: `./.venv/bin/pytest -q`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add app/security.py app/dependencies.py app/routers/auth.py tests/test_auth.py
git commit -m "Add token_version enforcement and /auth/logout endpoint"
```

---

### Task 3: Login lockout after repeated failures

**Files:**
- Modify: `app/config.py:12-13`
- Modify: `app/routers/auth.py` (`login` function)
- Modify: `.env.example`
- Test: `tests/test_auth.py` (append)

**Interfaces:**
- Consumes: `User.failed_login_attempts`, `User.locked_until` (Task 1).
- Produces: `settings.login_max_attempts`, `settings.login_lockout_minutes` — consumed nowhere else this round.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_auth.py`:

```python
from sqlalchemy import select

from app.db import SessionLocal
from app.models import User


def test_lockout_after_max_failed_attempts(client):
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "admin@oxyn.test", "password": "wrong-password"},
        )
        assert response.status_code == 401

    locked = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@oxyn.test", "password": "StrongPass123!"},
    )
    assert locked.status_code == 423


def test_successful_login_resets_failed_attempts(client):
    for _ in range(3):
        client.post(
            "/api/v1/auth/login",
            data={"username": "admin@oxyn.test", "password": "wrong-password"},
        )
    ok = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@oxyn.test", "password": "StrongPass123!"},
    )
    assert ok.status_code == 200

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "admin@oxyn.test"))
        assert user.failed_login_attempts == 0
```

Move the `from sqlalchemy import select`, `from app.db import SessionLocal`, `from app.models import User` lines to the top of `tests/test_auth.py` (above the existing test functions) rather than inline, so the file has one clean import block.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/pytest tests/test_auth.py -v -k "lockout or resets"`
Expected: FAIL — `test_lockout_after_max_failed_attempts` gets 401 instead of 423 on the 6th call (no lockout yet).

- [ ] **Step 3: Add lockout settings**

In `app/config.py`, after line 13 (`refresh_token_days: int = 30`), add:

```python
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
```

- [ ] **Step 4: Implement lockout in `login`**

In `app/routers/auth.py`, add to the imports:

```python
from datetime import datetime, timedelta, timezone
```

and

```python
from app.config import settings
```

Replace the `login` function with:

```python
@router.post("/login", response_model=TokenPair)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower(), User.active.is_(True)))
    invalid_credentials = HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    if not user:
        raise invalid_credentials
    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=423, detail="Conta temporariamente bloqueada. Tente novamente mais tarde.")
    if not verify_password(form.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.login_max_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
        db.commit()
        raise invalid_credentials
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return token_pair(user)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/bin/pytest tests/test_auth.py -v`
Expected: all PASS.

- [ ] **Step 6: Document the new settings**

In `.env.example`, after the `REFRESH_TOKEN_DAYS=30` line, add:

```
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
```

- [ ] **Step 7: Run the full suite**

Run: `./.venv/bin/pytest -q`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add app/config.py app/routers/auth.py tests/test_auth.py .env.example
git commit -m "Lock accounts out after repeated failed login attempts"
```

---

### Task 4: Rate limit `/auth/login` by IP

**Files:**
- Create: `app/rate_limit.py`
- Modify: `app/config.py`
- Modify: `app/routers/auth.py` (`login` function)
- Modify: `tests/conftest.py`
- Modify: `.env.example`
- Test: `tests/test_auth.py` (append)

**Interfaces:**
- Consumes: `settings.login_rate_limit_per_minute`.
- Produces: `app.routers.auth.login_rate_limiter: InMemoryRateLimiter` — consumed by `tests/conftest.py`'s autouse fixture to reset state between tests.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_auth.py`:

```python
def test_login_rate_limited_by_ip(client):
    from app.config import settings

    for _ in range(settings.login_rate_limit_per_minute):
        client.post(
            "/api/v1/auth/login",
            data={"username": "admin@oxyn.test", "password": "wrong-password"},
        )
    blocked = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@oxyn.test", "password": "wrong-password"},
    )
    assert blocked.status_code == 429
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_auth.py -v -k rate_limited`
Expected: FAIL — gets 423 (locked out from Task 3's logic, since 20 failed attempts blows past the 5-attempt lockout) instead of 429. This is expected until the rate limiter runs first.

- [ ] **Step 3: Implement the in-memory limiter**

Create `app/rate_limit.py`:

```python
import threading
import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    """Fixed-window request counter keyed by an arbitrary string (e.g. client IP).

    Single-process only — swap for a Redis-backed limiter before running
    multiple API instances behind a load balancer.
    """

    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
```

- [ ] **Step 4: Add the rate limit setting**

In `app/config.py`, after the `login_lockout_minutes: int = 15` line added in Task 3, add:

```python
    login_rate_limit_per_minute: int = 20
```

- [ ] **Step 5: Wire the limiter into `login`, checked first**

In `app/routers/auth.py`, add to the imports:

```python
from fastapi import APIRouter, Depends, HTTPException, Request
```

(replacing the existing `from fastapi import APIRouter, Depends, HTTPException` line) and:

```python
from app.rate_limit import InMemoryRateLimiter
```

After `router = APIRouter(prefix="/auth", tags=["Autenticação"])`, add:

```python
login_rate_limiter = InMemoryRateLimiter(max_requests=settings.login_rate_limit_per_minute)
```

Replace the `login` function's signature and first line with:

```python
@router.post("/login", response_model=TokenPair)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not login_rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Muitas tentativas de login. Tente novamente em instantes.")
    user = db.scalar(select(User).where(User.email == form.username.lower(), User.active.is_(True)))
```

(the rest of the function body from Task 3 is unchanged).

- [ ] **Step 6: Reset the limiter between tests**

In `tests/conftest.py`, add to the imports:

```python
from app.routers.auth import login_rate_limiter
```

At the start of the `database` fixture body (`tests/conftest.py:15`), before `Base.metadata.drop_all(engine)`, add:

```python
    login_rate_limiter.reset()
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `./.venv/bin/pytest tests/test_auth.py -v`
Expected: all PASS, including `test_login_rate_limited_by_ip`.

- [ ] **Step 8: Document the new setting**

In `.env.example`, after `LOGIN_LOCKOUT_MINUTES=15`, add:

```
LOGIN_RATE_LIMIT_PER_MINUTE=20
```

- [ ] **Step 9: Run the full suite**

Run: `./.venv/bin/pytest -q`
Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add app/rate_limit.py app/config.py app/routers/auth.py tests/conftest.py tests/test_auth.py .env.example
git commit -m "Rate limit /auth/login by client IP"
```

---

### Task 5: Global error handlers

**Files:**
- Create: `app/errors.py`
- Modify: `app/main.py`
- Test: `tests/test_errors.py` (new)

**Interfaces:**
- Produces: `register_error_handlers(app: FastAPI) -> None`, `logger = logging.getLogger("oxyn")` — the same `"oxyn"` logger namespace is used by Task 9's structured logging.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_errors.py`:

```python
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


def test_unhandled_exception_returns_generic_500(client, auth_headers, monkeypatch):
    from app.routers import hospitals

    def boom(*args, **kwargs):
        raise RuntimeError("falha simulada")

    # patches the name as looked up inside hospitals.py at call time,
    # not app.audit.log_action itself
    monkeypatch.setattr(hospitals, "log_action", boom)

    response = client.post(
        "/api/v1/hospitals",
        headers=auth_headers,
        json={"name": "Hospital Instável"},
    )
    assert response.status_code == 500
    assert response.json()["error_code"] == "internal_error"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/pytest tests/test_errors.py -v`
Expected: `test_validation_error_has_structured_body` FAILS (current 422 body is FastAPI's default `{"detail": [...]}`, no `error_code` key); `test_unhandled_exception_returns_generic_500` FAILS by raising `RuntimeError` up through the test client (no handler registered yet).

- [ ] **Step 3: Implement the handlers**

Create `app/errors.py`:

```python
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("oxyn")


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(part) for part in error["loc"] if part != "body"), "message": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error_code": "validation_error", "errors": errors},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erro não tratado ao processar %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error_code": "internal_error", "detail": "Erro interno. Tente novamente mais tarde."},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
```

- [ ] **Step 4: Register the handlers in `main.py`**

In `app/main.py:6`, add to the imports:

```python
from app.errors import register_error_handlers
```

After the `app.add_middleware(CORSMiddleware, ...)` block (`app/main.py:24-30`), add:

```python
register_error_handlers(app)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/bin/pytest tests/test_errors.py -v`
Expected: all PASS.

- [ ] **Step 6: Run the full suite**

Run: `./.venv/bin/pytest -q`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add app/errors.py app/main.py tests/test_errors.py
git commit -m "Add global exception handlers for validation and unhandled errors"
```

---

### Task 6: `ShiftCreate` period validation (moved to schema) + shift flow tests

**Files:**
- Modify: `app/schemas.py:1-3`, `app/schemas.py` (`ShiftCreate` class)
- Modify: `app/routers/shifts.py` (`create_shift`)
- Test: `tests/test_shifts.py` (new)

**Interfaces:**
- No new cross-task interfaces — this is a self-contained validation move.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_shifts.py`:

```python
def _create_hospital_and_room(client, auth_headers):
    hospital = client.post(
        "/api/v1/hospitals",
        headers=auth_headers,
        json={"name": "Hospital Central", "city": "São Paulo"},
    )
    hospital_id = hospital.json()["id"]
    room = client.post(
        f"/api/v1/hospitals/{hospital_id}/rooms",
        headers=auth_headers,
        json={"code": "01", "name": "Sala 01"},
    )
    return hospital_id, room.json()["id"]


def test_shift_end_before_start_is_rejected(client, auth_headers):
    hospital_id, room_id = _create_hospital_and_room(client, auth_headers)
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    response = client.post(
        "/api/v1/shifts",
        headers=auth_headers,
        json={
            "hospital_id": hospital_id,
            "user_id": me["id"],
            "room_id": room_id,
            "shift_date": "2026-07-20",
            "starts_at": "2026-07-20T14:00:00Z",
            "ends_at": "2026-07-20T10:00:00Z",
        },
    )
    assert response.status_code == 422


def test_check_in_then_check_out_flow(client, auth_headers):
    hospital_id, room_id = _create_hospital_and_room(client, auth_headers)
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    shift = client.post(
        "/api/v1/shifts",
        headers=auth_headers,
        json={
            "hospital_id": hospital_id,
            "user_id": me["id"],
            "room_id": room_id,
            "shift_date": "2026-07-20",
            "starts_at": "2026-07-20T07:00:00Z",
            "ends_at": "2026-07-20T19:00:00Z",
        },
    )
    shift_id = shift.json()["id"]

    check_out_early = client.post(f"/api/v1/shifts/{shift_id}/check-out", headers=auth_headers)
    assert check_out_early.status_code == 409

    check_in = client.post(f"/api/v1/shifts/{shift_id}/check-in", headers=auth_headers)
    assert check_in.status_code == 200
    assert check_in.json()["check_in_at"] is not None

    check_out = client.post(f"/api/v1/shifts/{shift_id}/check-out", headers=auth_headers)
    assert check_out.status_code == 200
    assert check_out.json()["check_out_at"] is not None
```

- [ ] **Step 2: Run tests to verify current state**

Run: `./.venv/bin/pytest tests/test_shifts.py -v`
Expected: `test_shift_end_before_start_is_rejected` PASSES already (router-level check exists); `test_check_in_then_check_out_flow` PASSES already too (existing behavior, just newly covered). Both should be green before your change — this confirms the baseline behavior you're about to refactor/preserve.

- [ ] **Step 3: Move the validation into the schema**

In `app/schemas.py:3`, change:

```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field
```

to:

```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
```

Replace the `ShiftCreate` class with:

```python
class ShiftCreate(BaseModel):
    hospital_id: str
    user_id: str
    room_id: str | None = None
    shift_date: date
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def check_period(self) -> "ShiftCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("Término deve ser posterior ao início")
        return self
```

- [ ] **Step 4: Remove the now-redundant router check**

In `app/routers/shifts.py`, remove these two lines from `create_shift`:

```python
    if body.ends_at <= body.starts_at:
        raise HTTPException(status_code=422, detail="Término deve ser posterior ao início")
```

- [ ] **Step 5: Run tests to verify they still pass**

Run: `./.venv/bin/pytest tests/test_shifts.py -v`
Expected: both PASS — `test_shift_end_before_start_is_rejected` now fails via Pydantic's `model_validator` instead of the router's manual check, but still returns 422 (FastAPI turns `ValueError` from a validator into a 422 automatically).

- [ ] **Step 6: Run the full suite**

Run: `./.venv/bin/pytest -q`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add app/schemas.py app/routers/shifts.py tests/test_shifts.py
git commit -m "Move shift period validation to schema; add shift flow tests"
```

---

### Task 7: Prevent resolving an already-resolved alert

**Files:**
- Modify: `app/routers/alerts.py`
- Test: `tests/test_alerts.py` (new)

**Interfaces:** None cross-task.

- [ ] **Step 1: Write the failing test**

Create `tests/test_alerts.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_alerts.py -v`
Expected: FAIL — second resolve currently returns 200.

- [ ] **Step 3: Guard against double resolution**

In `app/routers/alerts.py:3`, change:

```python
from fastapi import APIRouter, Depends
```

to:

```python
from fastapi import APIRouter, Depends, HTTPException
```

Replace `resolve_alert` with:

```python
@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    alert = tenant_object_or_404(db, Alert, alert_id, user.tenant_id)
    if alert.resolved_at is not None:
        raise HTTPException(status_code=409, detail="Alerta já resolvido")
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by_id = user.id
    log_action(db, user, "resolve", "alert", alert.id)
    db.commit()
    db.refresh(alert)
    return alert
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_alerts.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `./.venv/bin/pytest -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routers/alerts.py tests/test_alerts.py
git commit -m "Reject resolving an already-resolved alert"
```

---

### Task 8: Room status transition state machine

**Files:**
- Modify: `app/routers/hospitals.py`
- Test: `tests/test_rooms.py` (new)

**Interfaces:** None cross-task.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rooms.py`:

```python
def _create_hospital_and_room(client, auth_headers):
    hospital = client.post(
        "/api/v1/hospitals",
        headers=auth_headers,
        json={"name": "Hospital Central", "city": "São Paulo"},
    )
    hospital_id = hospital.json()["id"]
    room = client.post(
        f"/api/v1/hospitals/{hospital_id}/rooms",
        headers=auth_headers,
        json={"code": "01", "name": "Sala 01"},
    )
    return hospital_id, room.json()["id"]


def test_valid_room_status_transition_chain(client, auth_headers):
    hospital_id, room_id = _create_hospital_and_room(client, auth_headers)
    for status in ("preparation", "surgery", "recovery", "free"):
        response = client.patch(
            f"/api/v1/hospitals/{hospital_id}/rooms/{room_id}",
            headers=auth_headers,
            json={"status": status},
        )
        assert response.status_code == 200
        assert response.json()["status"] == status


def test_invalid_room_status_transition_is_rejected(client, auth_headers):
    hospital_id, room_id = _create_hospital_and_room(client, auth_headers)
    response = client.patch(
        f"/api/v1/hospitals/{hospital_id}/rooms/{room_id}",
        headers=auth_headers,
        json={"status": "recovery"},
    )
    assert response.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/pytest tests/test_rooms.py -v`
Expected: `test_valid_room_status_transition_chain` PASSES already; `test_invalid_room_status_transition_is_rejected` FAILS (currently returns 200 — any status is accepted from any status).

- [ ] **Step 3: Add the transition table and enforce it**

In `app/routers/hospitals.py:8`, change:

```python
from app.models import Hospital, OperatingRoom, Role, User
```

to:

```python
from app.models import Hospital, OperatingRoom, Role, RoomStatus, User
```

After `router = APIRouter(prefix="/hospitals", tags=["Hospitais e salas"])`, add:

```python
ALLOWED_ROOM_TRANSITIONS: dict[RoomStatus, set[RoomStatus]] = {
    RoomStatus.free: {RoomStatus.preparation, RoomStatus.blocked},
    RoomStatus.preparation: {RoomStatus.surgery, RoomStatus.blocked},
    RoomStatus.surgery: {RoomStatus.recovery, RoomStatus.blocked},
    RoomStatus.recovery: {RoomStatus.free, RoomStatus.blocked},
    RoomStatus.blocked: {RoomStatus.free},
}
```

Replace `update_room` with:

```python
@router.patch("/{hospital_id}/rooms/{room_id}", response_model=RoomOut)
def update_room(
    hospital_id: str,
    room_id: str,
    body: RoomUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.owner, Role.admin, Role.coordinator, Role.anesthetist, Role.nurse)),
):
    room = tenant_object_or_404(db, OperatingRoom, room_id, user.tenant_id)
    if room.hospital_id != hospital_id:
        raise HTTPException(status_code=404, detail="Sala não pertence ao hospital")
    changes = body.model_dump(exclude_unset=True)
    new_status = changes.get("status")
    if new_status is not None and new_status != room.status and new_status not in ALLOWED_ROOM_TRANSITIONS[room.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Transição de status inválida: {room.status.value} → {new_status.value}",
        )
    for key, value in changes.items():
        setattr(room, key, value)
    log_action(db, user, "update", "operating_room", room.id, changes)
    db.commit()
    db.refresh(room)
    return room
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/pytest tests/test_rooms.py -v`
Expected: both PASS.

- [ ] **Step 5: Run the full suite**

Run: `./.venv/bin/pytest -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routers/hospitals.py tests/test_rooms.py
git commit -m "Enforce a room status transition state machine"
```

---

### Task 9: Request-ID middleware, structured logging, auth event logs

**Files:**
- Create: `app/request_context.py`
- Create: `app/logging_config.py`
- Modify: `app/main.py`
- Modify: `app/routers/auth.py`
- Test: `tests/test_observability.py` (new)

**Interfaces:**
- Consumes: `logger = logging.getLogger("oxyn")` namespace convention from Task 5.
- Produces: `request_id_var: contextvars.ContextVar[str]`, `configure_logging() -> None` — not consumed elsewhere this round, but this is the seam future tasks (e.g. a metrics middleware) would hook into.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_observability.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/pytest tests/test_observability.py -v`
Expected: both FAIL — no `X-Request-ID` header yet, no `oxyn.auth` logger emitting yet.

- [ ] **Step 3: Add the request-id contextvar**

Create `app/request_context.py`:

```python
import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
```

- [ ] **Step 4: Add logging configuration**

Create `app/logging_config.py`:

```python
import logging

from app.request_context import request_id_var


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s")
    )
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
```

`addHandler` (not replacing `root.handlers`) is deliberate — it must not remove pytest's own log-capturing handler or any handler uvicorn attaches, only add ours alongside them.

- [ ] **Step 5: Wire the middleware and logging setup into `main.py`**

Replace the full contents of `app/main.py` with:

```python
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.errors import register_error_handlers
from app.logging_config import configure_logging
from app.request_context import request_id_var
from app.routers import alerts, auth, dashboard, hospitals, safety, shifts, users

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API multi-tenant para gestão de serviços de anestesiologia.",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)


@app.middleware("http")
async def add_request_id(request, call_next):
    request_id = str(uuid.uuid4())
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok", "service": "oxyn-command-api"}


for router in (auth.router, users.router, hospitals.router, shifts.router, safety.router, alerts.router, dashboard.router):
    app.include_router(router, prefix="/api/v1")
```

- [ ] **Step 6: Log auth events**

In `app/routers/auth.py`, add to the imports:

```python
import logging
```

After the `router = APIRouter(...)` / `login_rate_limiter = ...` lines, add:

```python
logger = logging.getLogger("oxyn.auth")
```

In the `login` function, add logging at each outcome. The full function becomes:

```python
@router.post("/login", response_model=TokenPair)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not login_rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Muitas tentativas de login. Tente novamente em instantes.")
    user = db.scalar(select(User).where(User.email == form.username.lower(), User.active.is_(True)))
    invalid_credentials = HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    if not user:
        logger.warning("Tentativa de login com e-mail desconhecido: %s", form.username.lower())
        raise invalid_credentials
    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until > now:
        logger.warning("Login bloqueado por lockout: user_id=%s", user.id)
        raise HTTPException(status_code=423, detail="Conta temporariamente bloqueada. Tente novamente mais tarde.")
    if not verify_password(form.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.login_max_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            logger.warning("Usuário bloqueado após tentativas falhas: user_id=%s", user.id)
        db.commit()
        logger.info("Falha de login: user_id=%s attempts=%s", user.id, user.failed_login_attempts)
        raise invalid_credentials
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    logger.info("Login bem-sucedido: user_id=%s", user.id)
    return token_pair(user)
```

And `logout` becomes:

```python
@router.post("/logout", status_code=204)
def logout(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user.token_version += 1
    db.commit()
    logger.info("Logout: user_id=%s", user.id)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `./.venv/bin/pytest tests/test_observability.py -v`
Expected: both PASS.

- [ ] **Step 8: Run the full suite**

Run: `./.venv/bin/pytest -q`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add app/request_context.py app/logging_config.py app/main.py app/routers/auth.py tests/test_observability.py
git commit -m "Add request-id middleware, structured logging, and auth event logs"
```

---

### Task 10: Regression tests — role permissions and tenant isolation

**Files:**
- Modify: `tests/conftest.py`
- Test: `tests/test_permissions.py` (new)

**Interfaces:** None cross-task — pure test coverage of existing, already-correct behavior.

- [ ] **Step 1: Add test fixtures for a second tenant and arbitrary-role users**

In `tests/conftest.py`, add at the end of the file:

```python
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
```

- [ ] **Step 2: Write the tests**

Create `tests/test_permissions.py`:

```python
def test_nurse_cannot_create_hospital(client, user_factory):
    nurse_headers = user_factory("enfermeira@example.com", "nurse")
    response = client.post(
        "/api/v1/hospitals",
        headers=nurse_headers,
        json={"name": "Hospital Sem Permissão"},
    )
    assert response.status_code == 403


def test_viewer_cannot_create_user(client, user_factory):
    viewer_headers = user_factory("visualizador@example.com", "viewer")
    response = client.post(
        "/api/v1/users",
        headers=viewer_headers,
        json={"email": "novo@example.com", "full_name": "Novo", "password": "StrongPass123!", "role": "viewer"},
    )
    assert response.status_code == 403


def test_coordinator_can_create_room_but_not_hospital(client, user_factory, auth_headers):
    hospital = client.post(
        "/api/v1/hospitals",
        headers=auth_headers,
        json={"name": "Hospital Central"},
    )
    hospital_id = hospital.json()["id"]
    coordinator_headers = user_factory("coordenador@example.com", "coordinator")

    forbidden = client.post(
        "/api/v1/hospitals",
        headers=coordinator_headers,
        json={"name": "Hospital Extra"},
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        f"/api/v1/hospitals/{hospital_id}/rooms",
        headers=coordinator_headers,
        json={"code": "01", "name": "Sala 01"},
    )
    assert allowed.status_code == 201


def test_cannot_access_hospital_from_other_tenant(client, auth_headers, other_tenant_auth_headers):
    hospital = client.post(
        "/api/v1/hospitals",
        headers=auth_headers,
        json={"name": "Hospital Privado"},
    )
    hospital_id = hospital.json()["id"]

    response = client.get(f"/api/v1/hospitals/{hospital_id}/rooms", headers=other_tenant_auth_headers)
    assert response.status_code == 404


def test_users_are_isolated_by_tenant(client, auth_headers, other_tenant_auth_headers):
    response = client.get("/api/v1/users", headers=other_tenant_auth_headers)
    assert response.status_code == 200
    emails = [user["email"] for user in response.json()]
    assert "admin@oxyn.test" not in emails
```

- [ ] **Step 3: Run the tests**

Run: `./.venv/bin/pytest tests/test_permissions.py -v`
Expected: all PASS (this documents existing, already-correct role/tenant isolation behavior — if anything fails here, it's a real bug worth stopping on, not a step to "fix forward" silently).

- [ ] **Step 4: Run the full suite**

Run: `./.venv/bin/pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_permissions.py
git commit -m "Add regression tests for role permissions and tenant isolation"
```

---

### Task 11: Final verification and README update

**Files:**
- Modify: `README.md`
- No new tests — this task verifies and documents.

- [ ] **Step 1: Run ruff**

Run: `./.venv/bin/ruff check .`
Expected: no errors. If ruff flags anything (e.g. an unused import left over from earlier tasks), fix it and re-run until clean.

- [ ] **Step 2: Run the full test suite with coverage**

Run: `./.venv/bin/pytest --cov=app -q`
Expected: all tests PASS; note the coverage percentage in your final report to the user.

- [ ] **Step 3: Update the README's Migrações section**

Replace:

```markdown
## Migrações

Para gerar a primeira migração após subir o banco:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

O `scripts.bootstrap` usa `create_all` para facilitar o primeiro teste. Em produção, utilize exclusivamente migrações Alembic.
```

with:

```markdown
## Migrações

O schema é versionado via Alembic desde a migração `initial schema`. Para subir o banco:

```bash
alembic upgrade head
python -m scripts.bootstrap
```

O `scripts.bootstrap` não usa mais `create_all` — ele assume que `alembic upgrade head` já rodou. O `Dockerfile` já executa essa sequência automaticamente no `CMD`.

Para gerar uma nova migração depois de alterar `app/models.py`:

```bash
alembic revision --autogenerate -m "descrição da mudança"
alembic upgrade head
```
```

- [ ] **Step 4: Update the README's security checklist**

In the `## Segurança antes de produção` list, replace:

```markdown
- Adicionar rate limiting, revogação de sessão e MFA para administradores
```

with:

```markdown
- ~~Rate limiting~~ e ~~revogação de sessão~~ implementados (`/auth/logout` + lockout); falta MFA para administradores
```

- [ ] **Step 5: Add the new endpoints to the routes table**

In the `## Rotas principais` table, the `Identidade` row currently reads:

```markdown
| Identidade | `/api/v1/auth` |
```

Leave the table as-is (it documents route prefixes, not every verb) but add a line right below the table:

```markdown
`POST /api/v1/auth/logout` invalida imediatamente todos os tokens emitidos anteriormente para o usuário autenticado.
```

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "Update README for migrations, logout, and security checklist"
```

- [ ] **Step 7: Report to the user**

Summarize: number of commits made, final test count and pass rate, coverage percentage, and remind the user that `.venv/` is local-only (gitignored) — a fresh clone needs `python3 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"` before running tests, and needs a real Postgres (via `docker compose up --build`, which now also runs `alembic upgrade head` automatically) before serving traffic.
