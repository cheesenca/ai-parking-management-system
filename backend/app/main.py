from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core import create_tables, check_connection
from app.features.occupancy.api.endpoints import router as slots_router
from app.features.ocr.api.endpoints import router as ocr_router, ws_router
from app.features.forecast.api.endpoints import router as forecast_router
from app.features.auth.api.endpoints import router as auth_router
from app.features.members.api.endpoints import router as members_router

check_connection()
create_tables()

app = FastAPI(
    title="AIPS Backend API",
    description="AI Parking System",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(members_router)
app.include_router(slots_router)
app.include_router(ocr_router)
app.include_router(ws_router)    
app.include_router(forecast_router)


@app.get("/")
def root():
    return {"message": "AIPS Backend API", "status": "running", "version": "1.0.0"}


@app.get("/health")
def health():
    db_ok = check_connection()
    return {
        "status":   "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
    }