import os
import json
import pandas as pd
from datetime import date
from django.shortcuts import render


AREA_CODES = ["P1W", "P1E", "P2W", "P2E", "P3W", "P3E"]

AREA_NUMERIC_COLS = [
    "P1W_predicted", "P1W_available",
    "P1E_predicted", "P1E_available",
    "P2W_predicted", "P2W_available",
    "P2E_predicted", "P2E_available",
    "P3W_predicted", "P3W_available",
    "P3E_predicted", "P3E_available",
]

STATUS_COLS = [
    "P1W_status",
    "P1E_status",
    "P2W_status",
    "P2E_status",
    "P3W_status",
    "P3E_status",
]


def get_forecast_folder():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(app_dir)
    workspace_root = os.path.dirname(project_dir)
    forecast_folder = os.path.join(workspace_root, "forecast")
    return forecast_folder


def apply_forecast_total(df):
    if "prophet_yhat" in df.columns:
        df["total_vehicles"] = df["prophet_yhat"]
    elif "yhat_best" in df.columns:
        df["total_vehicles"] = df["yhat_best"]
    elif "total_vehicles" not in df.columns:
        df["total_vehicles"] = 0

    df["total_vehicles"] = (
        pd.to_numeric(df["total_vehicles"], errors="coerce")
        .fillna(0)
        .round()
        .astype(int)
    )

    return df


def prepare_forecast_data():
    forecast_folder = get_forecast_folder()

    daily_path = os.path.join(forecast_folder, "daily_forecast.csv")
    weekly_path = os.path.join(forecast_folder, "weekly_forecast.csv")
    monthly_path = os.path.join(forecast_folder, "monthly_forecast.csv")

    daily_df = pd.read_csv(daily_path)
    weekly_df = pd.read_csv(weekly_path)
    monthly_df = pd.read_csv(monthly_path)

    daily_df = apply_forecast_total(daily_df)
    weekly_df = apply_forecast_total(weekly_df)
    monthly_df = apply_forecast_total(monthly_df)

    daily_df["ds"] = pd.to_datetime(daily_df["ds"])
    daily_df = daily_df.sort_values("ds")
    daily_df["ds"] = daily_df["ds"].dt.date

    weekly_df = weekly_df.sort_values(["year", "week"])
    monthly_df = monthly_df.sort_values(["year", "month"])

    for df in [daily_df, weekly_df, monthly_df]:
        for col in AREA_NUMERIC_COLS:
            if col in df.columns:
                df[col] = (
                    pd.to_numeric(df[col], errors="coerce")
                    .fillna(0)
                    .round()
                    .astype(int)
                )
            else:
                df[col] = 0

        for col in STATUS_COLS:
            if col not in df.columns:
                df[col] = "Normal"
            else:
                df[col] = df[col].fillna("Normal")

    return daily_df, weekly_df, monthly_df


def get_weekly_level(row, area_code):
    total_predicted = 0

    for area in AREA_CODES:
        total_predicted += int(row.get(f"{area}_predicted", 0) or 0)

    if total_predicted <= 0:
        return "Good"

    area_predicted = int(row.get(f"{area_code}_predicted", 0) or 0)

    # Samakan dengan dashboard:
    # dashboard membulatkan contribution dulu sebelum menentukan status
    contribution = round((area_predicted / total_predicted) * 100)

    if contribution >= 18:
        return "High"
    elif contribution >= 15:
        return "Moderate"
    else:
        return "Good"


def get_monthly_trend(monthly_df, row_index, area_code):
    if row_index <= 0:
        return "Start"

    current_value = int(monthly_df.iloc[row_index].get(f"{area_code}_available", 0) or 0)
    previous_value = int(monthly_df.iloc[row_index - 1].get(f"{area_code}_available", 0) or 0)

    if previous_value <= 0 and current_value > 0:
        return "Increase"

    change_ratio = (current_value - previous_value) / max(previous_value, 1)

    if change_ratio > 0.02:
        return "Increase"
    elif change_ratio < -0.02:
        return "Decrease"
    else:
        return "Stable"


def month_name(month_number):
    month_map = {
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

    return month_map.get(int(month_number), f"Month {month_number}")


def build_area_attention_summary(daily_row, weekly_row, monthly_df, monthly_index=0):
    area_summary = []

    for area in AREA_CODES:
        daily_status = str(daily_row.get(f"{area}_status", "Normal"))
        weekly_status = get_weekly_level(weekly_row, area)
        monthly_trend = get_monthly_trend(monthly_df, monthly_index, area)

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

        if daily_status == "Full" or weekly_status == "High" or monthly_trend == "Decrease":
            priority = "High"
            action = "Prioritize monitoring and prepare operational adjustment."
        elif daily_status == "Warning" or weekly_status == "Moderate":
            priority = "Medium"
            action = "Monitor during peak period and review area usage."
        else:
            priority = "Low"
            action = "Continue standard monitoring."

        if not reasons:
            reasons.append("Stable condition")

        area_summary.append({
            "area": area,
            "priority": priority,
            "daily_status": daily_status,
            "weekly_status": weekly_status,
            "monthly_trend": monthly_trend,
            "reason": "; ".join(reasons),
            "action": action,
        })

    priority_order = {"High": 1, "Medium": 2, "Low": 3}
    area_summary = sorted(area_summary, key=lambda item: priority_order[item["priority"]])

    return area_summary


def get_daily_index_from_selected_date(daily_df, selected_date):
    if not selected_date:
        return daily_df.index[0] if not daily_df.empty else 0

    daily_match = daily_df[daily_df["ds"].astype(str) == str(selected_date)]

    if not daily_match.empty:
        return daily_match.index[0]

    return daily_df.index[0] if not daily_df.empty else 0


def get_weekly_index_from_selected_date(weekly_df, selected_date):
    """
    Weekly report otomatis mengikuti week dari selected date.
    """
    if weekly_df.empty:
        return 0

    try:
        selected_datetime = pd.to_datetime(selected_date)
        selected_year = int(selected_datetime.isocalendar().year)
        selected_week = int(selected_datetime.isocalendar().week)

        weekly_match = weekly_df[
            (weekly_df["year"].astype(int) == selected_year) &
            (weekly_df["week"].astype(int) == selected_week)
        ]

        if not weekly_match.empty:
            return weekly_match.index[0]

        weekly_match = weekly_df[weekly_df["week"].astype(int) == selected_week]

        if not weekly_match.empty:
            return weekly_match.index[0]

    except Exception:
        pass

    return weekly_df.index[0]


def get_monthly_index_from_selected_date(monthly_df, selected_date):
    """
    Monthly report otomatis mengikuti bulan dari selected date.
    """
    if monthly_df.empty:
        return 0

    try:
        selected_datetime = pd.to_datetime(selected_date)
        selected_year = int(selected_datetime.year)
        selected_month = int(selected_datetime.month)

        monthly_match = monthly_df[
            (monthly_df["year"].astype(int) == selected_year) &
            (monthly_df["month"].astype(int) == selected_month)
        ]

        if not monthly_match.empty:
            return monthly_match.index[0]

        monthly_match = monthly_df[monthly_df["month"].astype(int) == selected_month]

        if not monthly_match.empty:
            return monthly_match.index[0]

    except Exception:
        pass

    return monthly_df.index[0]


def forecast_dashboard(request):
    daily_df, weekly_df, monthly_df = prepare_forecast_data()

    daily_forecast = daily_df.to_dict(orient="records")
    weekly_forecast = weekly_df.to_dict(orient="records")
    monthly_forecast = monthly_df.to_dict(orient="records")

    daily_count = len(daily_forecast)
    weekly_count = len(weekly_forecast)
    monthly_count = len(monthly_forecast)

    normal_count = sum((daily_df[col] == "Normal").sum() for col in STATUS_COLS)
    warning_count = sum((daily_df[col] == "Warning").sum() for col in STATUS_COLS)
    full_count = sum((daily_df[col] == "Full").sum() for col in STATUS_COLS)

    avg_total_vehicles = int(daily_df["total_vehicles"].mean()) if not daily_df.empty else 0
    peak_demand = int(daily_df["total_vehicles"].max()) if not daily_df.empty else 0
    projected_risk = warning_count + full_count

    daily_chart_df = daily_df.head(7)
    daily_chart_labels = daily_chart_df["ds"].astype(str).tolist()
    daily_chart_values = daily_chart_df["total_vehicles"].astype(int).tolist()
    daily_dates = daily_df["ds"].astype(str).tolist()

    context = {
        "year": 2026,
        "daily_forecast": daily_forecast,
        "weekly_forecast": weekly_forecast,
        "monthly_forecast": monthly_forecast,
        "daily_count": daily_count,
        "weekly_count": weekly_count,
        "monthly_count": monthly_count,
        "normal_count": normal_count,
        "warning_count": warning_count,
        "full_count": full_count,
        "avg_total_vehicles": avg_total_vehicles,
        "peak_demand": peak_demand,
        "projected_risk": projected_risk,
        "daily_chart_labels_json": json.dumps(daily_chart_labels),
        "daily_chart_values_json": json.dumps(daily_chart_values),
        "daily_dates_json": json.dumps(daily_dates),
    }

    return render(request, "forecast_app/forecast_dashboard.html", context)

def get_daily_index_on_or_after(daily_df, reference_date):
    if daily_df.empty:
        return 0

    try:
        reference_datetime = pd.to_datetime(reference_date)
        daily_dates = pd.to_datetime(daily_df["ds"])

        matched = daily_df[daily_dates >= reference_datetime]

        if not matched.empty:
            return matched.index[0]

        return daily_df.index[-1]

    except Exception:
        return daily_df.index[0]


def get_weekly_index_by_week(weekly_df, selected_week):
    if weekly_df.empty:
        return 0

    try:
        selected_week = int(selected_week)

        weekly_match = weekly_df[weekly_df["week"].astype(int) == selected_week]

        if not weekly_match.empty:
            return weekly_match.index[0]

    except Exception:
        pass

    return weekly_df.index[0]


def get_monthly_index_by_month(monthly_df, selected_month):
    if monthly_df.empty:
        return 0

    try:
        selected_month = int(selected_month)

        monthly_match = monthly_df[monthly_df["month"].astype(int) == selected_month]

        if not monthly_match.empty:
            return monthly_match.index[0]

    except Exception:
        pass

    return monthly_df.index[0]


def get_reference_date_from_weekly_row(weekly_row):
    try:
        year = int(weekly_row.get("year", 2026))
        week = int(weekly_row.get("week", 1))

        return date.fromisocalendar(year, week, 1)

    except Exception:
        return date(2026, 6, 1)


def get_reference_date_from_monthly_row(monthly_row):
    try:
        year = int(monthly_row.get("year", 2026))
        month = int(monthly_row.get("month", 6))

        return date(year, month, 1)

    except Exception:
        return date(2026, 6, 1)


def management_report(request):
    daily_df, weekly_df, monthly_df = prepare_forecast_data()

    selected_type = request.GET.get("type", "daily")
    selected_date = request.GET.get("date")
    selected_week = request.GET.get("week")
    selected_month = request.GET.get("month")

    # =========================================================
    # MODE 1: USER EXPORT DARI DAILY VIEW
    # Daily menjadi acuan utama.
    # Weekly dan Monthly otomatis mengikuti tanggal daily.
    # =========================================================
    if selected_type == "daily":
        if not selected_date and not daily_df.empty:
            selected_date = str(daily_df.iloc[0].get("ds", ""))

        daily_index = get_daily_index_from_selected_date(daily_df, selected_date)
        reference_date = pd.to_datetime(daily_df.loc[daily_index].get("ds"))

        weekly_index = get_weekly_index_from_selected_date(weekly_df, reference_date)
        monthly_index = get_monthly_index_from_selected_date(monthly_df, reference_date)

    # =========================================================
    # MODE 2: USER EXPORT DARI WEEKLY VIEW
    # Weekly menjadi acuan utama.
    # Daily mengikuti awal minggu tersebut.
    # Monthly mengikuti bulan dari minggu tersebut.
    # =========================================================
    elif selected_type == "weekly":
        weekly_index = get_weekly_index_by_week(weekly_df, selected_week)
        weekly_row_temp = weekly_df.loc[weekly_index]

        reference_date = get_reference_date_from_weekly_row(weekly_row_temp)

        daily_index = get_daily_index_on_or_after(daily_df, reference_date)
        monthly_index = get_monthly_index_from_selected_date(monthly_df, reference_date)

    # =========================================================
    # MODE 3: USER EXPORT DARI MONTHLY VIEW
    # Monthly menjadi acuan utama.
    # Daily mengikuti awal bulan tersebut.
    # Weekly mengikuti minggu dari awal bulan tersebut.
    # =========================================================
    elif selected_type == "monthly":
        monthly_index = get_monthly_index_by_month(monthly_df, selected_month)
        monthly_row_temp = monthly_df.loc[monthly_index]

        reference_date = get_reference_date_from_monthly_row(monthly_row_temp)

        daily_index = get_daily_index_on_or_after(daily_df, reference_date)
        weekly_index = get_weekly_index_from_selected_date(weekly_df, reference_date)

    # =========================================================
    # FALLBACK
    # =========================================================
    else:
        if not selected_date and not daily_df.empty:
            selected_date = str(daily_df.iloc[0].get("ds", ""))

        daily_index = get_daily_index_from_selected_date(daily_df, selected_date)
        reference_date = pd.to_datetime(daily_df.loc[daily_index].get("ds"))

        weekly_index = get_weekly_index_from_selected_date(weekly_df, reference_date)
        monthly_index = get_monthly_index_from_selected_date(monthly_df, reference_date)

    # =========================================================
    # SELECTED ROW
    # =========================================================
    daily_row = daily_df.loc[daily_index] if not daily_df.empty else pd.Series()
    weekly_row = weekly_df.loc[weekly_index] if not weekly_df.empty else pd.Series()
    monthly_row = monthly_df.loc[monthly_index] if not monthly_df.empty else pd.Series()

    daily_position = daily_df.index.get_loc(daily_index) if daily_index in daily_df.index else 0
    weekly_position = weekly_df.index.get_loc(weekly_index) if weekly_index in weekly_df.index else 0
    monthly_position = monthly_df.index.get_loc(monthly_index) if monthly_index in monthly_df.index else 0

    daily_window = daily_df.iloc[daily_position:daily_position + 7]
    weekly_window = weekly_df.iloc[weekly_position:weekly_position + 7]
    monthly_window = monthly_df.iloc[monthly_position:monthly_position + 7]

    # =========================================================
    # DAILY INSIGHT
    # =========================================================
    daily_full_count = 0
    daily_warning_count = 0
    daily_normal_count = 0

    for _, row in daily_window.iterrows():
        for col in STATUS_COLS:
            status = str(row.get(col, "Normal"))

            if status == "Full":
                daily_full_count += 1
            elif status == "Warning":
                daily_warning_count += 1
            else:
                daily_normal_count += 1

    daily_total = int(daily_row.get("total_vehicles", 0) or 0)
    daily_selected_date = str(daily_row.get("ds", "-"))

    daily_avg_total = int(daily_window["total_vehicles"].mean()) if not daily_window.empty else 0
    daily_occupancy = min(99, max(0, round((daily_avg_total / 1500) * 100)))

    if daily_full_count > 0:
        daily_condition = "High Risk"
        daily_recommendation = "Prepare overflow parking and prioritize areas with Full status."
    elif daily_warning_count > 0:
        daily_condition = "Needs Monitoring"
        daily_recommendation = "Monitor Warning areas before they become full."
    else:
        daily_condition = "Stable"
        daily_recommendation = "Continue normal parking operation."

    # =========================================================
    # WEEKLY INSIGHT
    # =========================================================
    weekly_high_count = 0
    weekly_moderate_count = 0
    weekly_good_count = 0

    for _, row in weekly_window.iterrows():
        for area in AREA_CODES:
            level = get_weekly_level(row, area)

            if level == "High":
                weekly_high_count += 1
            elif level == "Moderate":
                weekly_moderate_count += 1
            else:
                weekly_good_count += 1

    weekly_total = int(weekly_row.get("total_vehicles", 0) or 0)
    weekly_selected = f"W{int(weekly_row.get('week', 0) or 0)}"

    if weekly_high_count > 0:
        weekly_condition = "Needs Attention"
        weekly_recommendation = "Review High areas and adjust weekly parking allocation."
    elif weekly_moderate_count > 0:
        weekly_condition = "Needs Monitoring"
        weekly_recommendation = "Monitor Moderate areas during peak periods."
    else:
        weekly_condition = "Stable"
        weekly_recommendation = "Continue standard weekly monitoring."

    # =========================================================
    # MONTHLY INSIGHT
    # =========================================================
    monthly_increase_count = 0
    monthly_decrease_count = 0
    monthly_stable_count = 0
    monthly_start_count = 0

    for row_index in range(monthly_position, min(monthly_position + 7, len(monthly_df))):
        for area in AREA_CODES:
            trend = get_monthly_trend(monthly_df, row_index, area)

            if trend == "Increase":
                monthly_increase_count += 1
            elif trend == "Decrease":
                monthly_decrease_count += 1
            elif trend == "Stable":
                monthly_stable_count += 1
            else:
                monthly_start_count += 1

    monthly_total = int(monthly_row.get("total_vehicles", 0) or 0)
    monthly_number = int(monthly_row.get("month", 0) or 0)
    monthly_selected = month_name(monthly_number)

    if monthly_decrease_count > 0:
        monthly_condition = "Planning Required"
        monthly_recommendation = "Review areas with decreasing availability for capacity planning."
    elif monthly_increase_count > 0:
        monthly_condition = "Availability Improved"
        monthly_recommendation = "Use monthly availability trend to support future parking capacity planning."
    else:
        monthly_condition = "Stable"
        monthly_recommendation = "Continue monthly parking monitoring."

    # =========================================================
    # AREA ATTENTION SUMMARY
    # =========================================================
    area_summary = build_area_attention_summary(
        daily_row=daily_row,
        weekly_row=weekly_row,
        monthly_df=monthly_df,
        monthly_index=monthly_position,
    )

    high_priority_count = sum(1 for item in area_summary if item["priority"] == "High")
    medium_priority_count = sum(1 for item in area_summary if item["priority"] == "Medium")
    low_priority_count = sum(1 for item in area_summary if item["priority"] == "Low")

    executive_summary = [
        "Parking demand forecast shows selected areas require operational monitoring.",
        "Daily forecast is used for operational risk by identifying Full and Warning conditions.",
        "Weekly forecast is aligned with the selected report perspective to monitor area demand contribution.",
        "Monthly forecast is aligned with the selected report perspective to support capacity planning based on availability trend.",
    ]

    context = {
        "report_date": date.today().strftime("%d %B %Y"),
        "report_year": 2026,
        "selected_type": selected_type,

        "daily_selected_date": daily_selected_date,
        "daily_total": daily_total,
        "daily_occupancy": daily_occupancy,
        "daily_full_count": daily_full_count,
        "daily_warning_count": daily_warning_count,
        "daily_normal_count": daily_normal_count,
        "daily_condition": daily_condition,
        "daily_recommendation": daily_recommendation,

        "weekly_selected": weekly_selected,
        "weekly_total": weekly_total,
        "weekly_high_count": weekly_high_count,
        "weekly_moderate_count": weekly_moderate_count,
        "weekly_good_count": weekly_good_count,
        "weekly_condition": weekly_condition,
        "weekly_recommendation": weekly_recommendation,

        "monthly_selected": monthly_selected,
        "monthly_total": monthly_total,
        "monthly_increase_count": monthly_increase_count,
        "monthly_decrease_count": monthly_decrease_count,
        "monthly_stable_count": monthly_stable_count,
        "monthly_start_count": monthly_start_count,
        "monthly_condition": monthly_condition,
        "monthly_recommendation": monthly_recommendation,

        "area_summary": area_summary,
        "high_priority_count": high_priority_count,
        "medium_priority_count": medium_priority_count,
        "low_priority_count": low_priority_count,

        "executive_summary": executive_summary,
    }

    return render(request, "forecast_app/management_report.html", context)