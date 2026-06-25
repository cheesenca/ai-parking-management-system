import os

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from forecast_app.forecast_generation import generate_forecasts
from forecast_app.models import DailyForecast, WeeklyForecast, MonthlyForecast


class Command(BaseCommand):
    help = "Generate forecast CSVs and import them into PostgreSQL via Django ORM"

    def add_arguments(self, parser):
        parser.add_argument(
            "--forecast-dir",
            default=None,
            help="Forecast CSV folder (default: <workspace>/forecast)",
        )
        parser.add_argument(
            "--start-date",
            default="2026-06-01",
            help="Forecast start date (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--end-date",
            default="2026-12-31",
            help="Forecast end date (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--generate-only",
            action="store_true",
            help="Generate forecast CSVs only and skip DB import.",
        )
        parser.add_argument(
            "--import-only",
            action="store_true",
            help="Import forecast CSVs only and skip CSV generation.",
        )

    def handle(self, *args, **options):
        forecast_dir = options["forecast_dir"]
        if forecast_dir is None:
            workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            forecast_dir = os.path.join(workspace_root, "forecast")

        if not options["import_only"]:
            self.stdout.write("Generating forecast CSVs...\n")
            generate_forecasts(
                start_date=options["start_date"],
                end_date=options["end_date"],
                forecast_folder=forecast_dir,
            )
            self.stdout.write(self.style.SUCCESS(f"Forecast CSVs generated in: {forecast_dir}"))

        if not options["generate_only"]:
            self.stdout.write("Importing forecast CSVs into PostgreSQL...\n")
            self._import_forecasts(forecast_dir)
            self.stdout.write(self.style.SUCCESS("Forecast import completed."))

    def _read_csv(self, filename, forecast_dir):
        path = os.path.join(forecast_dir, filename)
        if not os.path.exists(path):
            raise CommandError(f"Forecast CSV not found: {path}")
        return pd.read_csv(path)

    def _import_forecasts(self, forecast_dir):
        self._import_daily(forecast_dir)
        self._import_weekly(forecast_dir)
        self._import_monthly(forecast_dir)

    def _daily_defaults(self, row):
        return {
            "total_vehicles": int(row["total_vehicles"]),
            "P1W_predicted": float(row["P1W_predicted"]),
            "P1W_available": int(row["P1W_available"]),
            "P1W_status": str(row["P1W_status"]),
            "P1E_predicted": float(row["P1E_predicted"]),
            "P1E_available": int(row["P1E_available"]),
            "P1E_status": str(row["P1E_status"]),
            "P2W_predicted": float(row["P2W_predicted"]),
            "P2W_available": int(row["P2W_available"]),
            "P2W_status": str(row["P2W_status"]),
            "P2E_predicted": float(row["P2E_predicted"]),
            "P2E_available": int(row["P2E_available"]),
            "P2E_status": str(row["P2E_status"]),
            "P3W_predicted": float(row["P3W_predicted"]),
            "P3W_available": int(row["P3W_available"]),
            "P3W_status": str(row["P3W_status"]),
            "P3E_predicted": float(row["P3E_predicted"]),
            "P3E_available": int(row["P3E_available"]),
            "P3E_status": str(row["P3E_status"]),
        }

    def _import_daily(self, forecast_dir):
        df_daily = self._read_csv("daily_forecast.csv", forecast_dir)
        df_daily["ds"] = pd.to_datetime(df_daily["ds"]).dt.date

        inserted = 0
        for _, row in df_daily.iterrows():
            DailyForecast.objects.update_or_create(
                ds=row["ds"],
                defaults=self._daily_defaults(row),
            )
            inserted += 1

        self.stdout.write(self.style.SUCCESS(f"Imported {inserted} daily rows."))

    def _import_weekly(self, forecast_dir):
        df_weekly = self._read_csv("weekly_forecast.csv", forecast_dir)

        inserted = 0
        for _, row in df_weekly.iterrows():
            WeeklyForecast.objects.update_or_create(
                year=int(row["year"]),
                week=int(row["week"]),
                defaults=self._daily_defaults(row),
            )
            inserted += 1

        self.stdout.write(self.style.SUCCESS(f"Imported {inserted} weekly rows."))

    def _import_monthly(self, forecast_dir):
        df_monthly = self._read_csv("monthly_forecast.csv", forecast_dir)

        inserted = 0
        for _, row in df_monthly.iterrows():
            MonthlyForecast.objects.update_or_create(
                year=int(row["year"]),
                month=int(row["month"]),
                defaults=self._daily_defaults(row),
            )
            inserted += 1

        self.stdout.write(self.style.SUCCESS(f"Imported {inserted} monthly rows."))
