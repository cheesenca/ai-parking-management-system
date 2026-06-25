import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','capstone_parking.settings')
import django
django.setup()
from forecast_app.models import DailyForecast, WeeklyForecast, MonthlyForecast

print('\n--- Weekly samples ---')
for w in WeeklyForecast.objects.filter(year=2026).order_by('week')[:5]:
    print(w.week, w.total_vehicles, w.P1W_status, w.P1E_status, w.P2W_status, w.P3W_status)

print('\n--- Monthly samples ---')
for m in MonthlyForecast.objects.filter(year=2026).order_by('month')[:5]:
    print(m.month, m.total_vehicles, m.P1W_status, m.P2W_status)

print('\n--- Daily samples end ---')
for d in DailyForecast.objects.filter(ds__year=2026).order_by('ds')[-5:]:
    print(d.ds, d.total_vehicles, d.P1W_status, d.P2W_status)
