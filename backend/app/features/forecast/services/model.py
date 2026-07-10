
import logging
import joblib
from app.core.config import settings
 
logger = logging.getLogger(__name__)
 
_arima_model = None
 
 
def _load_model():
    """
    Lazy-load the fitted ARIMA model once and cache it in memory
    """
    global _arima_model
    if _arima_model is not None:
        return _arima_model
 
    if not settings.ARIMA_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"ARIMA model not found at {settings.ARIMA_MODEL_PATH}. "
            "Make sure arima.joblib is placed in the models/ directory."
        )
 
    logger.info(f"Loading ARIMA model from {settings.ARIMA_MODEL_PATH}")
    _arima_model = joblib.load(settings.ARIMA_MODEL_PATH)
    return _arima_model
 
 
def forecast_next_days(periods: int = 30) -> list[dict]:
    """
    Generate a forward forecast using the pre-trained ARIMA model.
    Returns a list of {step, predicted_demand, lower, upper} dicts.
    """
    model = _load_model()
 
    # statsmodels ARIMAResultsWrapper: get_forecast gives mean + confidence interval
    forecast_result = model.get_forecast(steps=periods)
    mean = forecast_result.predicted_mean
    conf_int = forecast_result.conf_int()
 
    results = []
    for i in range(periods):
        results.append({
            "step": i + 1,
            "predicted_demand": round(float(mean.iloc[i]), 2),
            "lower": round(float(conf_int.iloc[i, 0]), 2),
            "upper": round(float(conf_int.iloc[i, 1]), 2),
        })
    return results