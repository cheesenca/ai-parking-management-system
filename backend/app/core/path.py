from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
APP_DIR = BASE_DIR / "app"
FEATURES_DIR = APP_DIR / "features"

__all__ = ["BASE_DIR", "APP_DIR", "FEATURES_DIR"]