from __future__ import annotations

import cv2
import asyncio
import base64
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db.session import get_db, session_local
from app.db.models import EntryExitLog, OccupancySnapshot, ParkingSlot, ParkingZone
from app.features.auth.endpoints import get_current_user
from app.features.ocr.pipeline.plate_utils import normalize_plate, is_valid_plate_format
from app.features.ocr.services.plate_lookup import find_vehicle_by_plate, resolve_or_create_vehicle
from app.features.ocr.services.session_tracking import record_entry, record_exit

from app.features.occupancy.schemas.slots import CategoryInfo, ZoneUpdate, CapacityUpdate, DetectionEvent
from app.features.occupancy.services.layout import SLOT_LAYOUTS, ZONE_CAMERA_DEVICE, slot_category_map
from app.features.occupancy.services.detection import SlotSmoother, map_detections_to_slots
from app.features.occupancy.services import calibration as calib
from app.features.occupancy.services import camera as camera_svc
from app.features.occupancy.services import vision
from app.features.occupancy.services.persistence import persist_slot_update, sync_calibration_to_db

logger = logging.getLogger(__name__)

router = APIRouter()
ws_router = APIRouter(tags=["WebSocket"])

SMOOTHER_WINDOW = 8
SMOOTHER_MIN_VOTES = 5
 
DB_WRITE_INTERVAL_SEC = 0.5
ALIGN_LOG_INTERVAL_SEC = 1.0
NO_REFERENCE_WARN_INTERVAL_SEC = 5.0
FRAME_LOOP_DELAY_SEC = 0.05
MAX_CONSECUTIVE_READ_FAILURES = 10


def _zone_or_404(zone_key: str) -> list[dict]:
    """Retrieve the layout for a given zone key, or raise a 404 error if not found"""
    layout = SLOT_LAYOUTS.get(zone_key)
    if not layout:
        raise HTTPException(status_code=404, detail=f"Unknown zone '{zone_key}'")
    return layout


@ws_router.websocket("/ws/slots")
async def slots_camera_ws(
    websocket: WebSocket,
    zone: str = Query(default="west"),
    camera_index: Optional[str] = Query(default=None),
    conf: float = Query(default=0.25),
):
    """WebSocket endpoint to stream live camera feed with slot occupancy detection"""
    await websocket.accept()
    loop = asyncio.get_event_loop()

    layout = SLOT_LAYOUTS.get(zone)
    if not layout:
        await websocket.send_json({"error": f"Unknown zone '{zone}'", "conn": "disconnected"})
        await websocket.close()
        return

    model = await loop.run_in_executor(None, vision.get_slot_model)
    if model is None:
        await websocket.send_json({"error": "Occupancy model failed to load.", "conn": "disconnected"})
        await websocket.close()
        return

    resolved_source = camera_index if camera_index is not None else ZONE_CAMERA_DEVICE.get(zone, "0")
    source = camera_svc.resolve_source(str(resolved_source))
    cap = await loop.run_in_executor(None, camera_svc.open_camera, source)
    if not cap or not cap.isOpened():
        await websocket.send_json({"error": f"Camera/Video '{resolved_source}' unavailable.", "conn": "disconnected"})
        await websocket.close()
        return

    calibration = calib.load_calibration(zone)
    ref_thumb = await loop.run_in_executor(None, calib.load_reference_thumb, zone) if calibration else None
    slot_ids = [s["id"] for s in (calibration or layout)]
    smoother = SlotSmoother(slot_ids, window=SMOOTHER_WINDOW, min_votes_to_flip=SMOOTHER_MIN_VOTES)
    id_to_category = slot_category_map(layout)
    device = getattr(vision, "_device", None) or "cpu"

    if not calibration:
        logger.warning(
            "zone=%s NOT CALIBRATED — save a layout via Slot Calibration, then reconnect. "
            "DB writes are skipped until then.", zone,
        )
    elif ref_thumb is None:
        logger.warning(
            "zone=%s calibrated but reference image is missing/unreadable — "
            "re-save calibration. DB writes are skipped until alignment can be checked.", zone,
        )
    else:
        logger.info("zone=%s calibration loaded (%d slots), reference image OK.", zone, len(calibration))

    try:
        await _run_camera_loop(
            websocket, loop, cap, model, device, zone, conf,
            calibration, ref_thumb, smoother, id_to_category,
        )
    except WebSocketDisconnect:
        logger.info("Client disconnected.")
    except Exception:
        logger.exception("zone=%s slots websocket loop crashed", zone)
    finally:
        cap.release()


async def _run_camera_loop(
    websocket, 
    loop, cap, 
    model, 
    device, 
    zone, conf,
    calibration, 
    ref_thumb, 
    smoother, 
    id_to_category,
):
    """Run the camera loop"""
    last_push = 0.0
    last_align_log = 0.0
    consecutive_failures = 0

    while True:
        ret, frame = await loop.run_in_executor(None, cap.read)
        if not ret:
            consecutive_failures += 1
            logger.warning("Frame read failed (%d/%d).", consecutive_failures, MAX_CONSECUTIVE_READ_FAILURES)
            if consecutive_failures >= MAX_CONSECUTIVE_READ_FAILURES:
                logger.error("Too many consecutive failed reads, disconnecting.")
                break
            await asyncio.sleep(0.1)
            continue
        consecutive_failures = 0

        aligned, align_score, live_calibration = False, None, None
        if calibration and ref_thumb is not None:
            aligned, align_score, homography = await loop.run_in_executor(
                None, calib.estimate_alignment, frame, ref_thumb
            )
            if aligned and homography is not None:
                live_calibration = await loop.run_in_executor(
                    None, calib.warp_calibration, calibration, homography
                )
        use_calibration = bool(calibration and live_calibration)

        now_t = loop.time()
        if align_score is not None and (now_t - last_align_log) >= ALIGN_LOG_INTERVAL_SEC:
            logger.info(
                "zone=%s good_feature_matches=%s (need >= %d, aligned=%s)",
                zone, align_score, calib.MIN_GOOD_MATCHES, use_calibration,
            )
            last_align_log = now_t
        elif calibration and ref_thumb is None and (now_t - last_align_log) >= NO_REFERENCE_WARN_INTERVAL_SEC:
            logger.warning("zone=%s skipping DB writes: no reference image loaded.", zone)
            last_align_log = now_t

        if use_calibration:
            dets = await loop.run_in_executor(None, vision.run_inference, frame, model, conf, device)
            raw_status = map_detections_to_slots(dets, live_calibration)
            status = smoother.update(raw_status)
        else:
            dets, status = [], {}

        frame_b64 = await loop.run_in_executor(
            None, _encode_annotated_frame, frame, use_calibration, calibration, live_calibration, status, zone,
        )

        now = loop.time()
        if use_calibration and now - last_push >= DB_WRITE_INTERVAL_SEC:
            await loop.run_in_executor(None, persist_slot_update, zone, status, id_to_category)
            last_push = now

        occ = sum(1 for v in status.values() if v == "Occupied")
        try:
            await websocket.send_json({
                "frame": frame_b64,
                "detections": len(dets),
                "occupied": occ,
                "available": (len(status) - occ) if status else 0,
                "calibrated": bool(calibration),
                "calibration_active": use_calibration,
                "align_score": align_score,
            })
        except Exception:
            logger.info("zone=%s send failed, treating as disconnect.", zone)
            break
        await asyncio.sleep(FRAME_LOOP_DELAY_SEC)


def _encode_annotated_frame(frame, use_calibration, calibration, live_calibration, status, zone) -> str:
    """Encode the frame with annotations for WebSocket transmission"""
    if use_calibration:
        drawn = vision.draw_calibrated_slots(frame, live_calibration, status)
    elif calibration is None:
        drawn = vision.draw_notice(frame, f"Zone '{zone}' has not been calibrated yet.")
    else:
        drawn = vision.draw_notice(frame, "Camera not aligned with calibrated view.")
    return vision.encode_jpeg_b64(drawn)


@router.get("/live")
def get_live_slots(zone: str = Query(...), db: Session = Depends(get_db)):
    """Get the live occupancy status of parking slots"""
    parking_zone = db.query(ParkingZone).filter(ParkingZone.zone_key == zone).first()
    if not parking_zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone}' not found")

    slots = db.query(ParkingSlot).filter(ParkingSlot.zone_id == parking_zone.zone_id).all()
    dashboard = parking_zone.to_dashboard_dict()

    return {
        "zone": zone,
        "timestamp": datetime.now().isoformat(),
        "slots": [
            {"id": s.slot_label, "status": s.current_status, "category": s.category}
            for s in slots
        ],
        "category_summary": dashboard["category_summary"],
        "total_capacity": dashboard["total_capacity"],
        "total_occupied": dashboard["total_occupied"],
        "total_available": dashboard["total_available"],
        "overall_rate_pct": dashboard["overall_rate_pct"],
    }


@router.get("/calibration/{zone_key}/snapshot")
def calibration_snapshot(zone_key: str, current_user=Depends(get_current_user)):
    """Get a snapshot from the camera for a specific zone"""
    layout = _zone_or_404(zone_key)
    resolved_source = ZONE_CAMERA_DEVICE.get(zone_key, "0")
    source = camera_svc.resolve_source(resolved_source)

    frame = camera_svc.capture_single_frame(source)
    if frame is None:
        raise HTTPException(status_code=503, detail=f"Could not read a frame from camera '{resolved_source}'.")
    
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode camera snapshot")

    height, width = frame.shape[:2]
    return {
        "zone": zone_key,
        "width": width,
        "height": height,
        "image": base64.b64encode(buf).decode("utf-8"),
        "default_slots": layout,
    }


@router.get("/calibration/{zone_key}/defaults")
def calibration_defaults(zone_key: str, current_user=Depends(get_current_user)):
    """Get the default slot layout for a specific zone"""
    layout = _zone_or_404(zone_key)
    return {
        "zone": zone_key,
        "default_slots": layout,
        "slots": calib.load_calibration(zone_key) or [],
    }


@router.get("/calibration/{zone_key}")
def get_calibration(zone_key: str, current_user=Depends(get_current_user)):
    """Get the calibration layout for a specific zone"""
    _zone_or_404(zone_key)
    slots = calib.load_calibration(zone_key) or []
    return {"zone": zone_key, "slots": slots, "calibrated": len(slots) > 0}


@router.post("/calibration/{zone_key}")
def save_calibration(zone_key: str, payload: dict, current_user=Depends(get_current_user)):
    """Save a new calibration layout for a specific zone"""
    if getattr(current_user, "role", None) != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can save slot calibration")
    _zone_or_404(zone_key)

    slots = payload.get("slots")
    if not isinstance(slots, list) or not slots:
        raise HTTPException(status_code=400, detail="`slots` must be a non-empty list")
    for s in slots:
        if not all(k in s for k in ("id", "category", "polygon")):
            raise HTTPException(status_code=400, detail="Each slot needs id, category, and polygon")
        if not isinstance(s["polygon"], list) or len(s["polygon"]) < 3:
            raise HTTPException(status_code=400, detail=f"Slot '{s.get('id')}' polygon needs at least 3 points")

    ref_b64 = payload.get("reference_image")
    if not ref_b64:
        raise HTTPException(
            status_code=400,
            detail="`reference_image` is required so the camera view can later be verified against it",
        )
    try:
        ref_bytes = base64.b64decode(ref_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="`reference_image` must be valid base64") from exc

    calib.save_calibration(zone_key, slots)
    calib.reference_image_path(zone_key).write_bytes(ref_bytes)
    sync_calibration_to_db(zone_key, slots)

    return {"zone": zone_key, "saved": len(slots), "calibrated": True}


@router.patch("/zones/{zone_key}/capacity")
def update_zone_capacity(
    zone_key: str,
    payload: CapacityUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update the capacity of a specific parking zone"""
    if getattr(current_user, "role", None) != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can change zone capacity")

    zone = db.query(ParkingZone).filter(ParkingZone.zone_key == zone_key).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_key}' not found")

    if payload.employee_capacity is not None:
        zone.employee_capacity = payload.employee_capacity
    if payload.vendor_capacity is not None:
        zone.vendor_capacity = payload.vendor_capacity
    if payload.visitor_capacity is not None:
        zone.visitor_capacity = payload.visitor_capacity

    zone.total_capacity = zone.employee_capacity + zone.vendor_capacity + zone.visitor_capacity
    db.commit()
    db.refresh(zone)

    return {
        "zone": zone.zone_key,
        "total_capacity": zone.total_capacity,
        "employee_capacity": zone.employee_capacity,
        "vendor_capacity": zone.vendor_capacity,
        "visitor_capacity": zone.visitor_capacity,
    }


@router.post("/update")
def update_parking_slots(payload: ZoneUpdate, db: Session = Depends(get_db)):
    """Update the occupancy status of parking slots for a specific zone"""
    zone = db.query(ParkingZone).filter(ParkingZone.zone_key == payload.zone).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{payload.zone}' not found")

    slot_ids = [s.id for s in payload.slots]
    existing = {
        slot.slot_label: slot
        for slot in db.query(ParkingSlot)
        .filter(ParkingSlot.zone_id == zone.zone_id, ParkingSlot.slot_label.in_(slot_ids))
        .all()
    }

    new_slots = []
    for slot_data in payload.slots:
        slot = existing.get(slot_data.id)
        if slot:
            slot.current_status = slot_data.status
            slot.category = slot_data.category
        else:
            new_slots.append(ParkingSlot(
                zone_id=zone.zone_id,
                slot_label=slot_data.id,
                category=slot_data.category,
                current_status=slot_data.status,
                coordinates_polygon=[],
            ))

    if new_slots:
        db.bulk_save_objects(new_slots)

    total_cap = sum(c.total for c in payload.category_summary.values())
    total_occ = sum(c.used for c in payload.category_summary.values())
    total_avail = sum(c.available for c in payload.category_summary.values())
    rate = (total_occ / total_cap * 100) if total_cap else 0.0

    emp = payload.category_summary.get("Employee", CategoryInfo(used=0, total=0, available=0, rate_pct=0))
    ven = payload.category_summary.get("Vendor", CategoryInfo(used=0, total=0, available=0, rate_pct=0))
    vis = payload.category_summary.get("Visitor", CategoryInfo(used=0, total=0, available=0, rate_pct=0))

    db.add(OccupancySnapshot(
        zone_id=zone.zone_id,
        recorded_at=datetime.fromisoformat(payload.timestamp),
        total_capacity=total_cap,
        total_occupied=total_occ,
        total_available=total_avail,
        overall_rate_pct=rate,
        employee_used=emp.used, employee_total=emp.total,
        vendor_used=ven.used, vendor_total=ven.total,
        visitor_used=vis.used, visitor_total=vis.total,
    ))

    zone.used_capacity = total_occ
    zone.employee_used = emp.used
    zone.vendor_used = ven.used
    zone.visitor_used = vis.used

    db.commit()
    return {"message": "Slots updated successfully", "zone": payload.zone}


@router.post("/detection")
def record_detection(event: DetectionEvent, db: Session = Depends(get_db)):
    """Record a new detection event"""
    zone = db.query(ParkingZone).filter(ParkingZone.zone_key == event.zone).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    plate_norm = normalize_plate(event.plate)
    vehicle = find_vehicle_by_plate(db, plate_norm)
    if vehicle is None and not is_valid_plate_format(plate_norm):
        raise HTTPException(
            status_code=422,
            detail=f"Plate '{event.plate}' is unregistered and not a valid Indonesian plate format — not recorded",
        )
    if vehicle is None:
        vehicle = resolve_or_create_vehicle(db, plate_norm)

    event_type = "Entry" if event.status == "Occupied" else "Exit"
    event_ts = datetime.fromisoformat(event.timestamp)
    db.add(EntryExitLog(
        zone_id=zone.zone_id,
        event_type=event_type,
        plate_detected=plate_norm[:20],
        confidence_score=event.confidence,
        event_timestamp=event_ts,
        auth_method="AI_LPR",
    ))

    if event_type == "Entry":
        record_entry(db, vehicle.vehicle_id, zone.zone_id, event_ts)
    else:
        record_exit(db, vehicle.vehicle_id, event_ts)

    db.commit()
    return {"message": "Detection event logged and session synced successfully"}


@router.get("/logs")
def get_logs(
    zone: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get the latest entry/exit logs"""
    q = db.query(EntryExitLog)
    if zone:
        pz = db.query(ParkingZone).filter(ParkingZone.zone_key == zone).first()
        if pz:
            q = q.filter(EntryExitLog.zone_id == pz.zone_id)
    logs = q.order_by(EntryExitLog.event_timestamp.desc()).limit(limit).all()
    return [log.to_log_dict() for log in logs]