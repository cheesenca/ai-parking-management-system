import asyncio
import base64
import sys
import cv2
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, Literal

# Add pipeline directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))
from pipeline import AIPSPipeline

from app.core.database import SessionLocal, get_db
from app.core.models import EntryExitLog, ParkingZone, Vehicle, ParkingSession
from app.features.auth.endpoints import get_current_user

# App setup 
router = APIRouter()
ws_router = APIRouter() 

# Lazy-load pipeline (only once, on first connection)
_pipeline: AIPSPipeline | None = None

def get_pipeline() -> AIPSPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = AIPSPipeline(use_pretrained=False)
    return _pipeline


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
            plate_detected=event.get("plate", "")[:20],
            confidence_score=event.get("confidence"),
            event_timestamp=event_ts,
            auth_method="AI_LPR",
        )
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[OCR->DB] Failed to save detection event: {e}")
    finally:
        db.close()


# Health check 
@router.get("/api/health")
def health():
    return {"status": "ok", "model": "loaded" if _pipeline else "not_loaded"}


# Manual trigger endpoint (HTTP) 
@router.post("/api/scan/simulate")
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


class ManualApprovePayload(BaseModel):
    plate: str
    zone: str
    event_type: Literal["entry", "exit"]
    timestamp: str
    original_confidence: Optional[float] = None


# Manual approval endpoint (HTTP)
@router.post("/manual-approve")
def manual_approve_plate(payload: ManualApprovePayload, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Manually confirm a plate that the automated OCR pipeline flagged as
    low-confidence / unreadable. Classifies the plate against registered
    members, writes an entry_exit_log row, and keeps parking_session in sync
    — mirroring what /api/v1/slots/detection does for automated detections.
    """
    zone = db.query(ParkingZone).filter(ParkingZone.zone_key == payload.zone).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{payload.zone}' not found")

    plate = payload.plate.strip().upper()
    vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate).first()
    member = vehicle.member if vehicle else None
    classification = "Member" if member else "Visitor"

    db_event_type = "Entry" if payload.event_type == "entry" else "Exit"
    try:
        event_ts = datetime.fromisoformat(payload.timestamp)
    except ValueError:
        event_ts = datetime.now()

    log = EntryExitLog(
        zone_id=zone.zone_id,
        event_type=db_event_type,
        plate_detected=plate,
        confidence_score=payload.original_confidence,
        event_timestamp=event_ts,
        auth_method="Manual_Security",
    )
    db.add(log)

    # parking_session is keyed by vehicle_id, so a session can only be tracked
    # for plates that belong to a registered Vehicle (members). Unregistered
    # visitor plates are still recorded in entry_exit_log above.
    if vehicle is not None:
        if payload.event_type == "entry":
            db.add(ParkingSession(
                vehicle_id=vehicle.vehicle_id,
                zone_id=zone.zone_id,
                entry_time=event_ts,
                status="IN",
            ))
        else:
            active_session = (
                db.query(ParkingSession)
                .filter(ParkingSession.vehicle_id == vehicle.vehicle_id, ParkingSession.status == "IN")
                .order_by(ParkingSession.entry_time.desc())
                .first()
            )
            if active_session:
                active_session.status = "OUT"
                active_session.exit_time = event_ts

    db.commit()

    return {
        "recorded": True,
        "plate": plate,
        "classification": classification,
        "member": member.to_member_dict() if member else None,
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
                payload["detection"] = {
                    "plate_detected": ev['plate'],
                    "confidence": ev['confidence'],
                    "vehicle_type": ev['vehicle_type'],
                    "event_type": ev['event_type'],
                    "timestamp": ev['timestamp'],
                    "status": ev['status'],
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