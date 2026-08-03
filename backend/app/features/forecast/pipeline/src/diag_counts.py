import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','capstone_parking.settings')
import django
django.setup()
from app.features.forecast.pipeline.src.forecast_app.models import WeeklyForecast, MonthlyForecast

for model,name in [(WeeklyForecast,'weekly'),(MonthlyForecast,'monthly')]:
    qs = model.objects.filter(year=2026)
    counts={'Normal':0,'Warning':0,'Full':0}
    for item in qs:
        for field in ['P1W_status','P1E_status','P2W_status','P2E_status','P3W_status','P3E_status']:
            st=getattr(item,field)
            if st in counts:
                counts[st]+=1
    print(name,'counts',counts)
