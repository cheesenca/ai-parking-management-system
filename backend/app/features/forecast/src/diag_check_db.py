import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','capstone_parking.settings')
import django
django.setup()
from forecast_app.models import DailyForecast, WeeklyForecast, MonthlyForecast
from django.db.models import Max, Min
print('Daily count', DailyForecast.objects.count())
print('Daily min', DailyForecast.objects.aggregate(Min('ds')))
print('Daily max', DailyForecast.objects.aggregate(Max('ds')))
print('Weekly count', WeeklyForecast.objects.count())
print('Weekly min', WeeklyForecast.objects.aggregate(Min('week')))
print('Weekly max', WeeklyForecast.objects.aggregate(Max('week')))
print('Monthly count', MonthlyForecast.objects.count())
print('Monthly min', MonthlyForecast.objects.aggregate(Min('month')))
print('Monthly max', MonthlyForecast.objects.aggregate(Max('month')))
