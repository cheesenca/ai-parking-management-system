import os
from pathlib import Path
from pydantic_settings import BaseSettings

from app.core.path import BASE_DIR


class BaseAppSettings(BaseSettings):
    # API Metadata
    API_TITLE: str = "AI Parking Management System"
    API_DESCRIPTION: str = "AI Parking Management System Backend API"
    API_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # Environment / CORS
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]

    # Core Directories
    MODELS_DIR: Path = BASE_DIR / "models"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Database & Network
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:@127.0.0.1:3306/aips_db",
    )
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    API_TIMEOUT: float = float(os.getenv("API_TIMEOUT", "0.5"))

    @property
    def SLOTS_UPDATE_URL(self) -> str:
        return f"{self.BACKEND_URL}/api/slots/update"