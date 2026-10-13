"""
Usage:
    python -m scripts.seed_occupancy_history
    python -m scripts.seed_occupancy_history --zone west --days 60
    python -m scripts.seed_occupancy_history --zone west --days 60 --wipe-existing
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

<<<<<<< HEAD
from app.core.database import SessionLocal
from app.core.models import OccupancySnapshot, ParkingZone
=======
from app.db.session import SessionLocal
from app.db.models import OccupancySnapshot, ParkingZone
>>>>>>> origin/master

N_DAYS_DEFAULT = 60
RANDOM_SEED = 42


def _get_zone(db, zone_key: str) -> ParkingZone | None:
    return db.query(ParkingZone).filter(ParkingZone.zone_key == zone_key).first()


def _existing_dates(db, zone_id: int) -> set:
    rows = (
        db.query(OccupancySnapshot.recorded_at)
        .filter(OccupancySnapshot.zone_id == zone_id)
        .all()
    )
    return {r[0].date() for r in rows}


def _rate_for_day(day_index: int, weekday: int) -> float:
    """
    Weekly pattern: lower occupancy on weekends (Sat=5, Sun=6),
    a mild upward trend over time, plus small random noise.
    Clamped to a sane 40-99% band.
    """
    base = 60.0
    trend = min(day_index * 0.25, 20.0)  # gentle rise over the window
    weekend_dip = -20.0 if weekday >= 5 else 0.0
    noise = random.uniform(-6.0, 6.0)
    rate = base + trend + weekend_dip + noise
    return max(40.0, min(99.0, rate))


def seed_zone(db, zone: ParkingZone, days: int, wipe_existing: bool) -> int:
    if wipe_existing:
        deleted = (
            db.query(OccupancySnapshot)
            .filter(OccupancySnapshot.zone_id == zone.zone_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        print(f"   [zone={zone.zone_key}] wiped {deleted} existing snapshot(s).")

    existing = _existing_dates(db, zone.zone_id)
    capacity = zone.total_capacity or 900
    today = datetime.now().date()

    created = 0
    random.seed(RANDOM_SEED + zone.zone_id)  # reproducible per zone
    for i in range(days, 0, -1):
        day = today - timedelta(days=i)
        if day in existing:
            continue  # don't create a second snapshot for a day that already has one

        rate = _rate_for_day(day_index=days - i, weekday=day.weekday())
        occupied = int(round(capacity * rate / 100.0))
        occupied = min(occupied, capacity)
        available = capacity - occupied

        recorded_at = datetime.combine(day, datetime.min.time()).replace(hour=23, minute=59)

        snapshot = OccupancySnapshot(
            zone_id=zone.zone_id,
            recorded_at=recorded_at,
            total_capacity=capacity,
            total_occupied=occupied,
            total_available=available,
            overall_rate_pct=round(rate, 2),
        )
        db.add(snapshot)
        created += 1

    db.commit()
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zone", choices=["west", "east", "all"], default="all",
                         help="Zone to seed (default: all)")
    parser.add_argument("--days", type=int, default=N_DAYS_DEFAULT,
                         help=f"Number of past calendar days to seed (default: {N_DAYS_DEFAULT})")
    parser.add_argument("--wipe-existing", action="store_true",
                         help="Delete all existing snapshots for the zone(s) before seeding")
    args = parser.parse_args()

    zone_keys = ["west", "east"] if args.zone == "all" else [args.zone]

    db = SessionLocal()
    try:
        print(f"== Seeding {args.days} days of occupancy history ==")
        for zk in zone_keys:
            zone = _get_zone(db, zk)
            if zone is None:
                print(f"[SKIP] Zone '{zk}' not found in parking_zone table.")
                continue
            created = seed_zone(db, zone, args.days, args.wipe_existing)
            print(f"   [zone={zk}] {created} new day(s) inserted.")

        print("\nDone. Now run:")
        print("   python -m scripts.forecast_occupancy_integration --zone west --cleanup")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())