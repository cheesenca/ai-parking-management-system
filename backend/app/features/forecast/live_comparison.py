from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from app.core.models import OccupancySnapshot, ParkingZone
from app.features.forecast.models import AREA_ZONE_ID_MAP, REAL_LOCATIONS


def _zone_ids_by_key(db: Session) -> dict[str, int]:
    """
    Returns a dict mapping zone_key to zone_id for all zones in REAL_LOCATIONS
    """
    rows = db.query(ParkingZone.zone_key, ParkingZone.zone_id).filter(
        ParkingZone.zone_key.in_(REAL_LOCATIONS)
    ).all()
    return {key: zid for key, zid in rows}


def _latest_snapshot(db: Session, zone_id: int, on_date: date) -> OccupancySnapshot | None:
    """
    Returns the latest OccupancySnapshot for the given zone_id on the given date
    """
    start = datetime.combine(on_date, datetime.min.time())
    end = start + timedelta(days=1)
    row = (
        db.query(OccupancySnapshot)
        .filter(OccupancySnapshot.zone_id == zone_id,
                OccupancySnapshot.recorded_at >= start,
                OccupancySnapshot.recorded_at < end)
        .order_by(OccupancySnapshot.recorded_at.desc())
        .first()
    )
    if row is not None:
        return row
    return (
        db.query(OccupancySnapshot)
        .filter(OccupancySnapshot.zone_id == zone_id)
        .order_by(OccupancySnapshot.recorded_at.desc())
        .first()
    )


def _calibration(predicted: float, actual: float) -> tuple[float, str]:
    """
    Given a predicted and actual value, returns the deviation percentage and a label
    """
    if predicted <= 0:
        return 0.0, "No forecast"
    deviation_pct = round(((actual - predicted) / predicted) * 100, 1)
    if abs(deviation_pct) <= 10:
        label = "Accurate"
    elif deviation_pct > 10:
        label = "Underestimated"
    else:
        label = "Overestimated" 
    return deviation_pct, label


def build_live_comparison(db: Session, daily_row, selected_date: date) -> dict:
    """
    Given a daily forecast row and a selected date
    """
    from app.features.forecast.models import AREA_PLANT_MAP

    zone_ids = _zone_ids_by_key(db)
    predicted_by_zone = {"west": 0.0, "east": 0.0}
    for area, plant in AREA_PLANT_MAP.items():
        predicted_by_zone[plant.lower()] += getattr(daily_row, f"{area}_predicted")

    zones = {}
    any_live = False
    for loc in REAL_LOCATIONS:
        zone_id = zone_ids.get(loc) or AREA_ZONE_ID_MAP[next(a for a, p in AREA_PLANT_MAP.items() if p.lower() == loc)]
        snapshot = _latest_snapshot(db, zone_id, selected_date)
        predicted = predicted_by_zone[loc]

        if snapshot is None:
            zones[loc] = {
                "location": loc,
                "predicted": round(predicted),
                "actual": None,
                "has_live_data": False,
                "deviation_pct": None,
                "calibration": "No camera data yet",
                "recorded_at": None,
            }
            continue

        any_live = True
        deviation_pct, label = _calibration(predicted, snapshot.total_occupied)
        zones[loc] = {
            "location": loc,
            "predicted": round(predicted),
            "actual": snapshot.total_occupied,
            "has_live_data": True,
            "deviation_pct": deviation_pct,
            "calibration": label,
            "recorded_at": snapshot.recorded_at.isoformat(),
        }

    combined_predicted = zones["west"]["predicted"] + zones["east"]["predicted"]
    if zones["west"]["has_live_data"] and zones["east"]["has_live_data"]:
        combined_actual = zones["west"]["actual"] + zones["east"]["actual"]
        deviation_pct, label = _calibration(combined_predicted, combined_actual)
        zones["eastwest"] = {
            "location": "eastwest",
            "predicted": combined_predicted,
            "actual": combined_actual,
            "has_live_data": True,
            "deviation_pct": deviation_pct,
            "calibration": label,
            "recorded_at": min(zones["west"]["recorded_at"], zones["east"]["recorded_at"]),
        }
    else:
        zones["eastwest"] = {
            "location": "eastwest",
            "predicted": combined_predicted,
            "actual": None,
            "has_live_data": False,
            "deviation_pct": None,
            "calibration": "No camera data yet",
            "recorded_at": None,
        }

    return {"has_any_live_data": any_live, "zones": zones}
