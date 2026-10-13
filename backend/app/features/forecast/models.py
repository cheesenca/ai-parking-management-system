from types import SimpleNamespace
<<<<<<< HEAD
from app.core.models import AnalyticsData
=======
from app.db.models import AnalyticsData
>>>>>>> origin/master

# Canonical area codes present in the dataset
AREA_CODES = ["P1W", "P1E", "P2W", "P2E", "P3W", "P3E"]
AREA_PLANT_MAP = {
    "P1W": "West",
    "P2W": "West",
    "P3W": "West",
    "P1E": "East",
    "P2E": "East",
    "P3E": "East",
}

AREA_LOCATION_MAP = {area: plant.lower() for area, plant in AREA_PLANT_MAP.items()}
AREA_ZONE_ID_MAP = {area: (1 if loc == "west" else 2) for area, loc in AREA_LOCATION_MAP.items()}

REAL_LOCATIONS = ["west", "east"]
ALL_LOCATIONS = ["west", "east", "eastwest"]

_STATUS_RANK = {"Normal": 0, "Warning": 1, "Full": 2}


def row_to_area_breakdown(row) -> list[dict]:
    """
    Given a pseudo-record
    """
    get = row.get if isinstance(row, dict) else lambda k: getattr(row, k)
    breakdown = []
    for area in AREA_CODES:
        breakdown.append({
            "area": area,
            "plant": AREA_PLANT_MAP[area],
            "predicted": get(f"{area}_predicted"),
            "available": get(f"{area}_available"),
            "status": get(f"{area}_status"),
        })
    return breakdown


def _worst_status(statuses: list[str]) -> str:
    """
    Given a list of status strings
    """
    if not statuses:
        return "Normal"
    return max(statuses, key=lambda s: _STATUS_RANK.get(s, 0))


def aggregate_by_location(row) -> dict:
    """
    Given a pseudo-record
    """
    get = row.get if isinstance(row, dict) else lambda k: getattr(row, k)

    result = {loc: {"predicted": 0.0, "available": 0.0, "statuses": []} for loc in REAL_LOCATIONS}
    for area in AREA_CODES:
        loc = AREA_LOCATION_MAP[area]
        result[loc]["predicted"] += get(f"{area}_predicted")
        result[loc]["available"] += get(f"{area}_available")
        result[loc]["statuses"].append(get(f"{area}_status"))

    out = {}
    for loc in REAL_LOCATIONS:
        out[loc] = {
            "location": loc,
            "predicted": result[loc]["predicted"],
            "available": result[loc]["available"],
            "status": _worst_status(result[loc]["statuses"]),
        }

    out["eastwest"] = {
        "location": "eastwest",
        "predicted": out["west"]["predicted"] + out["east"]["predicted"],
        "available": out["west"]["available"] + out["east"]["available"],
        "status": _worst_status([out["west"]["status"], out["east"]["status"]]),
    }
    return out


def _build_pseudo_row(records: list[AnalyticsData], **extra) -> SimpleNamespace:
    """
    Given a list of AnalyticsData records
    """
    ns = SimpleNamespace(**extra)
    by_area = {r.area_code: r for r in records}
    total = 0.0
    for area in AREA_CODES:
        r = by_area.get(area)
        predicted = float(r.predicted_demand) if r else 0.0
        available = float(r.predicted_available or 0) if r else 0.0
        status = (r.status or "Normal") if r else "Normal"
        setattr(ns, f"{area}_predicted", predicted)
        setattr(ns, f"{area}_available", available)
        setattr(ns, f"{area}_status", status)
        total += predicted
    ns.total_vehicles = total
    return ns


def query_daily_rows(db) -> list[SimpleNamespace]:
    """
    Daily forecast grouped from analytics_data
    """
    rows = (
        db.query(AnalyticsData)
        .filter(AnalyticsData.period_type == "daily", AnalyticsData.area_code.isnot(None))
        .order_by(AnalyticsData.record_date.asc())
        .all()
    )
    grouped: dict = {}
    for r in rows:
        grouped.setdefault(r.record_date, []).append(r)
    return [
        _build_pseudo_row(recs, ds=day)
        for day, recs in sorted(grouped.items(), key=lambda kv: kv[0])
    ]


def query_weekly_rows(db) -> list[SimpleNamespace]:
    """
    Weekly forecast grouped from analytics_data
    """
    rows = (
        db.query(AnalyticsData)
        .filter(AnalyticsData.period_type == "weekly", AnalyticsData.area_code.isnot(None))
        .order_by(AnalyticsData.record_date.asc())
        .all()
    )
    grouped: dict = {}
    for r in rows:
        grouped.setdefault(r.period_label or r.record_date.isoformat(), []).append(r)

    out = []
    for label, recs in grouped.items():
        try:
            year_str, week_str = label.split("-W")
            year, week = int(year_str), int(week_str)
        except (ValueError, AttributeError):
            year, week = recs[0].record_date.isocalendar()[0], recs[0].record_date.isocalendar()[1]
        out.append(_build_pseudo_row(recs, year=year, week=week))
    out.sort(key=lambda r: (r.year, r.week))
    return out


def query_monthly_rows(db) -> list[SimpleNamespace]:
    """
    Monthly forecast grouped from analytics_data
    """
    rows = (
        db.query(AnalyticsData)
        .filter(AnalyticsData.period_type == "monthly", AnalyticsData.area_code.isnot(None))
        .order_by(AnalyticsData.record_date.asc())
        .all()
    )
    grouped: dict = {}
    for r in rows:
        grouped.setdefault(r.period_label or r.record_date.strftime("%Y-%m"), []).append(r)

    out = []
    for label, recs in grouped.items():
        try:
            year_str, month_str = label.split("-")
            year, month = int(year_str), int(month_str)
        except (ValueError, AttributeError):
            year, month = recs[0].record_date.year, recs[0].record_date.month
        out.append(_build_pseudo_row(recs, year=year, month=month))
    out.sort(key=lambda r: (r.year, r.month))
    return out
