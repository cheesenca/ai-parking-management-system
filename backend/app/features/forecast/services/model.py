import logging
import joblib
from app.core.config import settings
 
logger = logging.getLogger(__name__)
 
_prophet_models: dict | None = None


def reset_cache() -> None:
    """
    Reset the cached Prophet model
    """
    global _prophet_models
    _prophet_models = None
    logger.info("Prophet model cache cleared; next forecast call will reload from disk")

 
def _load_model():
    """
    Lazy-load the fitted Prophet model once and cache it in memory
    """
    global _prophet_models
    if _prophet_models is not None:
        return _prophet_models
 
    if not settings.PROPHET_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Prophet model not found at {settings.PROPHET_MODEL_PATH}"
        )
    logger.info(f"Loading Prophet model(s) from {settings.PROPHET_MODEL_PATH}")
    try:
        loaded = joblib.load(settings.PROPHET_MODEL_PATH)
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"Failed to load {settings.PROPHET_MODEL_PATH}: missing dependency '{exc.name}'"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load {settings.PROPHET_MODEL_PATH}: {exc}"
        ) from exc

    if not isinstance(loaded, dict):
        logger.warning(
            "Loaded Prophet model is not per-zone (legacy format)"
        )
        loaded = {"west": loaded, "east": loaded}
 
    _prophet_models = loaded
    return _prophet_models
 
 
def forecast_next_days(periods: int = 30) -> list[dict]:
    """
    Forecast the next `periods` days of parking demand using the Prophet model
    """
    models = _load_model()
 
    if zone is None:
        zone = "west" if "west" in models else next(iter(models))
    if zone not in models:
        raise KeyError(
            f"No Prophet model available for zone '{zone}'"
            f"Available zones: {list(models.keys())}"
        )
 
    model = models[zone]
    future = model.make_future_dataframe(periods=periods, freq="D", include_history=False)
    forecast = model.predict(future)
 
    results = []
    for i in range(periods):
        row = forecast.iloc[i]
        results.append({
            "step": i + 1,
            "predicted_demand": round(float(row["yhat"]), 2),
            "lower": round(float(row["yhat_lower"]), 2),
            "upper": round(float(row["yhat_upper"]), 2),
        })
    return results
