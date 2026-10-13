"""
Usage: python -m scripts.check_occupancy_data
"""

from app.db.session import SessionLocal
from app.core.config import settings
from app.db.models import OccupancySnapshot
from app.features.forecast.services.retrain import _zone_ids_by_key, _build_daily_series
 
 
def run():
    db = SessionLocal()
    try:
        total_rows = db.query(OccupancySnapshot).count()
        print(f"Total rows in occupancy_snapshot: {total_rows}\n")
 
        zone_ids = _zone_ids_by_key(db)
        if not zone_ids:
            print("No 'west'/'east' zone_key found in parking_zone table. Check your seed data")
            return
 
        for zone_key, zone_id in zone_ids.items():
            raw_count = (
                db.query(OccupancySnapshot)
                .filter(OccupancySnapshot.zone_id == zone_id)
                .count()
            )
            series = _build_daily_series(db, zone_id)
 
            print("=" * 60)
            print(f"Zone: {zone_key} (zone_id={zone_id})")
            print(f"Raw snapshot rows: {raw_count}")
            print(f"Daily data points after aggregation: {len(series)}")
            print(f"Minimum required to retrain: {settings.PROPHET_MIN_OBSERVATIONS}")
            print(f"Status: {'ENOUGH DATA' if len(series) >= settings.PROPHET_MIN_OBSERVATIONS else 'NOT ENOUGH YET'}")
 
            if len(series) > 0:
                print(f"Date range: {series.index.min().date()} -> {series.index.max().date()}")
                print("Last 7 daily values (overall_rate_pct avg):")
                print(series.tail(7).to_string())
            else:
                print("  No data at all for this zone yet")
            print()
 
        print("=" * 60)
        print(f"prophet.joblib path: {settings.PROPHET_MODEL_PATH}")
        if settings.PROPHET_MODEL_PATH.exists():
            import datetime
            mtime = datetime.datetime.fromtimestamp(settings.PROPHET_MODEL_PATH.stat().st_mtime)
            print(f"  Exists. Last modified: {mtime}")
        else:
            print("  Does not exist yet")
 
    finally:
        db.close()
 
 
if __name__ == "__main__":
    run()
