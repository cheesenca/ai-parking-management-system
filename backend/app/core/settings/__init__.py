from pydantic_settings import SettingsConfigDict

from app.core.path import BASE_DIR

from .base import BaseAppSettings
from .occupancy import OccupancySettings
from .ocr import OcrSettings
from .forecast import ForecastSettings


class Settings(BaseAppSettings, OccupancySettings, OcrSettings, ForecastSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")


settings = Settings()


def create_required_directories() -> None:
    """Ensures all required system directories exist before application startup"""
    directories = [
        settings.SLOT_ROOT,
        settings.SLOT_DATA_DIR,
        settings.MODELS_DIR,
        settings.LOGS_DIR,
        settings.PKLOT_DIR,
        settings.CUSTOM_DATASET / "train" / "occupied",
        settings.CUSTOM_DATASET / "train" / "empty",
        settings.CUSTOM_DATASET / "val" / "occupied",
        settings.CUSTOM_DATASET / "val" / "empty",
        settings.FORECAST_DATA_DIR,
        BASE_DIR / "data" / "occupancy" / "calibration",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


create_required_directories()

__all__ = ["settings", "Settings", "create_required_directories"]