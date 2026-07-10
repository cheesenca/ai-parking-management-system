from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.models import AnalyticsData, OccupancySnapshot, ParkingZone
from app.features.forecast.services.model import forecast_next_days

router = APIRouter()

# GET /api/forecast/arima
@router.get("/arima")
def get_arima_forecast(
    periods: int = Query(default=30, ge=1, le=90),
):
    """
    Generate a live total-demand forecast using the pre-trained ARIMA model (arima.joblib)
    """
    try:
        return {
            "model": "ARIMA",
            "periods": periods,
            "forecast": forecast_next_days(periods),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

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
    Retrieving data from the parking demand forecasting and average occupancy dashboard for a specific zone, based on the number of days parameter
    """
    zone = db.query(ParkingZone).filter(ParkingZone.zone_id == zone_id).first()
    if not zone:
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