import os
import logging
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core import create_tables, check_connection, settings, setup_logging
from app.features.auth.endpoints import router as auth_router
from app.features.members.endpoints import router as members_router
from app.features.forecast.api.endpoints import router as forecast_router
from app.features.forecast.services.retrain import retrain_all_zones
from app.features.ocr.api.endpoints import router as ocr_router, ws_router as ocr_ws_router
from app.features.ocr.services.review_queue import run_pending_review_sweep
from app.features.occupancy.api.endpoints import router as slots_router, ws_router as slots_ws_router

setup_logging()
logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def _run_prophet_retrain_job() -> None:
    """
    Run the Prophet retraining job and log the result
    """
    logger.info("Scheduled Prophet retrain starting...")
    try:
        results = retrain_all_zones()
        logger.info("Scheduled Prophet retrain finished: %s", results)
    except Exception:
        logger.exception("Scheduled Prophet retrain failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
 
    db_ok = check_connection()
    if not db_ok:
        logger.warning("Database connection check failed at startup")
    create_tables()
    logger.info("Database initialized")

    if settings.PROPHET_RETRAIN_ENABLED:
        scheduler.add_job(
            _run_prophet_retrain_job,
            trigger=CronTrigger(hour=settings.PROPHET_RETRAIN_HOUR, minute=settings.PROPHET_RETRAIN_MINUTE),
            id="prophet_retrain",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        logger.info(
            "Prophet retrain scheduled daily at %02d:%02d",
            settings.PROPHET_RETRAIN_HOUR, settings.PROPHET_RETRAIN_MINUTE,
        )
    else:
        logger.info("Prophet retrain scheduler disabled (PROPHET_RETRAIN_ENABLED=false)")

    scheduler.add_job(
        run_pending_review_sweep,
        trigger=IntervalTrigger(seconds=20),
        id="pending_review_sweep",
        replace_existing=True,
        misfire_grace_time=15,
    )
    logger.info("Pending-review reread sweep scheduled every 20s")

    scheduler.start()

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)
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
    