import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.request_context import request_id_var

logger = logging.getLogger("oxyn")


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(part) for part in error["loc"] if part != "body"), "message": error["msg"]}
        for error in exc.errors()
    ]
    request_id = getattr(request.state, "request_id", "-")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"error_code": "validation_error", "errors": errors},
        headers={"X-Request-ID": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "-")
    # The contextvar was already reset by the middleware's `finally` block by the
    # time this handler runs (Starlette's ExceptionMiddleware sits outside our
    # custom middleware), so restore it from request.state before logging.
    request_id_var.set(request_id)
    logger.exception("Erro não tratado ao processar %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error_code": "internal_error", "detail": "Erro interno. Tente novamente mais tarde."},
        headers={"X-Request-ID": request_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
