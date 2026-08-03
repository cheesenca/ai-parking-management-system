from __future__ import annotations

import logging
from datetime import date, time as dtime, timedelta
from typing import Literal, TypedDict

import joblib
import numpy as np
import pandas as pd
from prophet import Prophet
from sqlalchemy import func
from sqlalchemy.orm import Session
from statsmodels.tsa.arima.model import ARIMA

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.models import AnalyticsData, EntryExitLog, OccupancySnapshot, ParkingZone

logger = logging.getLogger(__name__)

MIN_HISTORY_DAYS = 14
FORECAST_HORIZON_DAYS = 365
ARIMA_ORDER = (5, 1, 0)
DEFAULT_PEAK_START = dtime(8, 0)
DEFAULT_PEAK_END = dtime(9, 0)

PROPHET_ZONE_KEYS = ["west", "east"]


class ZoneRetrainResult(TypedDict):
    status: Literal["ok", "insufficient_data", "error"]
    rows_written: int
    detail: str


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


def _build_daily_series(db: Session, zone_id: int) -> pd.DataFrame:
    """
    Aggregates EntryExitLog + OccupancySnapshot into one daily-indexed frame for a zone.
    """
    day_expr = func.date(EntryExitLog.event_timestamp)
    demand_rows = (
        db.query(day_expr.label("d"), func.count().label("demand"))
        .filter(EntryExitLog.zone_id == zone_id, EntryExitLog.event_type == "Entry")
        .group_by(day_expr)
        .order_by(day_expr)
        .all()
    )
    demand_df = pd.DataFrame(demand_rows, columns=["d", "demand"])
    if demand_df.empty:
        return demand_df
    demand_df["d"] = pd.to_datetime(demand_df["d"])

    occ_day_expr = func.date(OccupancySnapshot.recorded_at)
    occ_rows = (
        db.query(
            occ_day_expr.label("d"),
            func.avg(OccupancySnapshot.overall_rate_pct).label("avg_rate"),
            func.avg(OccupancySnapshot.employee_used).label("employee_used"),
            func.avg(OccupancySnapshot.vendor_used).label("vendor_used"),
            func.avg(OccupancySnapshot.visitor_used).label("visitor_used"),
        )
        .filter(OccupancySnapshot.zone_id == zone_id)
        .group_by(occ_day_expr)
        .all()
    )
    occ_df = pd.DataFrame(occ_rows, columns=["d", "avg_rate", "employee_used", "vendor_used", "visitor_used"])
    if not occ_df.empty:
        occ_df["d"] = pd.to_datetime(occ_df["d"])

    return demand_df.merge(occ_df, on="d", how="left").sort_values("d").reset_index(drop=True)


def _fit_and_forecast(series: pd.Series, steps: int) -> list[float] | None:
    try:
        fit = ARIMA(series.values, order=ARIMA_ORDER).fit()
        return [float(v) for v in fit.forecast(steps=steps)]
    except Exception as exc:
        logger.warning("ARIMA fit/forecast failed: %s", exc)
        return None


def _peak_hour(db: Session, zone_id: int) -> tuple[dtime, dtime]:
    """
    Mean occupancy by hour-of-day from OccupancySnapshot, falling back to the
    EntryExitLog Entry-hour histogram, then a static default. ARIMA gives no
    intraday shape, so one value is computed and reused across the whole horizon.
    """
    hour_expr = func.hour(OccupancySnapshot.recorded_at)
    rows = (
        db.query(hour_expr.label("h"), func.avg(OccupancySnapshot.total_occupied).label("avg_occ"))
        .filter(OccupancySnapshot.zone_id == zone_id)
        .group_by(hour_expr)
        .all()
    )
    if rows:
        best = max(rows, key=lambda r: r.avg_occ or -1).h
        return dtime(int(best)), dtime((int(best) + 1) % 24)

    hour_expr2 = func.hour(EntryExitLog.event_timestamp)
    rows2 = (
        db.query(hour_expr2.label("h"), func.count().label("cnt"))
        .filter(EntryExitLog.zone_id == zone_id, EntryExitLog.event_type == "Entry")
        .group_by(hour_expr2)
        .all()
    )
    if rows2:
        best = max(rows2, key=lambda r: r.cnt).h
        return dtime(int(best)), dtime((int(best) + 1) % 24)

    return DEFAULT_PEAK_START, DEFAULT_PEAK_END


def _avg_occupancy_rate(daily: pd.DataFrame, window: int = 14) -> float:
    recent = daily.tail(window)
    if "avg_rate" in recent and recent["avg_rate"].notna().any():
        return round(float(recent["avg_rate"].dropna().mean()), 1)
    return 0.0


def _category_ratio(zone: ParkingZone, daily: pd.DataFrame, window: int = 14) -> tuple[float, float, float]:
    """
    Prefers recent real OccupancySnapshot category proportions; falls back to the
    zone's static capacity ratio when no snapshot data exists yet.
    """
    recent = daily.tail(window)
    cols = ["employee_used", "vendor_used", "visitor_used"]
    if all(c in recent.columns for c in cols) and recent[cols].notna().any().any():
        means = recent[cols].mean(skipna=True).fillna(0)
        if means.sum() > 0:
            return (float(means["employee_used"]), float(means["vendor_used"]), float(means["visitor_used"]))
    return (float(zone.employee_capacity), float(zone.vendor_capacity), float(zone.visitor_capacity))


def _upsert_analytics(
    db: Session,
    zone_id: int,
    record_date: date,
    peak_start: dtime,
    peak_end: dtime,
    avg_rate: float,
    demand: int,
    emp: int,
    ven: int,
    vis: int,
) -> None:
    row = (
        db.query(AnalyticsData)
        .filter(AnalyticsData.zone_id == zone_id, AnalyticsData.record_date == record_date)
        .first()
    )
    if row is None:
        row = AnalyticsData(zone_id=zone_id, record_date=record_date)
        db.add(row)

    row.peak_hour_start = peak_start
    row.peak_hour_end = peak_end
    row.avg_occupancy_rate = avg_rate
    row.predicted_demand = demand
    row.predicted_employee = emp
    row.predicted_vendor = ven
    row.predicted_visitor = vis


def retrain_zone(db: Session, zone: ParkingZone) -> ZoneRetrainResult:
    daily = _build_daily_series(db, zone.zone_id)
    if daily.empty or len(daily) < MIN_HISTORY_DAYS:
        days = 0 if daily.empty else len(daily)
        return {"status": "insufficient_data", "rows_written": 0, "detail": f"only {days} day(s) of history"}

    series = daily.set_index("d")["demand"].asfreq("D").fillna(0)

    # Bridge the gap between the last observed day and today so forecasted dates
    # land in the future (dashboard filters on record_date >= since) instead of
    # being labeled starting right after a stale last-observed date.
    last_observed = series.index.max().date()
    today = date.today()
    gap_days = max(0, (today - last_observed).days)
    total_steps = gap_days + FORECAST_HORIZON_DAYS

    forecast_values = _fit_and_forecast(series, total_steps)
    if forecast_values is None:
        return {"status": "error", "rows_written": 0, "detail": "ARIMA fit failed"}

    horizon_values = forecast_values[gap_days:]
    target_dates = [today + timedelta(days=i + 1) for i in range(FORECAST_HORIZON_DAYS)]

    peak_start, peak_end = _peak_hour(db, zone.zone_id)
    avg_rate = _avg_occupancy_rate(daily)
    ratio = _category_ratio(zone, daily)

    rows_written = 0
    for target_date, value in zip(target_dates, horizon_values):
        demand = max(0, round(value))
        emp, ven, vis = _category_split(demand, *ratio)
        _upsert_analytics(db, zone.zone_id, target_date, peak_start, peak_end, avg_rate, demand, emp, ven, vis)
        rows_written += 1

    db.commit()
    return {"status": "ok", "rows_written": rows_written, "detail": f"gap_days={gap_days}"}


def combine_eastwest(
    db: Session,
    west_zone: ParkingZone,
    east_zone: ParkingZone,
    eastwest_zone: ParkingZone,
    target_dates: list[date],
) -> ZoneRetrainResult:
    """
    eastwest has no camera of its own — its forecast is the sum of west + east.
    """
    rows_written = 0
    for d in target_dates:
        w = db.query(AnalyticsData).filter(
            AnalyticsData.zone_id == west_zone.zone_id, AnalyticsData.record_date == d
        ).first()
        e = db.query(AnalyticsData).filter(
            AnalyticsData.zone_id == east_zone.zone_id, AnalyticsData.record_date == d
        ).first()
        if w is None or e is None:
            continue

        w_cap, e_cap = west_zone.total_capacity or 0, east_zone.total_capacity or 0
        cap_sum = w_cap + e_cap
        avg_rate = round((w.avg_occupancy_rate * w_cap + e.avg_occupancy_rate * e_cap) / cap_sum, 1) if cap_sum else 0.0

        _upsert_analytics(
            db,
            eastwest_zone.zone_id,
            d,
            min(w.peak_hour_start, e.peak_hour_start),
            max(w.peak_hour_end, e.peak_hour_end),
            avg_rate,
            w.predicted_demand + e.predicted_demand,
            w.predicted_employee + e.predicted_employee,
            w.predicted_vendor + e.predicted_vendor,
            w.predicted_visitor + e.predicted_visitor,
        )
        rows_written += 1

    db.commit()
    if rows_written == 0:
        return {"status": "insufficient_data", "rows_written": 0, "detail": "no overlapping west/east rows"}
    return {"status": "ok", "rows_written": rows_written, "detail": f"combined {rows_written} date(s)"}


def retrain_all_zones_arima(db: Session) -> dict[str, ZoneRetrainResult]:
    """
    Retrains the ARIMA-based demand forecast (AnalyticsData) for every zone.
    """
    zones = {z.zone_key: z for z in db.query(ParkingZone).all()}
    results: dict[str, ZoneRetrainResult] = {}

    for key in ("west", "east"):
        zone = zones.get(key)
        if zone is None:
            results[key] = {"status": "error", "rows_written": 0, "detail": f"zone '{key}' not seeded"}
            continue
        try:
            results[key] = retrain_zone(db, zone)
        except Exception as exc:
            db.rollback()
            logger.exception("Retrain failed for zone '%s'", key)
            results[key] = {"status": "error", "rows_written": 0, "detail": str(exc)}

    eastwest_zone = zones.get("eastwest")
    if eastwest_zone and results.get("west", {}).get("status") == "ok" and results.get("east", {}).get("status") == "ok":
        target_dates = [date.today() + timedelta(days=i + 1) for i in range(FORECAST_HORIZON_DAYS)]
        try:
            results["eastwest"] = combine_eastwest(db, zones["west"], zones["east"], eastwest_zone, target_dates)
        except Exception as exc:
            db.rollback()
            logger.exception("Combining eastwest forecast failed")
            results["eastwest"] = {"status": "error", "rows_written": 0, "detail": str(exc)}
    elif eastwest_zone:
        results["eastwest"] = {"status": "insufficient_data", "rows_written": 0, "detail": "west/east not both ok"}

    return results


def run_scheduled_retrain() -> None:
    db = SessionLocal()
    try:
        results = retrain_all_zones_arima(db)
        logger.info("Scheduled retrain complete: %s", results)
    except Exception:
        logger.exception("Scheduled retrain crashed")
    finally:
        db.close()


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


def _build_prophet_daily_series(db, zone_id: int) -> pd.Series:
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
    db = SessionLocal()
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

            raw_series = _build_prophet_daily_series(db, zone_id)
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

        return results
    finally:
        db.close()
