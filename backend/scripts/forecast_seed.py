"""
Usage: python -m scripts.forecast_seed
"""

import logging
import pandas as pd
from datetime import date, time
from pathlib import Path

from app.core.database import SessionLocal, create_tables
from app.core.models import AnalyticsData
from app.features.forecast.models import AREA_CODES, AREA_ZONE_ID_MAP

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "features" / "forecast" / "data"

_DEFAULT_PEAK_START = time(0, 0)
_DEFAULT_PEAK_END = time(0, 0)


def _clean_area_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures that all expected area columns exist in the DataFrame, filling missing
    """
    for area in AREA_CODES:
        for suffix in ("_predicted", "_available"):
            col = f"{area}{suffix}"
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0) if col in df.columns else 0
        col = f"{area}_status"
        df[col] = df[col].fillna("Normal") if col in df.columns else "Normal"
    return df


def _upsert_area_row(
    session, *, 
    period_type: str, 
    record_date: date, 
    period_label: str | None,
    area: str, predicted: float, 
    available: float, status: str,
) -> None:
    """
    Upsert a single row for a given area and period into the analytics_data table
    """
    zone_id = AREA_ZONE_ID_MAP[area]
    obj = (
        session.query(AnalyticsData)
        .filter(
            AnalyticsData.period_type == period_type,
            AnalyticsData.area_code == area,
            AnalyticsData.record_date == record_date,
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
            avg_occupancy_rate=0.0,
        )
        session.add(obj)
    obj.zone_id = zone_id
    obj.period_label = period_label
    obj.predicted_demand = round(predicted)
    obj.predicted_available = round(available)
    obj.status = status


def seed_daily(session) -> int:
    """
    Seed the daily forecast data from CSV into the analytics_data table
    """
    df = pd.read_csv(DATA_DIR / "daily_forecast.csv")
    df["ds"] = pd.to_datetime(df["ds"]).dt.date
    df = _clean_area_cols(df)

    count = 0
    for _, row in df.iterrows():
        record_date = row["ds"]
        for area in AREA_CODES:
            _upsert_area_row(
                session,
                period_type="daily",
                record_date=record_date,
                period_label=None,
                area=area,
                predicted=row[f"{area}_predicted"],
                available=row[f"{area}_available"],
                status=row[f"{area}_status"],
            )
            count += 1
    session.commit()
    return count


def seed_weekly(session) -> int:
    """
    Seed the weekly forecast data from CSV into the analytics_data table
    """
    df = pd.read_csv(DATA_DIR / "weekly_forecast.csv")
    df = _clean_area_cols(df)

    count = 0
    for _, row in df.iterrows():
        year, week = int(row["year"]), int(row["week"])
        record_date = date.fromisocalendar(year, week, 1)
        label = f"{year}-W{week}"
        for area in AREA_CODES:
            _upsert_area_row(
                session,
                period_type="weekly",
                record_date=record_date,
                period_label=label,
                area=area,
                predicted=row[f"{area}_predicted"],
                available=row[f"{area}_available"],
                status=row[f"{area}_status"],
            )
            count += 1
    session.commit()
    return count


def seed_monthly(session) -> int:
    """
    Seed the monthly forecast data from CSV into the analytics_data table
    """
    df = pd.read_csv(DATA_DIR / "monthly_forecast.csv")
    df = _clean_area_cols(df)

    count = 0
    for _, row in df.iterrows():
        year, month = int(row["year"]), int(row["month"])
        record_date = date(year, month, 1)
        label = f"{year}-{month:02d}"
        for area in AREA_CODES:
            _upsert_area_row(
                session,
                period_type="monthly",
                record_date=record_date,
                period_label=label,
                area=area,
                predicted=row[f"{area}_predicted"],
                available=row[f"{area}_available"],
                status=row[f"{area}_status"],
            )
            count += 1
    session.commit()
    return count


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
        print(f"Daily forecast seeded: {d} area-rows")
        print(f"Weekly forecast seeded: {w} area-rows")
        print(f"Monthly forecast seeded: {m} area-rows")
        print("All rows written into the existing analytics_data table (no extra tables).")
    finally:
        session.close()


if __name__ == "__main__":
    run()
