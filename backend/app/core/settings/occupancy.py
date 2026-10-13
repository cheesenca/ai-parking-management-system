import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings

from app.core.path import BASE_DIR, FEATURES_DIR


class OccupancySettings(BaseSettings):
    SLOT_ROOT: Path = FEATURES_DIR / "occupancy"
    SLOT_DATA_DIR: Path = BASE_DIR / "data" / "occupancy"
    PKLOT_DIR: Path = BASE_DIR / "ml" / "occupancy" / "datasets" / "dataset" / "pklot"
    CUSTOM_DATASET: Path = BASE_DIR / "ml" / "occupancy" / "datasets" / "dataset" / "custom" / "dataset"
    PARKING_MAP_JSON: Path = SLOT_DATA_DIR / "parking_map.json"
    OCCUPANCY_SNAPSHOT_INTERVAL_SEC: int = int(os.getenv("OCCUPANCY_SNAPSHOT_INTERVAL_SEC", "300"))

    OCCUPANCY_MODEL_PATH: Path = BASE_DIR / "models" / "pytorch" / "pklot.pt"

    # Perspective / Homography
    HOMOGRAPHY_SRC: Optional[List] = None
    HOMOGRAPHY_W: int = 960
    HOMOGRAPHY_H: int = 540
    HOMOGRAPHY_MATRIX: Path = SLOT_DATA_DIR / "homography_matrix.npy"

    # YOLO & Inference Hyperparameters
    YOLO_BASE_MODEL: str = "yolov8s.pt"
    YOLO_DEVICE: str = os.getenv("YOLO_DEVICE", "cuda")
    YOLO_IMGSZ: int = 1280
    VEHICLE_CLASSES: List[int] = [2, 3, 5, 7]
    YOLO_CONF: float = float(os.getenv("YOLO_CONF", "0.25"))
    YOLO_IOU_NMS: float = float(os.getenv("YOLO_IOU_NMS", "0.8"))
    IOU_THRESHOLD: float = float(os.getenv("IOU_THRESHOLD", "0.30"))