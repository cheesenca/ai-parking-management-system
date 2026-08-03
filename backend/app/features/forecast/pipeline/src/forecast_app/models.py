# forecast_app/models.py
from django.db import models

# ====== Daily Forecast ======
class DailyForecast(models.Model):
    ds = models.DateField(unique=True)
    yhat = models.FloatField()
    total_vehicles = models.FloatField()
    P1W_predicted = models.FloatField()
    P1W_available = models.FloatField()
    P1W_status = models.CharField(max_length=10)
    P1E_predicted = models.FloatField()
    P1E_available = models.FloatField()
    P1E_status = models.CharField(max_length=10)
    P2W_predicted = models.FloatField()
    P2W_available = models.FloatField()
    P2W_status = models.CharField(max_length=10)
    P2E_predicted = models.FloatField()
    P2E_available = models.FloatField()
    P2E_status = models.CharField(max_length=10)
    P3W_predicted = models.FloatField()
    P3W_available = models.FloatField()
    P3W_status = models.CharField(max_length=10)
    P3E_predicted = models.FloatField()
    P3E_available = models.FloatField()
    P3E_status = models.CharField(max_length=10)

    class Meta:
        db_table = 'daily_forecast'
    
    def __str__(self):
        return f"Forecast {self.ds} - {int(self.total_vehicles)} vehicles"

# ====== Weekly Forecast ======
class WeeklyForecast(models.Model):
    year = models.IntegerField()
    week = models.IntegerField()
    total_vehicles = models.FloatField()
    P1W_predicted = models.FloatField()
    P1W_available = models.FloatField()
    P1W_status = models.CharField(max_length=10)
    P1E_predicted = models.FloatField()
    P1E_available = models.FloatField()
    P1E_status = models.CharField(max_length=10)
    P2W_predicted = models.FloatField()
    P2W_available = models.FloatField()
    P2W_status = models.CharField(max_length=10)
    P2E_predicted = models.FloatField()
    P2E_available = models.FloatField()
    P2E_status = models.CharField(max_length=10)
    P3W_predicted = models.FloatField()
    P3W_available = models.FloatField()
    P3W_status = models.CharField(max_length=10)
    P3E_predicted = models.FloatField()
    P3E_available = models.FloatField()
    P3E_status = models.CharField(max_length=10)

    class Meta:
        db_table = 'weekly_forecast'
        unique_together = ('year', 'week')
    
    def __str__(self):
        return f"Week {self.week} {self.year}"

# ====== Monthly Forecast ======
class MonthlyForecast(models.Model):
    year = models.IntegerField()
    month = models.IntegerField()
    total_vehicles = models.FloatField()
    P1W_predicted = models.FloatField()
    P1W_available = models.FloatField()
    P1W_status = models.CharField(max_length=10)
    P1E_predicted = models.FloatField()
    P1E_available = models.FloatField()
    P1E_status = models.CharField(max_length=10)
    P2W_predicted = models.FloatField()
    P2W_available = models.FloatField()
    P2W_status = models.CharField(max_length=10)
    P2E_predicted = models.FloatField()
    P2E_available = models.FloatField()
    P2E_status = models.CharField(max_length=10)
    P3W_predicted = models.FloatField()
    P3W_available = models.FloatField()
    P3W_status = models.CharField(max_length=10)
    P3E_predicted = models.FloatField()
    P3E_available = models.FloatField()
    P3E_status = models.CharField(max_length=10)

    class Meta:
        db_table = 'monthly_forecast'
        unique_together = ('year', 'month')
    
    def __str__(self):
        months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        return f"{months[self.month]} {self.year}"