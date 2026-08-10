import logging
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import AnalyticsData, OccupancySnapshot, ParkingZone
from app.features.auth.endpoints import get_current_user
from app.features.forecast.services.model import forecast_next_days
from app.features.forecast.services.retrain import retrain_all_zones_arima
from app.features.forecast.report import build_report
from app.features.forecast.models import (
    AREA_CODES,
    AREA_PLANT_MAP,
    ALL_LOCATIONS,
    aggregate_by_location,
    query_daily_rows,
    query_weekly_rows,
    query_monthly_rows,
    row_to_area_breakdown,
)

logger = logging.getLogger(__name__)
router = APIRouter()

STATUS_COLS = [f"{a}_status" for a in AREA_CODES]
MONTH_NAMES = [
    "", 
    "January", 
    "February", 
    "March", 
    "April", 
    "May", 
    "June",
    "July", 
    "August", 
    "September", 
    "October", 
    "November", 
    "December",
]


def _daily_to_dict(row) -> dict:
    """
    Convert a daily forecast row to a dictionary suitable for JSON serialization
    """
    return {
        "ds": row.ds.isoformat(),
        "total_vehicles": row.total_vehicles,
        "areas": row_to_area_breakdown(row),
    }


def _weekly_to_dict(row) -> dict:
    """
    Convert a weekly forecast row to a dictionary suitable for JSON serialization
    """
    return {
        "year": row.year,
        "week": row.week,
        "total_vehicles": row.total_vehicles,
        "areas": row_to_area_breakdown(row),
    }


def _monthly_to_dict(row) -> dict:
    """
    Convert a monthly forecast row to a dictionary suitable for JSON serialization
    """
    return {
        "year": row.year,
        "month": row.month,
        "month_name": MONTH_NAMES[row.month] if 1 <= row.month <= 12 else str(row.month),
        "total_vehicles": row.total_vehicles,
        "areas": row_to_area_breakdown(row),
    }

 
# GET /api/forecast/predictive/daily
@router.get("/predictive/daily")
def get_daily_forecast(
    start: str | None = Query(default=None, description="YYYY-MM-DD, defaults to earliest available"),
    days: int = Query(default=7, ge=1, le=196),
    db: Session = Depends(get_db),
):
    """
    Daily parking demand forecast (P1W..P3E), tagged with West/East plant
    """
    rows = query_daily_rows(db)
    if start:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="start must be YYYY-MM-DD")
        rows = [r for r in rows if r.ds >= start_date]
    rows = rows[:days]
    return {"count": len(rows), "records": [_daily_to_dict(r) for r in rows]}


# GET /api/forecast/predictive/weekly
@router.get("/predictive/weekly")
def get_weekly_forecast(
    limit: int = Query(default=28, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Weekly parking demand forecast (P1W..P3E), tagged with West/East plant
    """
    rows = query_weekly_rows(db)[:limit]
    return {"count": len(rows), "records": [_weekly_to_dict(r) for r in rows]}


# GET /api/forecast/predictive/monthly
@router.get("/predictive/monthly")
def get_monthly_forecast(
    limit: int = Query(default=12, ge=1, le=60),
    db: Session = Depends(get_db),
):
    """
    Monthly parking demand forecast (P1W..P3E), tagged with West/East plant
    """
    rows = query_monthly_rows(db)[:limit]
    return {"count": len(rows), "records": [_monthly_to_dict(r) for r in rows]}


# GET /api/forecast/predictive/dashboard
@router.get("/predictive/dashboard")
def get_predictive_dashboard(
    date_: str | None = Query(default=None, alias="date", description="Selected day, YYYY-MM-DD"),
    view: str = Query(default="daily", pattern="^(daily|weekly|monthly)$"),
    location: str = Query(default="eastwest", pattern="^(west|east|eastwest)$", description="Location scope: 'eastwest' = west+east combined (Predictive Analytics only)"),
    db: Session = Depends(get_db),
):
    """
    Retrieve the full predictive analytics dashboard payload
    """
    daily_rows = query_daily_rows(db)
    weekly_rows = query_weekly_rows(db)
    monthly_rows = query_monthly_rows(db)

    if not daily_rows:
        raise HTTPException(status_code=503, detail="Forecast data not seeded yet, run seed_forecast.py")

    # Resolve the selected daily record 
    selected = daily_rows[0]
    if date_:
        try:
            target = datetime.strptime(date_, "%Y-%m-%d").date()
            selected = next((r for r in daily_rows if r.ds == target), daily_rows[0])
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

    start_idx = daily_rows.index(selected)
    window = daily_rows[start_idx:start_idx + 7]

    # Areas belonging to the selected location scope
    if location == "eastwest":
        scoped_areas = AREA_CODES
    else:
        scoped_areas = [a for a, p in AREA_PLANT_MAP.items() if p.lower() == location]
    scoped_status_cols = [f"{a}_status" for a in scoped_areas]

    # KPI cards 
    full_count = sum(1 for r in window for c in scoped_status_cols if getattr(r, c) == "Full")
    warning_count = sum(1 for r in window for c in scoped_status_cols if getattr(r, c) == "Warning")
    risk_areas = full_count + warning_count

    if location == "eastwest":
        avg_total = sum(r.total_vehicles for r in window) / len(window) if window else 0
    else:
        avg_total = sum(
            sum(getattr(r, f"{a}_predicted") for a in scoped_areas) for r in window
        ) / len(window) if window else 0
    avg_occupancy_pct = min(99, max(0, round((avg_total / 1500) * 100)))

    # Area performance
    area_performance = []
    for area in scoped_areas:
        predicted = getattr(selected, f"{area}_predicted")
        available = getattr(selected, f"{area}_available")
        capacity = predicted + available if (predicted + available) > 0 else 1
        area_performance.append({
            "area": area,
            "plant": AREA_PLANT_MAP[area],
            "utilization_pct": round(min(100, (predicted / capacity) * 100)),
            "status": getattr(selected, f"{area}_status"),
        })

    # Location-level rollup (west / east / eastwest) for the selected day
    location_breakdown = aggregate_by_location(selected)

    if location == "eastwest":
        trend = [{"ds": r.ds.isoformat(), "total_vehicles": r.total_vehicles} for r in window]
    else:
        trend = [
            {"ds": r.ds.isoformat(), "total_vehicles": sum(getattr(r, f"{a}_predicted") for a in scoped_areas)}
            for r in window
        ]
    preview = [_daily_to_dict(r) for r in window]

    return {
        "selected_date": selected.ds.isoformat(),
        "location": location,
        "available_locations": ALL_LOCATIONS,
        "kpis": {
            "daily_records": int(selected.total_vehicles) if location == "eastwest" else round(location_breakdown[location]["predicted"]),
            "weekly_records": len(weekly_rows),
            "monthly_records": len(monthly_rows),
            "avg_occupancy_pct": avg_occupancy_pct,
            "risk_areas": risk_areas,
            "full_count": full_count,
            "warning_count": warning_count,
        },
        "area_performance": area_performance,
        "location_breakdown": location_breakdown,
        "trend": trend,
        "forecast_preview": preview,
        "plant_mapping": AREA_PLANT_MAP,
    }


# GET /api/forecast/predictive/report
@router.get("/predictive/report")
def get_predictive_report(
    date_: str | None = Query(default=None, alias="date", description="Selected day, YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    Generate a comprehensive predictive analytics report for a specific day
    """
    try:
        return build_report(db, date_)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# GET /api/forecast/prophet
@router.get("/prophet")
def get_prophet_forecast(
    periods: int = Query(default=30, ge=1, le=90),
    zone: str = Query(default="west", pattern="^(west|east)$"),
):
    """
    Forecast the next `periods` days of parking demand using the Prophet model for a specific zone
    """
    try:
        return {
            "model": "Prophet",
            "zone": zone,
            "periods": periods,
            "forecast": forecast_next_days(periods, zone=zone),
        }
    except FileNotFoundError as exc:
        logger.error("Prophet forecast unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except RuntimeError as exc:
        logger.error("Prophet forecast failed to load: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))


# POST /api/forecast/retrain
@router.post("/retrain")
def trigger_retrain(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Admin-triggered on-demand ARIMA retrain, bypassing the nightly schedule
    """
    if getattr(current_user, "role", None) != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can trigger a retrain")

    results = retrain_all_zones_arima(db)
    return {"triggered_at": datetime.now().isoformat(), "results": results}


# GET /api/forecast/zones
@router.get("/zones")
def list_zones(db: Session = Depends(get_db)):
    """
    Retrieve the list of all parking zones available in the database
    """
    zones = db.query(ParkingZone).all()
    return [{"zone_id": z.zone_id, **z.to_dashboard_dict()} for z in zones]


# GET /api/forecast/dashboard/{zone_id} 
@router.get("/dashboard/{zone_id}")
def get_forecast_dashboard(
    zone_id: int,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Retrieving data from the parking demand forecasting and average occupancy dashboard for a specific zone
    """
    zone = db.query(ParkingZone).filter(ParkingZone.zone_id == zone_id).first()
    if not zone:
        logger.warning("Forecast dashboard requested for unknown zone_id=%s", zone_id)
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")

    since = date.today() - timedelta(days=days)
    records = (
        db.query(AnalyticsData)
        .filter(
            AnalyticsData.zone_id == zone_id,
            AnalyticsData.record_date >= since,
        )
        .order_by(AnalyticsData.record_date.asc())
        .all()
    )

    data = [
        {
            "date": r.record_date.isoformat(),
            "predicted_demand": r.predicted_demand,
            "avg_occupancy_rate": r.avg_occupancy_rate,
            "peak_hour_start": str(r.peak_hour_start),
            "peak_hour_end": str(r.peak_hour_end),
            "employee": r.predicted_employee,
            "vendor": r.predicted_vendor,
            "visitor": r.predicted_visitor,
        }
        for r in records
    ]

    return {
        "zone_id": zone_id,
        "zone_name": zone.zone_name,
        "summary": zone.to_dashboard_dict(),
        "data": data,
    }


# GET /api/forecast/occupancy/history/{zone_id}
@router.get("/occupancy/history/{zone_id}")
def get_occupancy_history(
    zone_id: int,
    hours: int = Query(default=24, ge=1, le=8760),
    db: Session = Depends(get_db),
):
    """
    Capturing real-time historical snapshots of parking space occupancy based on specified hourly intervals
    """
    since = datetime.now() - timedelta(hours=hours)
    snapshots = (
        db.query(OccupancySnapshot)
        .filter(
            OccupancySnapshot.zone_id == zone_id,
            OccupancySnapshot.recorded_at >= since,
        )
        .order_by(OccupancySnapshot.recorded_at.asc())
        .all()
    )

    return [
        {
            "timestamp": s.recorded_at.isoformat(),
            "total_occupied": s.total_occupied,
            "total_capacity": s.total_capacity,
            "overall_rate_pct": s.overall_rate_pct,
            "employee_used": s.employee_used,
            "vendor_used": s.vendor_used,
            "visitor_used": s.visitor_used,
        }
        for s in snapshots
    ]
