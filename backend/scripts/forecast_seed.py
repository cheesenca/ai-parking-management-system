"""
Usage: python -m scripts.forecast_seed
"""

import logging
import pandas as pd
from datetime import date, time
from pathlib import Path

from app.core.database import SessionLocal, create_tables
from app.core.models import AnalyticsData
from app.features.forecast.models import AREA_CODES, AREA_ZONE_ID_MAP, AREA_LOCATION_MAP

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "features" / "forecast" / "data"

_DEFAULT_PEAK_START = time(0, 0)
_DEFAULT_PEAK_END = time(0, 0)

_STATUS_RANK = {
    "Normal": 0, 
    "Warning": 1, 
    "Full": 2
}

EASTWEST_ZONE_ID = 3


def _worst_status(statuses: list[str]) -> str:
    """
    Returns the worst status from a list of statuses, based on the defined
    """
    return max(statuses, key=lambda s: _STATUS_RANK.get(s, 0)) if statuses else "Normal"


def _occupancy_rate(predicted: float, available: float) -> float:
    """
    Computes the occupancy rate as a percentage of predicted demand over total capacity
    """
    capacity = predicted + available
    if capacity <= 0:
        return 0.0
    return round(min(100.0, (predicted / capacity) * 100), 2)


def _clean_area_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures that all expected area columns exist in the DataFrame
    """
    for area in AREA_CODES:
        for suffix in ("_predicted", "_available"):
            col = f"{area}{suffix}"
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0) if col in df.columns else 0
        col = f"{area}_status"
        df[col] = df[col].fillna("Normal") if col in df.columns else "Normal"
    return df


def _upsert_row(
    session, *,
    period_type: str,
    record_date: date,
    period_label: str | None,
    zone_id: int,
    area: str | None,
    predicted: float,
    available: float,
    status: str,
) -> None:
    """
    Inserts or updates a row in the analytics_data table for the given period, area, and zone
    """
    obj = (
        session.query(AnalyticsData)
        .filter(
            AnalyticsData.period_type == period_type,
            AnalyticsData.area_code == area,
            AnalyticsData.record_date == record_date,
            AnalyticsData.zone_id == zone_id,
        )
        .first()
    )
    if obj is None:
        obj = AnalyticsData(
            period_type=period_type,
            area_code=area,
            record_date=record_date,
            zone_id=zone_id,
            peak_hour_start=_DEFAULT_PEAK_START,
            peak_hour_end=_DEFAULT_PEAK_END,
        )
        session.add(obj)
    obj.zone_id = zone_id
    obj.period_label = period_label
    obj.predicted_demand = round(predicted)
    obj.predicted_available = round(available)
    obj.status = status
    obj.avg_occupancy_rate = _occupancy_rate(predicted, available)


def _seed_period(session, df: pd.DataFrame, period_type: str, row_to_key) -> int:
    """
    Seeds the analytics_data table for a given period type
    """
    count = 0
    for _, row in df.iterrows():
        record_date, period_label = row_to_key(row)

        west_predicted = west_available = east_predicted = east_available = 0.0
        west_statuses: list[str] = []
        east_statuses: list[str] = []

        for area in AREA_CODES:
            predicted = row[f"{area}_predicted"]
            available = row[f"{area}_available"]
            status = row[f"{area}_status"]

            _upsert_row(
                session,
                period_type=period_type,
                record_date=record_date,
                period_label=period_label,
                zone_id=AREA_ZONE_ID_MAP[area],
                area=area,
                predicted=predicted,
                available=available,
                status=status,
            )
            count += 1

            if AREA_LOCATION_MAP[area] == "west":
                west_predicted += predicted
                west_available += available
                west_statuses.append(status)
            else:
                east_predicted += predicted
                east_available += available
                east_statuses.append(status)

        # Combined "East & West" summary row for this date/period
        _upsert_row(
            session,
            period_type=period_type,
            record_date=record_date,
            period_label=period_label,
            zone_id=EASTWEST_ZONE_ID,
            area=None,
            predicted=west_predicted + east_predicted,
            available=west_available + east_available,
            status=_worst_status(west_statuses + east_statuses),
        )
        count += 1

    session.commit()
    return count


def seed_daily(session) -> int:
    """
    Seed the daily forecast data from CSV into the analytics_data table
    """
    df = pd.read_csv(DATA_DIR / "daily_forecast.csv")
    df["ds"] = pd.to_datetime(df["ds"]).dt.date
    df = _clean_area_cols(df)
    return _seed_period(session, df, "daily", lambda row: (row["ds"], None))


def seed_weekly(session) -> int:
    """
    Seed the weekly forecast data from CSV into the analytics_data table
    """
    df = pd.read_csv(DATA_DIR / "weekly_forecast.csv")
    df = _clean_area_cols(df)

    def key(row):
        year, week = int(row["year"]), int(row["week"])
        return date.fromisocalendar(year, week, 1), f"{year}-W{week}"

    return _seed_period(session, df, "weekly", key)


def seed_monthly(session) -> int:
    """
    Seed the monthly forecast data from CSV into the analytics_data table
    """
    df = pd.read_csv(DATA_DIR / "monthly_forecast.csv")
    df = _clean_area_cols(df)

    def key(row):
        year, month = int(row["year"]), int(row["month"])
        return date(year, month, 1), f"{year}-{month:02d}"

    return _seed_period(session, df, "monthly", key)


def run():
    """
    Seed the analytics_data table with daily, weekly, and monthly forecast data
    """
    create_tables()
    session = SessionLocal()
    try:
        d = seed_daily(session)
        w = seed_weekly(session)
        m = seed_monthly(session)
        print(f"Daily forecast seeded: {d} rows (per-area + East&West combined)")
        print(f"Weekly forecast seeded: {w} rows (per-area + East&West combined)")
        print(f"Monthly forecast seeded: {m} rows (per-area + East&West combined)")
        print("All rows written into the existing analytics_data table (no extra tables).")
    finally:
        session.close()


if __name__ == "__main__":
    run()