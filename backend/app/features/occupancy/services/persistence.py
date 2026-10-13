from __future__ import annotations

import logging
import time
from datetime import datetime

from app.core.config import settings
from app.db.session import session_local
from app.db.models import OccupancySnapshot, ParkingSlot, ParkingZone

logger = logging.getLogger(__name__)

_last_snapshot_at: dict[str, float] = {}

def persist_slot_update(zone_key: str, status: dict[str, str], id_to_category: dict[str, str]) -> None:
    """Storing or updating live status data from parking slot detection directly into the database"""
    if not status:
        return

    db = session_local()
    try:
        zone = db.query(ParkingZone).filter(ParkingZone.zone_key == zone_key).first()
        if not zone:
            return

        existing = {
            slot.slot_label: slot
            for slot in db.query(ParkingSlot)
            .filter(
                ParkingSlot.zone_id == zone.zone_id,
                ParkingSlot.slot_label.in_(status.keys()),
            )
            .all()
        }

        used_by_cat: dict[str, int] = {}
        new_slots: list[ParkingSlot] = []

        for slot_id, slot_status in status.items():
            category = id_to_category.get(slot_id, "Employee")
            slot = existing.get(slot_id)
            if slot:
                slot.current_status = slot_status
                slot.category = category
            else:
                new_slots.append(ParkingSlot(
                    zone_id=zone.zone_id, slot_label=slot_id, category=category,
                    current_status=slot_status, coordinates_polygon=[],
                ))
            if slot_status == "Occupied":
                used_by_cat[category] = used_by_cat.get(category, 0) + 1

        if new_slots:
            db.bulk_save_objects(new_slots)

        zone.employee_used = used_by_cat.get("Employee", 0)
        zone.vendor_used = used_by_cat.get("Vendor", 0)
        zone.visitor_used = used_by_cat.get("Visitor", 0)
        zone.used_capacity = sum(used_by_cat.values())

        _maybe_write_snapshot(db, zone, zone_key)

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Database write failed for zone=%s: %s", zone_key, exc)
    finally:
        db.close()


def _maybe_write_snapshot(db, zone: ParkingZone, zone_key: str) -> None:
    """Write a snapshot of the current occupancy status to the database"""
    now = time.time()
    if now - _last_snapshot_at.get(zone_key, 0) < settings.OCCUPANCY_SNAPSHOT_INTERVAL_SEC:
        return

    total_occupied = zone.used_capacity
    rate = round(total_occupied / zone.total_capacity * 100, 1) if zone.total_capacity else 0.0
    db.add(OccupancySnapshot(
        zone_id=zone.zone_id,
        recorded_at=datetime.now(),
        total_capacity=zone.total_capacity,
        total_occupied=total_occupied,
        total_available=max(0, zone.total_capacity - total_occupied),
        overall_rate_pct=rate,
        employee_used=zone.employee_used,
        employee_total=zone.employee_capacity,
        vendor_used=zone.vendor_used,
        vendor_total=zone.vendor_capacity,
        visitor_used=zone.visitor_used,
        visitor_total=zone.visitor_capacity,
    ))
    _last_snapshot_at[zone_key] = now
    logger.info(
        "zone=%s OccupancySnapshot written: %s/%s occupied (%.1f%%)",
        zone_key, total_occupied, zone.total_capacity, rate,
    )


def sync_calibration_to_db(zone_key: str, slots: list[dict]) -> None:
    """Sync the latest calibration polygons to the database for a given parking zone"""
    db = session_local()
    try:
        zone = db.query(ParkingZone).filter(ParkingZone.zone_key == zone_key).first()
        if not zone:
            return

        slot_ids = [s["id"] for s in slots]
        existing = {
            slot.slot_label: slot
            for slot in db.query(ParkingSlot)
            .filter(ParkingSlot.zone_id == zone.zone_id, ParkingSlot.slot_label.in_(slot_ids))
            .all()
        }

        new_slots = []
        for s in slots:
            slot = existing.get(s["id"])
            if slot:
                slot.coordinates_polygon = s["polygon"]
                slot.category = s["category"]
            else:
                new_slots.append(ParkingSlot(
                    zone_id=zone.zone_id, slot_label=s["id"], category=s["category"],
                    current_status="Available", coordinates_polygon=s["polygon"],
                ))
        if new_slots:
            db.bulk_save_objects(new_slots)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to sync calibration polygons to DB for zone=%s: %s", zone_key, exc)
    finally:
        db.close()