from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.forecast_dashboard, name="forecast_dashboard"),
    path("management-report/", views.management_report, name="management_report"),
]