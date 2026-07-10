from __future__ import annotations
import sys
import asyncio
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from app.core.database import get_db, SessionLocal
from app.core.models import EntryExitLog, ParkingSession, ParkingZone, Vehicle

# Router 
router = APIRouter()
ws_router = APIRouter(tags=["WebSocket"])

# Lazy-load AIPS pipeline
_pipeline_instance = None

# Bootstrap sys.path
def _bootstrap(f: str) -> None:
    p = Path(f).resolve()
    proj = None
    for parent in p.parents:
        if (parent / "requirements.txt").exists() and (parent / "app").is_dir():
            proj = parent
            break
    if proj and str(proj) not in sys.path:
        sys.path.insert(0, str(proj))
    ocr_pipeline = p.parent / "pipeline"
    if ocr_pipeline.is_dir() and str(ocr_pipeline.parent) not in sys.path:
        sys.path.insert(0, str(ocr_pipeline.parent))
_bootstrap(__file__)


def _get_pipeline():
    """
    Retrieve the singleton instance of AIPSPipeline
    """
    global _pipeline_instance
    if _pipeline_instance is not None:
        return _pipeline_instance
    try:
        from app.features.ocr.pipeline.pipeline import AIPSPipeline  
        _pipeline_instance = AIPSPipeline(use_pretrained=False)
        print("[OCR WS] Pipeline loaded successfully")
        return _pipeline_instance
    except Exception as exc:
        print(f"[OCR WS] Pipeline unavailable: {exc}")
        return None


def save_ocr_event_to_db(event_data: dict, gate_type: str):
    """
    Storing automatic OCR detection event data from the camera stream to a database    
    """
    db = SessionLocal()
    try:
        plate = event_data.get("plate", "")
        direction = event_data.get("event_type", "entry")
        conf = event_data.get("confidence", 0.0)
        v_type = event_data.get("vehicle_type", "car")
        if not plate:
            return

        zone_key = gate_type or "west"
        zone = db.query(ParkingZone).filter(ParkingZone.zone_key == zone_key).first()
        if not zone:
            return

        vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate).first()
        if not vehicle:
            vehicle = Vehicle(
                plate_number=plate,
                vehicle_type=v_type,
                user_category="Visitor"
            )
            db.add(vehicle)
            db.commit()
            db.refresh(vehicle)

        # Handle Parking Session
        active_session = db.query(ParkingSession).filter(
            ParkingSession.vehicle_id == vehicle.vehicle_id,
            ParkingSession.status == "IN"
        ).first()

        current_session_id = None
        if direction == "entry":
            if not active_session:
                new_session = ParkingSession(
                    vehicle_id=vehicle.vehicle_id,
                    zone_id=zone.zone_id,
                    entry_time=datetime.now(),
                    status="IN"
                )
                db.add(new_session)
                db.commit()
                db.refresh(new_session)
                current_session_id = new_session.session_id
            else:
                current_session_id = active_session.session_id
        elif direction == "exit":
            if active_session:
                active_session.status = "OUT"
                active_session.exit_time = datetime.now()
                current_session_id = active_session.session_id
                db.commit()

        db.add(EntryExitLog(
            zone_id=zone.zone_id,
            session_id=current_session_id,
            event_type="Entry" if direction == "entry" else "Exit",
            plate_detected=plate,
            confidence_score=conf,
            event_timestamp=datetime.now(),
            auth_method="AI_LPR"
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[OCR DB Error] Gagal menulis ke DB: {e}")
    finally:
        db.close()

# WebSocket /ws/camera 
@ws_router.websocket("/ws/camera")
async def camera_websocket(
    websocket: WebSocket,
    camera_index: str = Query(default="0"), 
    gate_type: Optional[str] = Query(default=None),
):
    """
    WebSocket for vehicle live detection
    """
    await websocket.accept()
    loop = asyncio.get_event_loop()
    pipeline = await loop.run_in_executor(None, _get_pipeline)

    if pipeline is None:
        await websocket.send_json({"error": "Model Pipeline gagal dimuat.", "conn": "disconnected"})
        await websocket.close()
        return

    import cv2
    if camera_index.isdigit():
        source = int(camera_index)
    else:
        source = camera_index

    cap = await loop.run_in_executor(None, lambda: cv2.VideoCapture(source))
    use_real_camera = cap.isOpened()
    if not use_real_camera:
        print(f"[OCR WS] Source {camera_index} unavailable. Connection closed.")
        await websocket.send_json({"error": f"Kamera/Video {camera_index} tidak dapat diakses.", "conn": "disconnected"})
        await websocket.close()
        return

    # LIVE Mode
    try:
        while True:
            ret, frame = await loop.run_in_executor(None, cap.read)
            if not ret:
                print("[OCR WS]Failed to read frame from source (Camera off / Video ended), Disconnected")
                break
            output = await loop.run_in_executor(None, pipeline.process_frame, frame)

            def _encode():
                _, buf = cv2.imencode(
                    ".jpg", output["frame"], [cv2.IMWRITE_JPEG_QUALITY, 65]
                )
                return base64.b64encode(buf.tobytes()).decode()

            frame_b64 = await loop.run_in_executor(None, _encode)
            payload: dict = {
                "frame": frame_b64,
                "vehicles": output.get("vehicles", []),
            }
            if output.get("events"):
                e = output["events"][0]
                payload["detection"] = {
                    "plate_detected": e.get("plate", ""),
                    "confidence": e.get("confidence", 0),
                    "vehicle_type": e.get("vehicle_type", "car"),
                    "event_type": e.get("event_type", "entry"),
                    "timestamp": e.get("timestamp", datetime.now().isoformat()),
                    "status": e.get("status", "detected"),
                }
                
                #
                loop.run_in_executor(None, save_ocr_event_to_db, e, gate_type)

            await websocket.send_json(payload)
            await asyncio.sleep(0.05) 
    except WebSocketDisconnect:
        print("[OCR WS] Client disconnected.")
    finally:
        cap.release()


# POST /api/ocr/scan 
@router.post("/scan")
def process_scanned_plate(
    plate_number: str,
    zone_id:      int,
    db: Session = Depends(get_db),
):
    """
    Manually processing gate entries—for example, when a user taps in with a card or QR code, or performs a manual scan that immediately transmits license plate information
    """
    zone = db.query(ParkingZone).filter(ParkingZone.zone_id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate_number).first()
    event_type = "Entry"
    if vehicle:
        active_session = db.query(ParkingSession).filter(
            ParkingSession.vehicle_id == vehicle.vehicle_id,
            ParkingSession.status == "IN",
        ).first()
        if active_session:
            active_session.status = "OUT"
            active_session.exit_time = datetime.now()
            event_type = "Exit"

    db.add(EntryExitLog(
        zone_id=zone_id,
        event_type=event_type,
        plate_detected=plate_number,
        confidence_score=1.0,
        event_timestamp=datetime.now(),
        auth_method="KPK_Scan",
    ))
    db.commit()

    return {
        "message": f"Plate {event_type.lower()} logged successfully",
        "plate": plate_number,
        "event_type": event_type,
    }


def process_ocr_gate_event(plate_num: str, confidence: float, event_type: str, zone_key: str):
    """
    Process vehicles at entry/exit gates using OCR results and automatically synchronize them with the database
    """
    db = SessionLocal()
    try:
        vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate_num).first()
        zone = db.query(ParkingZone).filter(ParkingZone.zone_key == zone_key).first()
        zone_id = zone.zone_id if zone else 1
        
        if event_type == "Entry":
            new_session = ParkingSession(
                vehicle_id=vehicle.vehicle_id if vehicle else None,
                zone_id=zone_id,
                status="IN"
            )
            db.add(new_session)
            db.flush() 
            log = EntryExitLog(
                session_id=new_session.session_id,
                zone_id=zone_id,
                event_type="Entry",
                plate_detected=plate_num,
                confidence_score=confidence,
                auth_method="AI_LPR"
            )
            db.add(log)
        elif event_type == "Exit":
            if vehicle:
                session = db.query(ParkingSession).filter(
                    ParkingSession.vehicle_id == vehicle.vehicle_id,
                    ParkingSession.status == "IN"
                ).first()
                
                if session:
                    session.status = "OUT"
                    session.exit_time = datetime.now()
                    log = EntryExitLog(
                        session_id=session.session_id,
                        zone_id=zone_id,
                        event_type="Exit",
                        plate_detected=plate_num,
                        confidence_score=confidence,
                        auth_method="AI_LPR"
                    )
                    db.add(log)
        db.commit()
        return {"status": "success", "message": f"Event {event_type} processed for {plate_num}"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()