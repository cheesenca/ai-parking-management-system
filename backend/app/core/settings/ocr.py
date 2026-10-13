from pathlib import Path
from pydantic_settings import BaseSettings

from app.core.path import BASE_DIR, FEATURES_DIR


class OcrSettings(BaseSettings):
    OCR_ROOT: Path = FEATURES_DIR / "ocr"
    OCR_PIPELINE_DIR: Path = OCR_ROOT / "pipeline"
    OCR_MODEL_PATH: Path = BASE_DIR / "models" / "pytorch" / "parkwise_detector.pt"