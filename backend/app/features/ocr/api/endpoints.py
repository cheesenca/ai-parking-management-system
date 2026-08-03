import asyncio
import base64
import logging
import sys
import cv2
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

# Add pipeline directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))
from pipeline import AIPSPipeline
from plate_utils import normalize_plate, is_valid_plate_format

from app.core.models import EntryExitLog, ParkingZone
from app.features.auth.endpoints import get_current_user
from app.features.ocr.schemas.detection import ManualApprovalRequest
from app.features.ocr.services.plate_lookup import find_vehicle_by_plate, resolve_or_create_vehicle
from app.features.ocr.services.session_tracking import record_entry, record_exit

logger = logging.getLogger(__name__)

# App setup
router = APIRouter()
ws_router = APIRouter()

# Lazy-load pipeline (only once, on first connection)
_pipeline: AIPSPipeline | None = None
# Set once AIPSPipeline() raises, so a persistently broken load (missing
# model file, no network for EasyOCR's first-run download, etc.) fails
# fast instead of being retried on every new /ws/camera connection.
# Cleared by a process restart.
_pipeline_load_failed = False

def get_pipeline() -> AIPSPipeline | None:
    global _pipeline, _pipeline_load_failed
    if _pipeline is not None:
        return _pipeline
    if _pipeline_load_failed:
        return None
    try:
        _pipeline = AIPSPipeline(use_pretrained=False)
        return _pipeline
    except Exception:
        _pipeline_load_failed = True
        logger.exception("[OCR WS] Pipeline failed to load")
        return None


def save_detection_event(event: dict, zone_key: str) -> None:
    """
    Persist one OCR detection/crossing event to entry_exit_log.
    Runs in its own short-lived DB session so a slow/failed write
    never blocks or crashes the camera streaming loop.
    """
    db = SessionLocal()
    try:
        zone = db.query(ParkingZone).filter(ParkingZone.zone_key == zone_key).first()
        if zone is None:
            print(f"[OCR->DB] Unknown zone_key '{zone_key}', skipping log write")
            return

        plate_norm = normalize_plate(event.get("plate", ""))
        vehicle = find_vehicle_by_plate(db, plate_norm)
        if vehicle is None and not is_valid_plate_format(plate_norm):
            print(f"[OCR->DB] Rejected unregistered, non-standard plate '{plate_norm}' — not recorded")
            return
        if vehicle is None:
            vehicle = resolve_or_create_vehicle(db, plate_norm, event.get("vehicle_type", "Car"))

        event_type_map = {"entry": "Entry", "exit": "Exit"}
        db_event_type = event_type_map.get(event.get("event_type"), "Denied")

        raw_ts = event.get("timestamp")
        try:
            event_ts = datetime.fromisoformat(raw_ts) if raw_ts else datetime.now()
        except ValueError:
            event_ts = datetime.now()

        log = EntryExitLog(
            zone_id=zone.zone_id,
            event_type=db_event_type,
            plate_detected=plate_norm[:20],
            confidence_score=event.get("confidence"),
            event_timestamp=event_ts,
            auth_method="AI_LPR",
        )
        db.add(log)

        if db_event_type == "Entry":
            record_entry(db, vehicle.vehicle_id, zone.zone_id, event_ts)
        elif db_event_type == "Exit":
            record_exit(db, vehicle.vehicle_id, event_ts)

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[OCR->DB] Failed to save detection event: {e}")
    finally:
        db.close()


def _lookup_member_for_display(plate: str) -> dict | None:
    """
    Short-lived-session lookup used to enrich the live WS payload with the
    matched member (if any), independent of whether the event ends up
    persisted to entry_exit_log.
    """
    if not plate:
        return None
    db = SessionLocal()
    try:
        vehicle = find_vehicle_by_plate(db, plate)
        if vehicle and vehicle.user_category == "Member" and vehicle.member:
            return vehicle.member.to_member_dict()
        return None
    finally:
        db.close()


# Health check
@router.get("/health")
def health():
    return {"status": "ok", "model": "loaded" if _pipeline else "not_loaded"}


# Manual trigger endpoint (HTTP) 
@router.post("/scan/simulate")
def simulate_scan():
    """
    Simulates a detection event. Useful for testing the dashboard integration before your camera/model is ready.
    """
    import random, string

    fake_plate = (
        random.choice(['B','D','F','E']) + ' ' +
        str(random.randint(1000, 9999)) + ' ' +
        ''.join(random.choices(string.ascii_uppercase, k=3))
    )
    return {
        "plate_detected": fake_plate,
        "confidence": round(random.uniform(0.72, 0.99), 2),
        "vehicle_type": random.choice(['car', 'motorcycle']),
        "event_type": random.choice(['entry', 'exit']),
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "status": "detected",
    }


# POST /api/v1/ocr/manual-approve
@router.post("/manual-approve")
def manual_approve_detection(
    payload: ManualApprovalRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Staff-approved (or corrected) low-confidence plate read. Skips the
    automated path's format safeguard — a human is vouching for this read —
    but still cross-checks it against registered vehicles for classification.
    """
    zone = db.query(ParkingZone).filter(ParkingZone.zone_key == payload.zone).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{payload.zone}' not found")

    plate_norm = normalize_plate(payload.plate)
    if not plate_norm:
        raise HTTPException(status_code=400, detail="Plate cannot be empty")

    vehicle = resolve_or_create_vehicle(db, plate_norm)
    member_dict = (
        vehicle.member.to_member_dict()
        if vehicle.user_category == "Member" and vehicle.member else None
    )

    try:
        event_ts = datetime.fromisoformat(payload.timestamp) if payload.timestamp else datetime.now()
    except ValueError:
        event_ts = datetime.now()

    db.add(EntryExitLog(
        zone_id=zone.zone_id,
        admin_id=current_user.admin_id,
        event_type="Entry" if payload.event_type == "entry" else "Exit",
        plate_detected=plate_norm[:20],
        confidence_score=payload.original_confidence,
        event_timestamp=event_ts,
        auth_method="Manual_Security",
    ))

    if payload.event_type == "entry":
        record_entry(db, vehicle.vehicle_id, zone.zone_id, event_ts)
    else:
        record_exit(db, vehicle.vehicle_id, event_ts)

    db.commit()

    return {
        "recorded": True,
        "plate": plate_norm,
        "classification": "Member" if member_dict else "Visitor",
        "member": member_dict,
    }


# WebSocket endpoint (WebSocket)
@ws_router.websocket("/ws/camera")
async def camera_feed(
    websocket: WebSocket,
    camera_index: int = Query(default=0),
    gate_type: str = Query(default="entry"),
    zone: str = Query(default="west"),
):
    """
    Connect from the ParkWise dashboard Parking Tracer page.
    Streams detection results in real time.

    Query params:
        camera_index : which camera to use (default 0 = first webcam)
        gate_type    : 'entry' or 'exit' — overrides direction detection
                       if set to a fixed value (optional, leave blank to
                       use automatic direction detection)
        zone         : zone_key (e.g. 'west', 'east') this camera/gate
                       belongs to — used to log entry_exit_log against
                       the correct parking_zone
    """
    await websocket.accept()
    print(f"[WS] Client connected | camera={camera_index}")

    pipeline = get_pipeline()
    if pipeline is None:
        await websocket.send_json({"error": "Model pipeline failed to load."})
        await websocket.close()
        return

    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        await websocket.send_json({"error": f"Cannot open camera {camera_index}"})
        await websocket.close()
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                await websocket.send_json({"error": "Camera read failed"})
                break

            output = pipeline.process_frame(frame)

            # Encode annotated frame as base64 JPEG for browser display
            _, buf   = cv2.imencode('.jpg', output['frame'], [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_b64 = base64.b64encode(buf).decode('utf-8')

            # Build payload
            payload = {
                "frame":    frame_b64,
                "vehicles": output['vehicles'],
                "events":   output['events'],
            }

            # If there are crossing events, enrich with full detection data
            if output['events']:
                ev = output['events'][0]   # take first event per frame
                member = _lookup_member_for_display(normalize_plate(ev['plate'])) if ev.get('plate') else None
                payload["detection"] = {
                    "plate_detected": ev['plate'],
                    "confidence": ev['confidence'],
                    "vehicle_type": ev['vehicle_type'],
                    "event_type": ev['event_type'],
                    "timestamp": ev['timestamp'],
                    "status": ev['status'],
                    "member": member,
                }

                # Persist confirmed crossing events (skip low-confidence/no-plate noise)
                if ev.get('status') == 'detected':
                    save_detection_event(ev, zone)

            await websocket.send_json(payload)

            # ~15 FPS to the browser
            await asyncio.sleep(0.067)

    except WebSocketDisconnect:
        print("[WS] Client disconnected")
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        cap.release()
        print("[WS] Camera released")