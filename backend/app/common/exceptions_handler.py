import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.common.exceptions import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    NotFoundError: 404,
    ValidationError: 422,
    ConflictError: 409,
    UnauthorizedError: 401,
    ForbiddenError: 403,
}


def register_exception_handlers(app: FastAPI) -> None:
    """Registers exception handlers"""
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        status_code = _STATUS_MAP.get(type(exc), 400)
        logger.warning("AppError [%s]: %s", type(exc).__name__, exc)
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})