from datetime import date, datetime
from typing import Any, Sequence
from app.features.forecast.models import AREA_CODES, query_daily_rows, query_monthly_rows, query_weekly_rows

MONTH_NAMES = {
    1: "January", 
    2: "February", 
    3: "March", 
    4: "April", 
    5: "May", 
    6: "June",
    7: "July", 
    8: "August", 
    9: "September", 
    10: "October", 
    11: "November", 
    12: "December",
}

HIGH_CONTRIBUTION_THRESHOLD = 18
MODERATE_CONTRIBUTION_THRESHOLD = 15

TREND_CHANGE_THRESHOLD = 0.02

ACTION_HIGH = "Prioritize monitoring and prepare operational adjustment."
ACTION_MEDIUM = "Monitor during peak period and review area usage."
ACTION_LOW = "Continue standard monitoring."

REC_DAILY_HIGH = "Prepare overflow parking and prioritize areas with Full status."
REC_DAILY_WARN = "Monitor Warning areas before they become full."
REC_DAILY_STABLE = "Continue normal parking operation."

REC_WEEKLY_HIGH = "Review High areas and adjust weekly parking allocation."
REC_WEEKLY_WARN = "Monitor Moderate areas during peak periods."
REC_WEEKLY_STABLE = "Continue standard weekly monitoring."

REC_MONTHLY_DECREASE = "Review areas with decreasing availability for capacity planning."
REC_MONTHLY_INCREASE = "Use monthly availability trend to support future parking capacity planning."
REC_MONTHLY_STABLE = "Continue monthly parking monitoring."

PRIORITY_HIGH = "High"
PRIORITY_MEDIUM = "Medium"
PRIORITY_LOW = "Low"

PRIORITY_ORDER = {
    PRIORITY_HIGH: 1, 
    PRIORITY_MEDIUM: 2, 
    PRIORITY_LOW: 3,
}


def _get_weekly_level(row: Any, area_code: str) -> str:
    """
    Determine the weekly level for a given area based on its predicted demand
    """
    area_predicted = getattr(row, f"{area_code}_predicted", 0)
    total_predicted = sum(getattr(row, f"{code}_predicted", 0) for code in AREA_CODES)

    if total_predicted <= 0:
        return "Good"

    contribution_percentage = round((area_predicted / total_predicted) * 100)
    
    if contribution_percentage >= HIGH_CONTRIBUTION_THRESHOLD:
        return "High"
        
    if contribution_percentage >= MODERATE_CONTRIBUTION_THRESHOLD:
        return "Moderate"
        
    return "Good"


def _get_monthly_trend(monthly_rows: Sequence[Any], row_index: int, area_code: str) -> str:
    """
    Measure the monthly trend for a given area based on its availability compared to the previous month
    """
    if row_index <= 0 or row_index >= len(monthly_rows):
        return "Start"

    current_available = getattr(monthly_rows[row_index], f"{area_code}_available", 0)
    previous_available = getattr(monthly_rows[row_index - 1], f"{area_code}_available", 0)

    if previous_available <= 0 and current_available > 0:
        return "Increase"

    change_ratio = (current_available - previous_available) / max(previous_available, 1)

    if change_ratio > TREND_CHANGE_THRESHOLD:
        return "Increase"

    if change_ratio < -TREND_CHANGE_THRESHOLD:
        return "Decrease"

    return "Stable"


def _daily_index_from_date(daily_rows: list[Any], selected_date: date | None) -> int:
    """
    Find the index of the daily forecast row that matches the selected date
    """
    if not daily_rows or not selected_date:
        return 0

    for index, row in enumerate(daily_rows):
        row_date = getattr(row, "ds", None)
        
        if row_date == selected_date:
            return index
            
    return 0


def _weekly_index_from_date(weekly_rows: list[Any], reference_date: date) -> int:
    """
    Find the index of the weekly forecast row that matches the reference date
    """
    if not weekly_rows:
        return 0

    iso_year, iso_week, _ = reference_date.isocalendar()
    partial_match_index = None

    for index, row in enumerate(weekly_rows):
        if row.year == iso_year and row.week == iso_week:
            return index
            
        if partial_match_index is None and row.week == iso_week:
            partial_match_index = index

    return partial_match_index if partial_match_index is not None else 0


def _monthly_index_from_date(monthly_rows: list[Any], reference_date: date) -> int:
    """
    Find the index of the monthly forecast row that matches the reference date
    """
    if not monthly_rows:
        return 0
        
    target_year = reference_date.year
    target_month = reference_date.month
    partial_match_index = None

    for index, row in enumerate(monthly_rows):
        if row.year == target_year and row.month == target_month:
            return index
            
        if partial_match_index is None and row.month == target_month:
            partial_match_index = index

    return partial_match_index if partial_match_index is not None else 0


def _compile_area_reasons(daily_status: str, weekly_status: str, monthly_trend: str) -> list[str]:
    """
    Compile reasons for the area attention summary based on daily, weekly, and monthly statuses
    """
    reasons = []
    
    if daily_status == "Full":
        reasons.append("Full condition in daily forecast")
    elif daily_status == "Warning":
        reasons.append("Warning condition in daily forecast")

    if weekly_status == "High": 
        reasons.append("High weekly demand contribution")
    elif weekly_status == "Moderate":
        reasons.append("Moderate weekly demand contribution")

    if monthly_trend == "Decrease": 
        reasons.append("Availability decreased compared with previous month")
    elif monthly_trend == "Increase":
        reasons.append("Availability increased compared with previous month")

    return reasons or ["Stable condition"]


def _determine_priority_and_action(daily_status: str, weekly_status: str, monthly_trend: str) -> tuple[str, str]:
    """
    Determine the priority level and recommended action based on daily, weekly, and monthly statuses
    """
    if daily_status == "Full" or weekly_status == "High" or monthly_trend == "Decrease":
        return PRIORITY_HIGH, ACTION_HIGH
        
    if daily_status == "Warning" or weekly_status == "Moderate":
        return PRIORITY_MEDIUM, ACTION_MEDIUM
        
    return PRIORITY_LOW, ACTION_LOW


def _build_area_attention_summary(
    daily_row: Any, 
    weekly_row: Any, 
    monthly_rows: list[Any], 
    monthly_index: int
) -> list[dict[str, Any]]:
    """
    Build a summary of area attention based on daily, weekly, and monthly insights
    """
    summary = []
    
    for area in AREA_CODES: 
        daily_status = getattr(daily_row, f"{area}_status", "Normal") if daily_row else "Normal"
        weekly_status = _get_weekly_level(weekly_row, area) if weekly_row else "Good"
        monthly_trend = _get_monthly_trend(monthly_rows, monthly_index, area)

        reasons = _compile_area_reasons(daily_status, weekly_status, monthly_trend)
        priority, action = _determine_priority_and_action(daily_status, weekly_status, monthly_trend)

        summary.append({
            "area": area,
            "priority": priority,
            "daily_status": daily_status,
            "weekly_status": weekly_status,
            "monthly_trend": monthly_trend,
            "reason": "; ".join(reasons),
            "action": action,
        })

    return sorted(summary, key=lambda item: PRIORITY_ORDER.get(item["priority"], 99))


def _get_reference_date(daily_rows: list[Any], selected_date_str: str | None) -> date:
    """
    Determine the reference date for the report based on the selected date string or default to the first daily row's date
    """
    if selected_date_str:
        try:
            return datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass 
            
    return daily_rows[0].ds


def _analyze_daily_insights(daily_window: list[Any]) -> dict[str, Any]:
    """
    Calculate daily metrics and conditions based on the provided daily window of forecast data
    """
    full_count = 0
    warning_count = 0
    total_vehicles = sum(r.total_vehicles for r in daily_window)

    for row in daily_window:
        for area in AREA_CODES: 
            status = getattr(row, f"{area}_status", None)
            if status == "Full":  
                full_count += 1
            elif status == "Warning":
                warning_count += 1

    avg_total = (total_vehicles / len(daily_window)) if daily_window else 0
    occupancy = min(99, max(0, round((avg_total / 1500) * 100)))

    if full_count > 0:
        condition, rec = "High Risk", REC_DAILY_HIGH
    elif warning_count > 0:
        condition, rec = "Needs Monitoring", REC_DAILY_WARN
    else:
        condition, rec = "Stable", REC_DAILY_STABLE

    return {
        "daily_occupancy": occupancy,
        "daily_full_count": full_count,
        "daily_warning_count": warning_count,
        "daily_condition": condition,
        "daily_recommendation": rec,
    }


def _analyze_weekly_insights(weekly_window: list[Any]) -> dict[str, Any]:
    """
    Calculate weekly metrics and conditions based on the provided weekly window of forecast data
    """
    high_count = moderate_count = good_count = 0

    for row in weekly_window:
        for area in AREA_CODES:  
            level = _get_weekly_level(row, area)  
            if level == "High": 
                high_count += 1
            elif level == "Moderate":
                moderate_count += 1
            else:
                good_count += 1

    if high_count > 0:
        condition, rec = "Needs Attention", REC_WEEKLY_HIGH
    elif moderate_count > 0:
        condition, rec = "Needs Monitoring", REC_WEEKLY_WARN
    else:
        condition, rec = "Stable", REC_WEEKLY_STABLE

    return {
        "weekly_high_count": high_count,
        "weekly_moderate_count": moderate_count,
        "weekly_good_count": good_count,
        "weekly_condition": condition,
        "weekly_recommendation": rec,
    }


def _analyze_monthly_insights(monthly_rows: list[Any], start_index: int) -> dict[str, Any]:
    """
    Calculate monthly metrics and conditions based on the provided monthly rows starting from the given index
    """
    increase_count = decrease_count = stable_count = 0
    end_index = min(start_index + 7, len(monthly_rows))

    for idx in range(start_index, end_index):
        for area in AREA_CODES: 
            trend = _get_monthly_trend(monthly_rows, idx, area)
            if trend == "Increase":
                increase_count += 1
            elif trend == "Decrease":
                decrease_count += 1
            elif trend == "Stable":
                stable_count += 1

    if decrease_count > 0:
        condition, rec = "Planning Required", REC_MONTHLY_DECREASE
    elif increase_count > 0:
        condition, rec = "Availability Improved", REC_MONTHLY_INCREASE
    else:
        condition, rec = "Stable", REC_MONTHLY_STABLE

    return {
        "monthly_increase_count": increase_count,
        "monthly_decrease_count": decrease_count,
        "monthly_stable_count": stable_count,
        "monthly_condition": condition,
        "monthly_recommendation": rec,
    }


def build_report(db: Any, selected_date_str: str | None = None) -> dict[str, Any]:
    """
    Build the full management report payload for the given selected date
    """
    daily_rows = query_daily_rows(db)
    weekly_rows = query_weekly_rows(db)
    monthly_rows = query_monthly_rows(db)

    if not daily_rows:
        raise ValueError("Forecast data not seeded yet. Run seed_forecast.py.")

    # Date Resolution & Indexing
    reference_date = _get_reference_date(daily_rows, selected_date_str)
    
    daily_index = _daily_index_from_date(daily_rows, reference_date)
    # Re-sync reference_date based on actual found daily row
    reference_date = daily_rows[daily_index].ds 
    
    weekly_index = _weekly_index_from_date(weekly_rows, reference_date)
    monthly_index = _monthly_index_from_date(monthly_rows, reference_date)

    daily_row = daily_rows[daily_index]
    weekly_row = weekly_rows[weekly_index] if weekly_rows else None
    monthly_row = monthly_rows[monthly_index] if monthly_rows else None

    # Insight Extraction
    daily_insights = _analyze_daily_insights(daily_rows[daily_index : daily_index + 7])
    weekly_insights = _analyze_weekly_insights(weekly_rows[weekly_index : weekly_index + 7])
    monthly_insights = _analyze_monthly_insights(monthly_rows, monthly_index)

    # Area Summary Integration
    area_summary = _build_area_attention_summary(
        daily_row=daily_row, 
        weekly_row=weekly_row, 
        monthly_rows=monthly_rows, 
        monthly_index=monthly_index
    )
    
    high_priority_count = sum(1 for item in area_summary if item["priority"] == PRIORITY_HIGH)

    # Construct Final Payload
    return {
        "report_date": date.today().strftime("%d %B %Y"),
        "report_year": reference_date.year,

        "daily_selected_date": daily_row.ds.isoformat(),
        "daily_total": round(daily_row.total_vehicles),
        **daily_insights, 

        "weekly_selected": f"W{weekly_row.week}" if weekly_row else "-",
        "weekly_total": round(weekly_row.total_vehicles) if weekly_row else 0,
        **weekly_insights, 

        "monthly_selected": MONTH_NAMES.get(monthly_row.month, "-") if monthly_row else "-",
        "monthly_total": round(monthly_row.total_vehicles) if monthly_row else 0,
        **monthly_insights,

        "area_summary": area_summary,
        "high_priority_count": high_priority_count,

        "executive_summary": [
            "Parking demand forecast shows selected areas require operational monitoring.",
            "Daily forecast is used for operational risk by identifying Full and Warning conditions.",
            "Weekly forecast is aligned with the selected report perspective to monitor area demand contribution.",
            "Monthly forecast is aligned with the selected report perspective to support capacity planning based on availability trend.",
        ],
    }
