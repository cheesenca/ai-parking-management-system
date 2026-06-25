import os
import sys
import pandas as pd
import django

# Setup Django
app_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(app_dir)
sys.path.insert(0, project_root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "capstone_parking.settings")
django.setup()

from forecast_app.models import DailyForecast, WeeklyForecast, MonthlyForecast

workspace_root = os.path.dirname(project_root)
forecast_folder = os.path.join(workspace_root, 'forecast')

# ====== 1. Daily Forecast ======
daily_path = os.path.join(forecast_folder, 'daily_forecast.csv')
df_daily = pd.read_csv(daily_path)
df_daily['ds'] = pd.to_datetime(df_daily['ds'])

for _, row in df_daily.iterrows():
    ds_value = row['ds'].strftime('%Y-%m-%d')
    DailyForecast.objects.update_or_create(
        ds=ds_value,
        defaults={
            'total_vehicles': row['total_vehicles'],
            'P1W_predicted': row['P1W_predicted'],
            'P1W_available': row['P1W_available'],
            'P1W_status': row['P1W_status'],
            'P1E_predicted': row['P1E_predicted'],
            'P1E_available': row['P1E_available'],
            'P1E_status': row['P1E_status'],
            'P2W_predicted': row['P2W_predicted'],
            'P2W_available': row['P2W_available'],
            'P2W_status': row['P2W_status'],
            'P2E_predicted': row['P2E_predicted'],
            'P2E_available': row['P2E_available'],
            'P2E_status': row['P2E_status'],
            'P3W_predicted': row['P3W_predicted'],
            'P3W_available': row['P3W_available'],
            'P3W_status': row['P3W_status'],
            'P3E_predicted': row['P3E_predicted'],
            'P3E_available': row['P3E_available'],
            'P3E_status': row['P3E_status'],
        }
    )
print("Daily forecast 2026 berhasil masuk DB!")

# ====== 2. Weekly Forecast ======
weekly_path = os.path.join(forecast_folder, 'weekly_forecast.csv')
df_weekly = pd.read_csv(weekly_path)

for _, row in df_weekly.iterrows():
    WeeklyForecast.objects.update_or_create(
        year=row['year'],
        week=row['week'],
        defaults={
            'total_vehicles': row['total_vehicles'],
            'P1W_predicted': row['P1W_predicted'],
            'P1W_available': row['P1W_available'],
            'P1W_status': row['P1W_status'],
            'P1E_predicted': row['P1E_predicted'],
            'P1E_available': row['P1E_available'],
            'P1E_status': row['P1E_status'],
            'P2W_predicted': row['P2W_predicted'],
            'P2W_available': row['P2W_available'],
            'P2W_status': row['P2W_status'],
            'P2E_predicted': row['P2E_predicted'],
            'P2E_available': row['P2E_available'],
            'P2E_status': row['P2E_status'],
            'P3W_predicted': row['P3W_predicted'],
            'P3W_available': row['P3W_available'],
            'P3W_status': row['P3W_status'],
            'P3E_predicted': row['P3E_predicted'],
            'P3E_available': row['P3E_available'],
            'P3E_status': row['P3E_status'],
        }
    )
print("Weekly forecast 2026 berhasil masuk DB!")

# ====== 3. Monthly Forecast ======
monthly_path = os.path.join(forecast_folder, 'monthly_forecast.csv')
df_monthly = pd.read_csv(monthly_path)

for _, row in df_monthly.iterrows():
    MonthlyForecast.objects.update_or_create(
        year=row['year'],
        month=row['month'],
        defaults={
            'total_vehicles': row['total_vehicles'],
            'P1W_predicted': row['P1W_predicted'],
            'P1W_available': row['P1W_available'],
            'P1W_status': row['P1W_status'],
            'P1E_predicted': row['P1E_predicted'],
            'P1E_available': row['P1E_available'],
            'P1E_status': row['P1E_status'],
            'P2W_predicted': row['P2W_predicted'],
            'P2W_available': row['P2W_available'],
            'P2W_status': row['P2W_status'],
            'P2E_predicted': row['P2E_predicted'],
            'P2E_available': row['P2E_available'],
            'P2E_status': row['P2E_status'],
            'P3W_predicted': row['P3W_predicted'],
            'P3W_available': row['P3W_available'],
            'P3W_status': row['P3W_status'],
            'P3E_predicted': row['P3E_predicted'],
            'P3E_available': row['P3E_available'],
            'P3E_status': row['P3E_status'],
        }
    )
print("Monthly forecast 2026 berhasil masuk DB!")