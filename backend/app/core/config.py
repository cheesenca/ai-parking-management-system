import os
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings

# ── Project layout ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
APP_DIR      = PROJECT_ROOT / "app"
FEATURES_DIR = APP_DIR / "features"

# ── Feature roots (dipakai langsung sebagai modul-level constant) ──────────────
FEATURE_ROOT    = FEATURES_DIR / "occupancy"
PARKING_MAP_JSON = FEATURE_ROOT / "data" / "parking_map.json"

# ── Perspective / homography (dipakai perspective_correction.py) ───────────────
HOMOGRAPHY_SRC: Optional[List] = None   # isi setelah run interactive_calibrate
HOMOGRAPHY_W: int = 960
HOMOGRAPHY_H: int = 540
HOMOGRAPHY_MATRIX: Path = FEATURE_ROOT / "data" / "homography_matrix.npy"

# ── YOLO constants (dipakai occupancy.py) ─────────────────────────────────────
YOLO_BASE_MODEL: str   = "yolov8s.pt"
YOLO_IOU_NMS:   float  = 0.45
YOLO_DEVICE:    str    = "cpu"
YOLO_IMGSZ:     int    = 640
# COCO class ids: car=2, motorcycle=3, bus=5, truck=7
VEHICLE_CLASSES: tuple = (2, 3, 5, 7)


class Settings(BaseSettings):
    # ── Slot occupancy ─────────────────────────────────────────────────────────
    SLOT_ROOT:         Path = FEATURES_DIR / "occupancy"
    SLOT_DATA_DIR:     Path = SLOT_ROOT / "data"
    SLOT_PIPELINE_DIR: Path = SLOT_ROOT / "pipeline"
    PKLOT_DIR:         Path = SLOT_PIPELINE_DIR / "dataset" / "pklot"
    CUSTOM_DATASET:    Path = SLOT_PIPELINE_DIR / "dataset" / "custom" / "dataset"

    # ── OCR ────────────────────────────────────────────────────────────────────
    OCR_ROOT:         Path = FEATURES_DIR / "ocr"
    OCR_PIPELINE_DIR: Path = OCR_ROOT / "pipeline"

    # ── Forecast ───────────────────────────────────────────────────────────────
    FORECAST_ROOT:      Path = FEATURES_DIR / "forecast"
    FORECAST_DATA_DIR:  Path = FORECAST_ROOT / "forecast" / "data"

    # ── Models & logs ──────────────────────────────────────────────────────────
    MODELS_DIR: Path = PROJECT_ROOT / "models"
    LOGS_DIR:   Path = PROJECT_ROOT / "logs"

    # ── Database ───────────────────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://admin:admin_password@localhost:3306/aips_db",
    )

    # ── Model paths ────────────────────────────────────────────────────────────
    YOLO_MODEL_PATH: Path = PROJECT_ROOT / "models" / "pkplot.pt"
    CNN_MODEL_PATH:  Path = PROJECT_ROOT / "models" / "slot_classifier.pth"
    OCR_MODEL_PATH:  Path = PROJECT_ROOT / "models" / "parkwise_detector.pt"

    # ── Hyperparameters ────────────────────────────────────────────────────────
    YOLO_CONF:     float = float(os.getenv("YOLO_CONF",      "0.50"))
    IOU_THRESHOLD: float = float(os.getenv("IOU_THRESHOLD",  "0.30"))

    # ── API ────────────────────────────────────────────────────────────────────
    BACKEND_URL: str   = os.getenv("BACKEND_URL", "http://localhost:8000")
    API_TIMEOUT: float = float(os.getenv("API_TIMEOUT", "0.5"))

    # Derived — dipakai pipeline untuk push data ke API
    @property
    def SLOTS_UPDATE_URL(self) -> str:
        return f"{self.BACKEND_URL}/api/slots/update"

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()


def create_required_directories() -> None:
    directories = [
        settings.SLOT_DATA_DIR,
        settings.MODELS_DIR,
        settings.LOGS_DIR,
        settings.PKLOT_DIR,
        settings.CUSTOM_DATASET / "train" / "occupied",
        settings.CUSTOM_DATASET / "train" / "empty",
        settings.CUSTOM_DATASET / "val"   / "occupied",
        settings.CUSTOM_DATASET / "val"   / "empty",
        settings.FORECAST_DATA_DIR,
        FEATURE_ROOT / "data",                    # untuk parking_map.json & homography
    ]
    for _d in directories:
        _d.mkdir(parents=True, exist_ok=True)


create_required_directories()