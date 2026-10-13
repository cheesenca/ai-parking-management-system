from __future__ import annotations

import logging
from datetime import date, timedelta

import joblib
import numpy as np
import pandas as pd
from prophet import Prophet

from app.core.config import settings
<<<<<<< HEAD
from app.core.database import SessionLocal
from app.core.models import AnalyticsData, OccupancySnapshot, ParkingZone
=======
from app.db.session import session_local
from app.db.models import AnalyticsData, OccupancySnapshot, ParkingZone
>>>>>>> origin/master

logger = logging.getLogger(__name__)

PROPHET_ZONE_KEYS = ["west", "east"]
AREA_ZONE_MAP = {
    "P1W": "west", "P2W": "west", "P3W": "west",
    "P1E": "east", "P2E": "east", "P3E": "east",
}


def _category_split(total: float, employee_cap: float, vendor_cap: float, visitor_cap: float) -> tuple[int, int, int]:
    """
    Proportionally splits `total` across three categories with largest-remainder
    rounding so the parts always sum exactly to `total`.
    """
    total = max(0, round(total))
    if total == 0:
        return (0, 0, 0)

    caps = [max(0.0, employee_cap), max(0.0, vendor_cap), max(0.0, visitor_cap)]
    cap_sum = sum(caps)
    if cap_sum == 0:
        return (total, 0, 0)

    raw = [total * c / cap_sum for c in caps]
    floors = [int(x) for x in raw]
    remainder = total - sum(floors)
    order = sorted(range(3), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in order[:remainder]:
        floors[i] += 1
    return (floors[0], floors[1], floors[2])


def _zone_ids_by_key(db) -> dict[str, int]:
    """
    Returns a dict mapping zone_key to zone_id for west/east zones
    """
    rows = (
        db.query(ParkingZone.zone_key, ParkingZone.zone_id)
        .filter(ParkingZone.zone_key.in_(PROPHET_ZONE_KEYS))
        .all()
    )
    return {key: zid for key, zid in rows}


def _build_daily_series(db, zone_id: int) -> pd.Series:
    """
    Builds a daily time series of occupancy rates for the given zone_id
    """
    rows = (
        db.query(OccupancySnapshot.recorded_at, OccupancySnapshot.overall_rate_pct)
        .filter(OccupancySnapshot.zone_id == zone_id)
        .order_by(OccupancySnapshot.recorded_at.asc())
        .all()
    )
    if not rows:
        return pd.Series(dtype=float)

    df = pd.DataFrame(rows, columns=["recorded_at", "overall_rate_pct"])
    df["date"] = pd.to_datetime(df["recorded_at"]).dt.date
    daily = df.groupby("date")["overall_rate_pct"].mean()
    daily.index = pd.to_datetime(daily.index)
    daily = daily.asfreq("D")
    daily = daily.interpolate(limit_direction="both")
    return daily


def _clip_outliers(series: pd.Series, z_thresh: float) -> pd.Series:
    """
    Clips outliers in the series that are more than z_thresh standard deviationss
    """
    if series.std(ddof=0) == 0 or len(series) < 3:
        return series
    mean, std = series.mean(), series.std(ddof=0)
    lower, upper = mean - z_thresh * std, mean + z_thresh * std
    n_clipped = int(((series < lower) | (series > upper)).sum())
    if n_clipped:
        logger.info("Clipped %d outlier day(s) outside [%.2f, %.2f]", n_clipped, lower, upper)
    return series.clip(lower=lower, upper=upper)


def _series_to_prophet_df(series: pd.Series) -> pd.DataFrame:
    """
    Converts a pandas Series to the format required by Prophet (columns 'ds' and 'y')
    """
    return pd.DataFrame({"ds": series.index, "y": series.values})


def _fit_prophet(series: pd.Series) -> Prophet:
    """
    Fits a Prophet model to the given daily time series
    """
    model = Prophet(
        weekly_seasonality=settings.PROPHET_WEEKLY_SEASONALITY,
        yearly_seasonality=settings.PROPHET_YEARLY_SEASONALITY,
        daily_seasonality=settings.PROPHET_DAILY_SEASONALITY,
    )
    model.fit(_series_to_prophet_df(series))
    return model


def _forecast_prophet(model: Prophet, steps: int) -> np.ndarray:
    """
    Forecasts the next `steps` days using the given Prophet model
    """
    future = model.make_future_dataframe(periods=steps, freq="D", include_history=False)
    forecast = model.predict(future)
    return forecast["yhat"].values[-steps:]


def _mae(actual: pd.Series, predicted: np.ndarray) -> float:
    """
    Computes the Mean Absolute Error between actual and predicted values
    """
    return float(np.mean(np.abs(actual.values - predicted)))


def _naive_seasonal_baseline(series: pd.Series, holdout_days: int) -> np.ndarray:
    """
    Returns a naive seasonal baseline forecast for the last `holdout_days` of the series
    """
    season = 7
    train = series.iloc[:-holdout_days]
    if len(train) < season:
        return np.full(holdout_days, train.iloc[-1])
    return train.iloc[-season:].values[:holdout_days] if season >= holdout_days else np.resize(train.iloc[-season:].values, holdout_days)


def _validate_candidate(series: pd.Series, zone_key: str, existing_models: dict) -> tuple[bool, dict]:
    """
    Validates a candidate Prophet model against the naive seasonal baseline and the previous model
    """
    holdout = settings.PROPHET_HOLDOUT_DAYS
    if len(series) < settings.PROPHET_MIN_OBSERVATIONS + holdout:
        return False, {"reason": "not_enough_data_for_holdout"}

    train, test = series.iloc[:-holdout], series.iloc[-holdout:]

    candidate = _fit_prophet(train)
    candidate_pred = _forecast_prophet(candidate, holdout)
    candidate_mae = _mae(test, candidate_pred)

    baseline_pred = _naive_seasonal_baseline(series, holdout)
    baseline_mae = _mae(test, baseline_pred)

    metrics = {
        "candidate_mae": round(candidate_mae, 3),
        "naive_baseline_mae": round(baseline_mae, 3),
    }

    if candidate_mae > baseline_mae:
        metrics["reason"] = "worse_than_naive_baseline"
        return False, metrics

    old_model = existing_models.get(zone_key)
    if old_model is not None:
        try:
            old_pred = _forecast_prophet(old_model, holdout)
            old_mae = _mae(test, old_pred)
            metrics["previous_model_mae"] = round(old_mae, 3)
            if candidate_mae > old_mae:
                metrics["reason"] = "worse_than_previous_model"
                return False, metrics
        except Exception as exc:
            logger.warning("Could not evaluate previous model for zone '%s': %s", zone_key, exc)

    metrics["reason"] = "passed_validation"
    return True, metrics


def _load_existing_models() -> dict:
    """
    Loads existing Prophet models from disk if available, otherwise returns an empty dict
    """
    if not settings.PROPHET_MODEL_PATH.exists():
        return {}
    try:
        loaded = joblib.load(settings.PROPHET_MODEL_PATH)
        return loaded if isinstance(loaded, dict) else {}
    except Exception as exc:
        logger.warning("Could not load existing models, starting fresh: %s", exc)
        return {}


def retrain_all_zones() -> dict[str, dict]:
    """
    Retrains Prophet models for all zones and saves them to disk
    """
<<<<<<< HEAD
    db = SessionLocal()
=======
    db = session_local()
>>>>>>> origin/master
    try:
        zone_ids = _zone_ids_by_key(db)
        existing_models = _load_existing_models()
        models = dict(existing_models)
        results: dict[str, dict] = {}

        for zone_key in PROPHET_ZONE_KEYS:
            zone_id = zone_ids.get(zone_key)
            if zone_id is None:
                logger.warning("Zone '%s' not found in parking_zone table, skipping", zone_key)
                results[zone_key] = {"status": "skipped", "reason": "zone_not_found"}
                continue

            raw_series = _build_daily_series(db, zone_id)
            if len(raw_series) < settings.PROPHET_MIN_OBSERVATIONS:
                logger.info(
                    "Zone '%s': only %d daily point(s), need >= %d. Keeping existing model",
                    zone_key, len(raw_series), settings.PROPHET_MIN_OBSERVATIONS,
                )
                results[zone_key] = {
                    "status": "skipped",
                    "reason": "insufficient_data",
                    "n_points": len(raw_series),
                }
                continue

            series = _clip_outliers(raw_series, settings.PROPHET_OUTLIER_ZSCORE)

            passed, metrics = _validate_candidate(series, zone_key, existing_models)
            if not passed:
                logger.warning("Zone '%s': candidate REJECTED (%s). Keeping existing model.", zone_key, metrics)
                results[zone_key] = {"status": "rejected", **metrics}
                continue

            logger.info("Zone '%s': candidate PASSED validation (%s). Refitting on full data...", zone_key, metrics)
            final_model = _fit_prophet(series)
            models[zone_key] = final_model
            results[zone_key] = {"status": "retrained", "n_points": len(series), **metrics}

        settings.PROPHET_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(models, settings.PROPHET_MODEL_PATH)
        logger.info("Saved Prophet models for zones %s to %s", list(models.keys()), settings.PROPHET_MODEL_PATH)

        from app.features.forecast.services import model as model_service
        model_service.reset_cache()

        try:
            sync_forecast_to_analytics_data(db, zone_ids, horizon_days=settings.PROPHET_FORECAST_HORIZON_DAYS)
        except Exception as exc:
            logger.exception("Failed to sync forecast into analytics_data: %s", exc)

        return results
    finally:
        db.close()


def sync_forecast_to_analytics_data(db, zone_ids: dict[str, int], horizon_days: int = 30) -> None:
    """
    Syncs the Prophet forecast into the analytics_data table for all zones and areas
    """
    from app.features.forecast.services.model import forecast_next_days

    today = date.today()

    for area, zone_key in AREA_ZONE_MAP.items():
        zone_id = zone_ids.get(zone_key)
        if zone_id is None:
            continue

        try:
            forecast_rows = forecast_next_days(periods=horizon_days, zone=zone_key)
        except (FileNotFoundError, KeyError) as exc:
            logger.warning("Skipping analytics_data sync for zone '%s': %s", zone_key, exc)
            continue

        for row in forecast_rows:
            record_date = today + timedelta(days=row["step"])
            predicted_demand = max(0, round(row["predicted_demand"] / 3))

            existing = (
                db.query(AnalyticsData)
                .filter_by(zone_id=zone_id, record_date=record_date, period_type="daily", area_code=area)
                .first()
            )
            if existing is None:
                existing = AnalyticsData(
                    zone_id=zone_id,
                    record_date=record_date,
                    period_type="daily",
                    area_code=area,
                    peak_hour_start="08:00:00",
                    peak_hour_end="17:00:00",
                    avg_occupancy_rate=0.0,
                    predicted_employee=0,
                    predicted_vendor=0,
                    predicted_visitor=0,
                )
                db.add(existing)

            existing.predicted_demand = predicted_demand
            existing.predicted_available = max(0, 300 - predicted_demand)
            existing.status = (
                "Full" if predicted_demand >= 300
                else "Warning" if predicted_demand >= 240
                else "Normal"
            )

        db.commit()

    logger.info("Synced Prophet forecast into analytics_data for %d areas, %d days ahead", len(AREA_ZONE_MAP), horizon_days)
