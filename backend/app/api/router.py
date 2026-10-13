from fastapi import APIRouter

from app.core.config import settings
from app.features.auth.endpoints import router as auth_router
from app.features.members.endpoints import router as members_router
from app.features.forecast.api.endpoints import router as forecast_router
from app.features.ocr.api.endpoints import (
    router as ocr_router,
    ws_router as ocr_ws_router,
)
from app.features.occupancy.api.endpoints import (
    router as slots_router,
    ws_router as slots_ws_router,
)

api_router = APIRouter()

api_router.include_router(
    auth_router,
    prefix=f"{settings.API_V1_PREFIX}/auth",
    tags=["Authentication"],
)
api_router.include_router(
    members_router,
    prefix=f"{settings.API_V1_PREFIX}/members",
    tags=["Members"],
)
api_router.include_router(
    slots_router,
    prefix=f"{settings.API_V1_PREFIX}/slots",
    tags=["Slot Occupancy"],
)
api_router.include_router(
    slots_ws_router,
    prefix=f"{settings.API_V1_PREFIX}/slots",
    tags=["Slot Occupancy - WebSocket"],
)
api_router.include_router(
    ocr_router,
    prefix=f"{settings.API_V1_PREFIX}/ocr",
    tags=["OCR"],
)
api_router.include_router(
    ocr_ws_router,
    prefix=f"{settings.API_V1_PREFIX}/ocr",
    tags=["OCR - WebSocket"],
)
api_router.include_router(
    forecast_router,
    prefix=f"{settings.API_V1_PREFIX}/forecast",
    tags=["Forecast"],
)

__all__ = ["api_router"]