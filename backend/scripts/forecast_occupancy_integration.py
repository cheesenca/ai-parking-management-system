"""
Usage: python -m scripts.forecast_occupancy_integration or python -m scripts.forecast_occupancy_integration --zone west --cleanup
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import AnalyticsData, OccupancySnapshot, ParkingZone
from app.features.forecast.services.retrain import (
    AREA_ZONE_MAP,
    retrain_all_zones,
)

SPIKE_RATE_PCT = 98.0  
SPIKE_DAYS = 5


def _get_zone_id(db, zone_key: str) -> int | None:
    row = db.query(ParkingZone.zone_id).filter(ParkingZone.zone_key == zone_key).first()
    return row[0] if row else None


def _snapshot_count(db, zone_id: int) -> int:
    return (
        db.query(OccupancySnapshot)
        .filter(OccupancySnapshot.zone_id == zone_id)
        .count()
    )


def _current_predicted_demand(db, area_code: str, days_ahead: int = 1) -> int | None:
    target_date = datetime.now().date() + timedelta(days=days_ahead)
    row = (
        db.query(AnalyticsData.predicted_demand)
        .filter_by(area_code=area_code, period_type="daily", record_date=target_date)
        .first()
    )
    return row[0] if row else None


def _insert_spike_snapshots(db, zone_id: int) -> list[int]:
    created_ids: list[int] = []
    now = datetime.now()
    for i in range(SPIKE_DAYS):
        recorded_at = (now - timedelta(days=i)).replace(hour=23, minute=59, second=0, microsecond=0)
        snapshot = OccupancySnapshot(
            zone_id=zone_id,
            recorded_at=recorded_at,
            total_capacity=900,
            total_occupied=int(900 * SPIKE_RATE_PCT / 100),
            total_available=900 - int(900 * SPIKE_RATE_PCT / 100),
            overall_rate_pct=SPIKE_RATE_PCT,
        )
        db.add(snapshot)
        db.flush()
        created_ids.append(snapshot.snapshot_id)
    db.commit()
    return created_ids


def _cleanup_snapshots(db, snapshot_ids: list[int]) -> None:
    db.query(OccupancySnapshot).filter(OccupancySnapshot.snapshot_id.in_(snapshot_ids)).delete(
        synchronize_session=False
    )
    db.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zone", choices=["west", "east"], default="west",
                         help="Zone to be tested (default: west)")
    parser.add_argument("--cleanup", action="store_true",
                         help="Delete trial snapshots after verification is complete")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        zone_id = _get_zone_id(db, args.zone)
        if zone_id is None:
            print(f"[FAILED] Zone '{args.zone}' not found in parking_zone table.")
            return 1

        area_code = next(a for a, z in AREA_ZONE_MAP.items() if z == args.zone)

        n_points = _snapshot_count(db, zone_id)
        print(f"== Verifying occupancy -> predictive analytics integration (zone: {args.zone}) ==")
        print(f"- Current number of OccupancySnapshots for zone '{args.zone}': {n_points}")
        print(f"- Minimum required by the model (PROPHET_MIN_OBSERVATIONS): {settings.PROPHET_MIN_OBSERVATIONS}")

        if n_points < settings.PROPHET_MIN_OBSERVATIONS:
            print(
                "[WARNING] Historical data is insufficient to retrain Prophet. "
                "Retrain will be skipped (status 'insufficient_data'), so the causality test "
                "below cannot be run validly. Add more occupancy data first, or run without "
                "this option to only see the baseline."
            )

        baseline = _current_predicted_demand(db, area_code)
        print(f"- Current predicted_demand for area '{area_code}' (tomorrow): {baseline}")

        print("\n-> Inserting 'spike' occupancy snapshots (causality test)...")
        snapshot_ids = _insert_spike_snapshots(db, zone_id)
        print(f"   {len(snapshot_ids)} new snapshots added (overall_rate_pct={SPIKE_RATE_PCT}%).")

        print("\n-> Running retrain_all_zones() ...")
        results = retrain_all_zones()
        zone_result = results.get(args.zone, {})
        print(f"   Retrain result for zone '{args.zone}': {zone_result}")

        db.expire_all()
        after = _current_predicted_demand(db, area_code)
        print(f"\n- predicted_demand AFTER retrain for area '{area_code}' (tomorrow): {after}")

        print("\n== RESULTS ==")
        if zone_result.get("status") not in ("retrained",):
            print(f"[INCONCLUSIVE] Retrain status is not 'retrained' (status={zone_result.get('status')}, "
                  f"reason={zone_result.get('reason')}). The model was not updated, so integration was not "
                  f"tested in this run.")
            verdict = 2
        elif baseline is None or after is None:
            print("[INCONCLUSIVE] No predicted_demand data to compare. "
                  "It's possible sync_forecast_to_analytics_data() has never run successfully.")
            verdict = 2
        elif after != baseline:
            print(f"[PASS] predicted_demand changed from {baseline} -> {after} after 'spike' occupancy data "
                  f"was inserted and the model was retrained. Occupancy -> predictive "
                  f"analytics integration is PROVEN to work.")
            verdict = 0
        else:
            print(f"[FAIL] predicted_demand DID NOT change ({baseline} -> {after}) even though occupancy data "
                  f"was drastically increased. Check logs for 'Failed to sync forecast into analytics_data' "
                  f"or the possibility that the model was not retrained.")
            verdict = 1

        if args.cleanup:
            print("\n-> Cleaning up trial snapshots...")
            _cleanup_snapshots(db, snapshot_ids)
            print("   Done.")
        else:
            print(f"\n(Trial snapshots were NOT automatically deleted. IDs: {snapshot_ids}. "
                  f"Rerun with --cleanup to clean them up, or retrain again "
                  f"later so the model relearns from the original occupancy data.)")

        return verdict
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())