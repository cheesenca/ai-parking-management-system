"""
One-off historical backfill: imports Parking_Scan_Data.xlsx (real KPK card-scan
records) into EntryExitLog, and derives resampled OccupancySnapshot rows from a
reconstructed running occupancy count per zone. Not part of the live app — run
once, manually:

    cd backend
    python scripts/backfill_historical_data.py --xlsx-path "D:\\Capstone\\Parking_Scan_Data.xlsx"
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import insert


def _bootstrap(f: str) -> None:
    p = Path(f).resolve()
    proj = None
    for parent in p.parents:
        if (parent / "requirements.txt").exists() and (parent / "app").is_dir():
            proj = parent
            break
    if proj and str(proj) not in sys.path:
        sys.path.insert(0, str(proj))


_bootstrap(__file__)

<<<<<<< HEAD
from app.core.database import SessionLocal  # noqa: E402
from app.core.models import EntryExitLog, OccupancySnapshot, ParkingZone  # noqa: E402
=======
from app.db.session import SessionLocal  # noqa: E402
from app.db.models import EntryExitLog, OccupancySnapshot, ParkingZone  # noqa: E402
>>>>>>> origin/master
from app.features.forecast.services.retrain import _category_split  # noqa: E402

logger = logging.getLogger(__name__)

ZONE_SUFFIX_MAP = {"W": "west", "E": "east"}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Backfill historical KPK scan data into EntryExitLog/OccupancySnapshot")
    ap.add_argument("--xlsx-path", default=str(Path(__file__).resolve().parents[2] / "Parking_Scan_Data.xlsx"))
    ap.add_argument("--sheet-name", default="Scan Data")
    ap.add_argument("--chunk-size", type=int, default=5000)
    ap.add_argument("--snapshot-interval", default="1h")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    return ap.parse_args()


def load_scan_data(xlsx_path: str, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name, engine="openpyxl")

    if pd.api.types.is_numeric_dtype(df["TIME_SCAN"]):
        df["event_timestamp"] = pd.to_datetime(df["TIME_SCAN"], unit="D", origin="1899-12-30")
    else:
        df["event_timestamp"] = pd.to_datetime(df["TIME_SCAN"])

    df["zone_key"] = df["POS_PARK_LOCATION"].astype(str).str[-1].map(ZONE_SUFFIX_MAP)
    bad = df["zone_key"].isna()
    if bad.any():
        logger.warning(
            "Dropping %d row(s) with unrecognized POS_PARK_LOCATION: %s",
            int(bad.sum()), sorted(df.loc[bad, "POS_PARK_LOCATION"].astype(str).unique()),
        )
        df = df[~bad]

    df["event_type"] = df["SCAN_FOR_POSITION"].map({"IN": "Entry", "OUT": "Exit"})
    df["plate_detected"] = ("KPK-" + df["MEMBER_KPK"].astype(str)).str.slice(0, 20)

    return df.sort_values(["zone_key", "event_timestamp"]).reset_index(drop=True)


def chunked_insert(db, table, records: list[dict], chunk_size: int, label: str) -> int:
    total = len(records)
    for i in range(0, total, chunk_size):
        chunk = records[i:i + chunk_size]
        db.execute(insert(table), chunk)
        db.commit()
        logger.info("%s: %d/%d rows", label, min(i + chunk_size, total), total)
    return total


def build_entry_exit_rows(df: pd.DataFrame, zone_ids: dict[str, int]) -> list[dict]:
    out = pd.DataFrame({
        "session_id": None,
        "admin_id": None,
        "zone_id": df["zone_key"].map(zone_ids),
        "event_type": df["event_type"],
        "plate_detected": df["plate_detected"],
        "confidence_score": None,
        "event_timestamp": df["event_timestamp"].dt.to_pydatetime(),
        "auth_method": "KPK_Scan",
    })
    return out.to_dict("records")


def derive_occupancy_snapshots(df: pd.DataFrame, zones: dict[str, "ParkingZone"], interval: str) -> list[dict]:
    """
    Reconstructs a running occupied-count per zone from sequential Entry/Exit
    events, then resamples the stepped series to one row per `interval` instead
    of one row per raw scan event.
    """
    rows: list[dict] = []
    for zone_key, group in df.groupby("zone_key", sort=False):
        zone = zones[zone_key]
        delta = group["event_type"].map({"Entry": 1, "Exit": -1})
        running = delta.cumsum().clip(lower=0)
        stepped = pd.Series(running.values, index=pd.DatetimeIndex(group["event_timestamp"].values))
        stepped = stepped[~stepped.index.duplicated(keep="last")].sort_index()

        resampled = stepped.resample(interval).last().ffill().fillna(0)
        resampled = resampled.clip(lower=0, upper=zone.total_capacity)

        for ts, occupied in resampled.items():
            occupied = int(occupied)
            emp, ven, vis = _category_split(occupied, zone.employee_capacity, zone.vendor_capacity, zone.visitor_capacity)
            total_cap = zone.total_capacity
            rows.append({
                "zone_id": zone.zone_id,
                "recorded_at": ts.to_pydatetime(),
                "total_capacity": total_cap,
                "total_occupied": occupied,
                "total_available": max(0, total_cap - occupied),
                "overall_rate_pct": round(occupied / total_cap * 100, 1) if total_cap else 0.0,
                "employee_used": emp,
                "employee_total": zone.employee_capacity,
                "vendor_used": ven,
                "vendor_total": zone.vendor_capacity,
                "visitor_used": vis,
                "visitor_total": zone.visitor_capacity,
            })
    return rows


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    logger.info("Loading %s ...", args.xlsx_path)
    df = load_scan_data(args.xlsx_path, args.sheet_name)
    logger.info(
        "Loaded %d usable row(s) spanning %s to %s",
        len(df), df["event_timestamp"].min(), df["event_timestamp"].max(),
    )

    db = SessionLocal()
    try:
        zones = {z.zone_key: z for z in db.query(ParkingZone).filter(ParkingZone.zone_key.in_(["west", "east"])).all()}
        missing = set(df["zone_key"].unique()) - set(zones)
        if missing:
            raise SystemExit(f"ParkingZone row(s) missing for: {sorted(missing)} — seed the database first")

        if not args.force:
            already = db.query(EntryExitLog).filter(EntryExitLog.auth_method == "KPK_Scan").first()
            if already is not None:
                raise SystemExit("Historical backfill already applied (KPK_Scan rows found). Pass --force to re-run.")

        entry_exit_rows = build_entry_exit_rows(df, {k: z.zone_id for k, z in zones.items()})
        snapshot_rows = derive_occupancy_snapshots(df, zones, args.snapshot_interval)
        logger.info(
            "Prepared %d EntryExitLog row(s) and %d OccupancySnapshot row(s)",
            len(entry_exit_rows), len(snapshot_rows),
        )

        if args.dry_run:
            logger.info("Dry run — no rows written.")
            return

        chunked_insert(db, EntryExitLog, entry_exit_rows, args.chunk_size, "EntryExitLog")
        chunked_insert(db, OccupancySnapshot, snapshot_rows, args.chunk_size, "OccupancySnapshot")

        logger.info(
            "Backfill complete. Call POST /api/v1/forecast/retrain to populate AnalyticsData "
            "now, or wait for the nightly 02:00 job."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
