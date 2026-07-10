import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
 
from app.core import create_tables, check_connection, settings
from app.features.auth.api import router as auth_router
from app.features.members.api import router as members_router
from app.features.forecast.api.endpoints import router as forecast_router
from app.features.ocr.api.endpoints import router as ocr_router, ws_router as ocr_ws_router
from app.features.occupancy.api.endpoints import router as slots_router, ws_router as slots_ws_router
 
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
 
    db_ok = check_connection()
    if not db_ok:
        logger.warning("Database connection check failed at startup")
    create_tables()
    logger.info("Database initialized")
 
    yield
 
    logger.info("Application shutting down...")
 
 
app = FastAPI(
    title="AI Parking Management System",
    description="AI Parking Management System Backend API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
app.include_router(
    auth_router, 
    prefix=f"{settings.API_V1_PREFIX}/auth", 
    tags=["Authentication"],
)
app.include_router(
    members_router, 
    prefix=f"{settings.API_V1_PREFIX}/members", 
    tags=["Members"],
)
app.include_router(
    slots_router, 
    prefix=f"{settings.API_V1_PREFIX}/slots", 
    tags=["Slot Occupancy"],
)
app.include_router(
    slots_ws_router, 
    prefix=f"{settings.API_V1_PREFIX}/slots", 
    tags=["Slot Occupancy - WebSocket"],
)
app.include_router(
    ocr_router, 
    prefix=f"{settings.API_V1_PREFIX}/ocr", 
    tags=["OCR"],
)
app.include_router(
    ocr_ws_router, 
    prefix=f"{settings.API_V1_PREFIX}/ocr", 
    tags=["OCR - WebSocket"],
)
app.include_router(
    forecast_router, 
    prefix=f"{settings.API_V1_PREFIX}/forecast", 
    tags=["Forecast"],
)

@app.get("/", tags=["Root"])
def root():
    return {
        "message": settings.API_TITLE,
        "description": settings.API_DESCRIPTION,
        "status": "running",
        "version": settings.API_VERSION,
        "features": {
            "auth": "Authentication and authorization",
            "members": "Member management",
            "slots": "Real-time parking slot occupancy detection",
            "ocr": "License plate OCR recognition",
            "forecast": "Parking occupancy forecasting",
        },
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "auth": f"{settings.API_V1_PREFIX}/auth",
            "members": f"{settings.API_V1_PREFIX}/members",
            "slots": f"{settings.API_V1_PREFIX}/slots",
            "ocr": f"{settings.API_V1_PREFIX}/ocr",
            "forecast": f"{settings.API_V1_PREFIX}/forecast",
        },
    }
 
@app.get("/health", tags=["Root"])
def health():
    db_ok = check_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
    }
 
 
if __name__ == "__main__":
    import uvicorn
 
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
