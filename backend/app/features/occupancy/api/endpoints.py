from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.models import (
    EntryExitLog, OccupancySnapshot, ParkingSlot, ParkingZone,
)

# ── Fix: import schema dari path yang benar ────────────────────────────────────
# slots.py ada di project root / schemas/slots.py
# Bootstrap dulu agar Python bisa menemukannya
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

from app.features.occupancy.schemas.slots import CategoryInfo, DetectionEvent, SlotItem, ZoneUpdate

router = APIRouter(prefix="/api/slots", tags=["Parking Slots"])


# ── GET /api/slots/live?zone=west ─────────────────────────────────────────────
# Dipanggil oleh frontend api.ts → useSlotOccupancy() setiap 2.5 detik
@router.get("/live")
def get_live_slots(zone: str = Query(...), db: Session = Depends(get_db)):
    """
    Mengembalikan status slot real-time untuk satu zone.
    Response sesuai schema ZoneUpdate yang diexpect frontend.
    """
    parking_zone = (
        db.query(ParkingZone).filter(ParkingZone.zone_key == zone).first()
    )
    if not parking_zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone}' not found")

    slots = (
        db.query(ParkingSlot)
        .filter(ParkingSlot.zone_id == parking_zone.zone_id)
        .all()
    )

    dashboard = parking_zone.to_dashboard_dict()

    return {
        "zone":             zone,
        "timestamp":        datetime.now().isoformat(),
        "slots":            [
            {"id": s.slot_label, "status": s.current_status, "category": s.category}
            for s in slots
        ],
        "category_summary": dashboard["category_summary"],
        "total_capacity":   dashboard["total_capacity"],
        "total_occupied":   dashboard["total_occupied"],
        "total_available":  dashboard["total_available"],
        "overall_rate_pct": dashboard["overall_rate_pct"],
    }


# ── POST /api/slots/update ────────────────────────────────────────────────────
# Dipush oleh pipeline occupancy setiap siklus deteksi
@router.post("/update")
def update_parking_slots(payload: ZoneUpdate, db: Session = Depends(get_db)):
    zone = db.query(ParkingZone).filter(ParkingZone.zone_key == payload.zone).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{payload.zone}' not found")

    for slot_data in payload.slots:
        slot = db.query(ParkingSlot).filter(
            ParkingSlot.zone_id   == zone.zone_id,
            ParkingSlot.slot_label == slot_data.id,
        ).first()

        if slot:
            slot.current_status = slot_data.status
            slot.category       = slot_data.category
        else:
            # Auto-create slot jika belum ada (pertama kali pipeline jalan)
            db.add(ParkingSlot(
                zone_id=zone.zone_id,
                slot_label=slot_data.id,
                category=slot_data.category,
                current_status=slot_data.status,
                coordinates_polygon=[],
            ))

    # Hitung aggregate
    total_cap  = sum(c.total     for c in payload.category_summary.values())
    total_occ  = sum(c.used      for c in payload.category_summary.values())
    total_avail= sum(c.available for c in payload.category_summary.values())
    rate       = (total_occ / total_cap * 100) if total_cap else 0.0

    emp = payload.category_summary.get("Employee", CategoryInfo(used=0, total=0, available=0, rate_pct=0))
    ven = payload.category_summary.get("Vendor",   CategoryInfo(used=0, total=0, available=0, rate_pct=0))
    vis = payload.category_summary.get("Visitor",  CategoryInfo(used=0, total=0, available=0, rate_pct=0))

    db.add(OccupancySnapshot(
        zone_id=zone.zone_id,
        recorded_at=datetime.fromisoformat(payload.timestamp),
        total_capacity=total_cap,
        total_occupied=total_occ,
        total_available=total_avail,
        overall_rate_pct=rate,
        employee_used=emp.used,  employee_total=emp.total,
        vendor_used=ven.used,    vendor_total=ven.total,
        visitor_used=vis.used,   visitor_total=vis.total,
    ))

    zone.used_capacity = total_occ
    zone.employee_used = emp.used
    zone.vendor_used   = ven.used
    zone.visitor_used  = vis.used

    db.commit()
    return {"message": "Slots updated successfully", "zone": payload.zone}


# ── POST /api/slots/detection ─────────────────────────────────────────────────
@router.post("/detection")
def record_detection(event: DetectionEvent, db: Session = Depends(get_db)):
    zone = db.query(ParkingZone).filter(ParkingZone.zone_key == event.zone).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    db.add(EntryExitLog(
        zone_id=zone.zone_id,
        event_type="Entry" if event.status == "Occupied" else "Exit",
        plate_detected=event.plate,
        confidence_score=event.confidence,
        event_timestamp=datetime.fromisoformat(event.timestamp),
        auth_method="AI_LPR",
    ))
    db.commit()
    return {"message": "Detection event logged"}


# ── GET /api/slots/logs ───────────────────────────────────────────────────────
# Dipanggil List.tsx untuk menggantikan mock entryLogs
@router.get("/logs")
def get_logs(
    zone:  Optional[str] = Query(default=None),
    limit: int           = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(EntryExitLog)
    if zone:
        pz = db.query(ParkingZone).filter(ParkingZone.zone_key == zone).first()
        if pz:
            q = q.filter(EntryExitLog.zone_id == pz.zone_id)
    logs = q.order_by(EntryExitLog.event_timestamp.desc()).limit(limit).all()
    return [log.to_log_dict() for log in logs]


# ── Helper functions dipanggil pipeline secara langsung ───────────────────────
def push_slot_update(
    zone: str,
    slot_status: Dict[str, str],
    category_summary: Dict[str, dict],
    parking_map: dict,
) -> bool:
    id_to_cat = {s["id"]: s.get("category", "Employee") for s in parking_map["slots"]}
    payload = ZoneUpdate(
        zone=zone,
        timestamp=datetime.now().isoformat(),
        slots=[
            SlotItem(id=sid, status=st, category=id_to_cat.get(sid, "Employee"))
            for sid, st in slot_status.items()
        ],
        category_summary={
            cat: CategoryInfo(**data) for cat, data in category_summary.items()
        },
    )
    try:
        r = requests.post(settings.SLOTS_UPDATE_URL, json=payload.model_dump(), timeout=settings.API_TIMEOUT)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


def push_detection_event(zone: str, plate: str, confidence: float, status: str = "Occupied") -> bool:
    payload = DetectionEvent(
        zone=zone,
        timestamp=datetime.now().isoformat(),
        plate=plate,
        confidence=confidence,
        status=status,
    )
    try:
        r = requests.post(
            f"{settings.BACKEND_URL}/api/slots/detection",
            json=payload.model_dump(),
            timeout=settings.API_TIMEOUT,
        )
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False