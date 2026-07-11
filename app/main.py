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
