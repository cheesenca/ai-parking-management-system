import os
from pathlib import Path
from pydantic_settings import BaseSettings

from app.core.path import BASE_DIR, FEATURES_DIR


class ForecastSettings(BaseSettings):
    FORECAST_ROOT: Path = FEATURES_DIR / "forecast"
    FORECAST_DATA_DIR: Path = FORECAST_ROOT / "forecast" / "data"

    ARIMA_MODEL_PATH: Path = BASE_DIR / "models" / "joblib" / "arima.joblib"
    PROPHET_MODEL_PATH: Path = BASE_DIR / "models" / "joblib" / "prophet.joblib"

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