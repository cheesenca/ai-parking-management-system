import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings

# Project Layout 
BASE_DIR = Path(__file__).resolve().parent.parent.parent
APP_DIR = BASE_DIR / "app"
FEATURES_DIR = APP_DIR / "features"

class Settings(BaseSettings):
    # API Metadata
    API_TITLE: str = "AI Parking Management System"
    API_DESCRIPTION: str = "AI Parking Management System Backend API"
    API_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # Core Directories
    MODELS_DIR: Path = BASE_DIR / "models"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Feature: Slot Occupancy 
    SLOT_ROOT: Path = FEATURES_DIR / "occupancy"
    SLOT_DATA_DIR: Path = SLOT_ROOT / "data"
    SLOT_PIPELINE_DIR: Path = SLOT_ROOT / "pipeline"
    PKLOT_DIR: Path = SLOT_PIPELINE_DIR / "dataset" / "pklot"
    CUSTOM_DATASET: Path = SLOT_PIPELINE_DIR / "dataset" / "custom" / "dataset"
    PARKING_MAP_JSON: Path = SLOT_ROOT / "data" / "parking_map.json"

    # Feature: OCR 
    OCR_ROOT: Path = FEATURES_DIR / "ocr"
    OCR_PIPELINE_DIR: Path = OCR_ROOT / "pipeline"

    # Feature: Forecast 
    FORECAST_ROOT: Path = FEATURES_DIR / "forecast"
    FORECAST_DATA_DIR: Path = FORECAST_ROOT / "forecast" / "data"

    # Model Files
    OCCUPANCY_MODEL_PATH: Path = BASE_DIR / "models" / "pytorch" / "pklot.pt"
    OCR_MODEL_PATH: Path = BASE_DIR / "models" / "pytorch" / "parkwise_detector.pt"
    ARIMA_MODEL_PATH: Path = BASE_DIR / "models" / "joblib" / "arima.joblib"
    PROPHET_MODEL_PATH: Path = BASE_DIR / "models" / "joblib" / "prophet.joblib"

    # Perspective / Homography
    HOMOGRAPHY_SRC: Optional[List] = None
    HOMOGRAPHY_W: int = 960
    HOMOGRAPHY_H: int = 540
    HOMOGRAPHY_MATRIX: Path = SLOT_ROOT / "data" / "homography_matrix.npy"

    # YOLO & Inference Hyperparameters
    YOLO_BASE_MODEL: str = "yolov8s.pt"
    YOLO_DEVICE: str = os.getenv("YOLO_DEVICE", "cuda")
    YOLO_IMGSZ: int = 1280
    VEHICLE_CLASSES: List[int] = [2, 3, 5, 7]
    YOLO_CONF: float = float(os.getenv("YOLO_CONF", "0.25"))
    YOLO_IOU_NMS: float = float(os.getenv("YOLO_IOU_NMS", "0.8"))
    IOU_THRESHOLD: float = float(os.getenv("IOU_THRESHOLD", "0.30"))

    # Prophet Retraining 
    PROPHET_MIN_OBSERVATIONS: int = 30
    PROPHET_HOLDOUT_DAYS: int = 7
    PROPHET_OUTLIER_ZSCORE: float = 3.0
    PROPHET_WEEKLY_SEASONALITY: bool = True
    PROPHET_YEARLY_SEASONALITY: bool = False
    PROPHET_DAILY_SEASONALITY: bool = False
    PROPHET_RETRAIN_ENABLED: bool = os.getenv("PROPHET_RETRAIN_ENABLED", "true").lower() == "true"
    PROPHET_RETRAIN_HOUR: int = int(os.getenv("PROPHET_RETRAIN_HOUR", "2"))
    PROPHET_RETRAIN_MINUTE: int = int(os.getenv("PROPHET_RETRAIN_MINUTE", "0"))
    PROPHET_FORECAST_HORIZON_DAYS: int = int(os.getenv("PROPHET_FORECAST_HORIZON_DAYS", "30"))

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

    class Config:
        env_file = ".env"
        extra = "allow"


# Initialize Settings
settings = Settings()


def create_required_directories() -> None:
    """
    Ensures all required system directories exist before application startup
    """
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
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


# Run initialization
create_required_directories()
