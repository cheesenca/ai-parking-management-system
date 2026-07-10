from __future__ import annotations
import sys
import asyncio
import base64
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from ultralytics import YOLO
from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.core.models import EntryExitLog, OccupancySnapshot, ParkingSlot, ParkingZone, ParkingSession
from app.features.occupancy.schemas.slots import CategoryInfo, DetectionEvent, SlotItem, ZoneUpdate

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
_bootstrap(__file__)

router = APIRouter()
ws_router = APIRouter(tags=["WebSocket"])

# Slot layout mirrors frontend's slotData.ts grid (W1-1..W4-5 / E1-1..E4-5)
def _build_layout(prefix: str) -> list[dict]:
    layout: list[dict] = []
    for c in range(1, 11): layout.append({"id": f"{prefix}1-{c}", "category": "Employee"})
    for c in range(1, 11): layout.append({"id": f"{prefix}2-{c}", "category": "Employee"})
    for c in range(1, 9):  layout.append({"id": f"{prefix}3-{c}", "category": "Vendor"})
    for c in range(1, 6):  layout.append({"id": f"{prefix}4-{c}", "category": "Visitor"})
    return layout

SLOT_LAYOUTS: dict[str, list[dict]] = {"west": _build_layout("W"), "east": _build_layout("E")}
CATEGORY_TOTAL = {"Employee": 100, "Vendor": 20, "Visitor": 10}
COLOR_AVAIL = (30, 200, 60)
COLOR_OCC = (30, 60, 220)

_slot_model = YOLO(str(settings.OCCUPANCY_MODEL_PATH))
def _get_slot_model():
    """Lazily load and cache the YOLOv8 occupancy model (pklot.pt)."""
    global _slot_model
    if _slot_model is not None:
        return _slot_model
    try:
        from ultralytics import YOLO
        from app.core.config import OCCUPANCY_MODEL_PATH
        _slot_model = YOLO(str(OCCUPANCY_MODEL_PATH))
        print("[SLOT WS] Occupancy model loaded successfully")
        return _slot_model
    except Exception as exc:
        print(f"[SLOT WS] Occupancy model unavailable: {exc}")
        return None


def _enhance(frame):
    import cv2
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def _draw_boxes(frame, dets: list[dict]):
    import cv2
    out = frame.copy()
    for d in dets:
        x1, y1, x2, y2 = int(d["x1"]), int(d["y1"]), int(d["x2"]), int(d["y2"])
        color = COLOR_AVAIL if d["label"] == "Available" else COLOR_OCC
        txt = f'{d["label"]} {d["conf"]:.0%}'
        ov = out.copy()
        cv2.rectangle(ov, (x1, y1), (x2, y2), color, -1)
        cv2.addWeighted(ov, 0.25, out, 0.75, 0, out)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(out, (x1, max(0, y1 - th - 8)), (x1 + tw + 6, y1), color, -1)
        cv2.putText(out, txt, (x1 + 3, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return out


def _map_to_slots(dets: list[dict], layout: list[dict]) -> dict[str, str]:
    """Spatially map YOLO detections (top-to-bottom, left-to-right) onto known slot IDs."""
    status = {s["id"]: "Available" for s in layout}
    ordered = sorted(dets, key=lambda d: ((d["y1"] + d["y2"]) / 2, (d["x1"] + d["x2"]) / 2))
    for i, d in enumerate(ordered):
        if i < len(layout):
            status[layout[i]["id"]] = d["label"]
    return status


def _persist_slot_update(zone_key: str, status: dict[str, str], layout: list[dict]) -> None:
    """Write live detection results directly into the DB — same effect as POST /api/slots/update."""
    id2cat = {s["id"]: s["category"] for s in layout}
    db = SessionLocal()
    try:
        zone = db.query(ParkingZone).filter(ParkingZone.zone_key == zone_key).first()
        if not zone:
            return

        used_by_cat: dict[str, int] = {}
        for sid, st in status.items():
            cat = id2cat.get(sid, "Employee")
            slot = db.query(ParkingSlot).filter(
                ParkingSlot.zone_id == zone.zone_id,
                ParkingSlot.slot_label == sid,
            ).first()
            if slot:
                slot.current_status = st
                slot.category = cat
            else:
                db.add(ParkingSlot(
                    zone_id=zone.zone_id, slot_label=sid, category=cat,
                    current_status=st, coordinates_polygon=[],
                ))
            if st == "Occupied":
                used_by_cat[cat] = used_by_cat.get(cat, 0) + 1

        zone.employee_used = used_by_cat.get("Employee", 0)
        zone.vendor_used = used_by_cat.get("Vendor", 0)
        zone.visitor_used = used_by_cat.get("Visitor", 0)
        zone.used_capacity = sum(used_by_cat.values())
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[SLOT WS] DB write failed: {e}")
    finally:
        db.close()


# WebSocket /ws/slots
@ws_router.websocket("/ws/slots")
async def slots_camera_ws(
    websocket: WebSocket,
    zone: str = Query(default="west"),
    camera_index: str = Query(default="0"),
    conf: float = Query(default=0.25),
):
    """
    Streams the parking-slot camera feed with live occupancy bounding boxes
    (YOLOv8 / pklot.pt) and persists the detected status into the database,
    so the existing GET /api/slots/live polling reflects it automatically.
    """
    await websocket.accept()
    loop = asyncio.get_event_loop()

    layout = SLOT_LAYOUTS.get(zone)
    if not layout:
        await websocket.send_json({"error": f"Unknown zone '{zone}'", "conn": "disconnected"})
        await websocket.close()
        return

    model = await loop.run_in_executor(None, _get_slot_model)
    if model is None:
        await websocket.send_json({"error": "Occupancy model failed to load.", "conn": "disconnected"})
        await websocket.close()
        return

    import cv2
    source = int(camera_index) if camera_index.isdigit() else camera_index
    cap = await loop.run_in_executor(None, lambda: cv2.VideoCapture(source))
    if not cap.isOpened():
        await websocket.send_json({"error": f"Camera/Video '{camera_index}' unavailable.", "conn": "disconnected"})
        await websocket.close()
        return

    try:
        last_push = 0.0
        while True:
            ret, frame = await loop.run_in_executor(None, cap.read)
            if not ret:
                print("[SLOT WS] Failed to read frame from source. Disconnected.")
                break

            def _infer():
                enhanced = _enhance(frame)
                h0, w0 = enhanced.shape[:2]
                scale = 640 / w0
                inf_f = cv2.resize(enhanced, (640, int(h0 * scale)))
                results = model(inf_f, conf=conf, verbose=False)
                dets: list[dict] = []
                for box in (results[0].boxes or []):
                    cls_id = int(box.cls[0])
                    x1, y1, x2, y2 = [v / scale for v in box.xyxy[0].tolist()]
                    dets.append({
                        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "label": "Available" if cls_id == 0 else "Occupied",
                        "conf": float(box.conf[0]),
                    })
                return dets

            dets = await loop.run_in_executor(None, _infer)
            status = _map_to_slots(dets, layout)

            def _encode():
                drawn = _draw_boxes(frame, dets)
                _, buf = cv2.imencode(".jpg", drawn, [cv2.IMWRITE_JPEG_QUALITY, 65])
                return base64.b64encode(buf.tobytes()).decode()

            frame_b64 = await loop.run_in_executor(None, _encode)

            now = loop.time()
            if now - last_push >= 0.5:
                await loop.run_in_executor(None, _persist_slot_update, zone, status, layout)
                last_push = now

            occ = sum(1 for v in status.values() if v == "Occupied")
            await websocket.send_json({
                "frame": frame_b64,
                "detections": len(dets),
                "occupied": occ,
                "available": len(layout) - occ,
            })
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        print("[SLOT WS] Client disconnected.")
    finally:
        cap.release()



# GET /api/slots/live?zone=west
@router.get("/live")
def get_live_slots(
    zone: str = Query(...), 
    db: Session = Depends(get_db)
):
    """
    Retrieve real-time parking slot occupancy status for a specific zone
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
    total_occupied = dashboard["total_occupied"]
    
    valid_sessions_count = db.query(ParkingSession).filter(
        ParkingSession.zone_id == parking_zone.zone_id,
        ParkingSession.status == "IN"
    ).count()
    ghost_count = max(0, total_occupied - valid_sessions_count)
    is_anomaly = ghost_count > 0

    if is_anomaly:
        print(f"[ALERT] Zone {zone}: Detection of {ghost_count} unidentified vehicles/vehicles that bypassed OCR in the parking area!")

    return {
        "zone": zone,
        "timestamp": datetime.now().isoformat(),
        "slots": [
            {"id": s.slot_label, "status": s.current_status, "category": s.category}
            for s in slots
        ],
        "category_summary": dashboard["category_summary"],
        "total_capacity": dashboard["total_capacity"],
        "total_occupied": total_occupied,
        "total_available": dashboard["total_available"],
        "overall_rate_pct": dashboard["overall_rate_pct"],
        "valid_sessions": valid_sessions_count,
        "ghost_vehicles": ghost_count,
        "anomaly": is_anomaly
    }


# POST /api/slots/update 
@router.post("/update")
def update_parking_slots(
    payload: ZoneUpdate, 
    db: Session = Depends(get_db)
):
    """
    Receives status updates for each parking slot from the AI ​​camera system (YOLO)
    """
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
            slot.category = slot_data.category
        else:
            db.add(ParkingSlot(
                zone_id=zone.zone_id,
                slot_label=slot_data.id,
                category=slot_data.category,
                current_status=slot_data.status,
                coordinates_polygon=[],
            ))

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
        employee_used=emp.used, 
        employee_total=emp.total,
        vendor_used=ven.used, 
        vendor_total=ven.total,
        visitor_used=vis.used, 
        visitor_total=vis.total,
    ))

    zone.used_capacity = total_occ
    zone.employee_used = emp.used
    zone.vendor_used = ven.used
    zone.visitor_used = vis.used

    db.commit()
    return {"message": "Slots updated successfully", "zone": payload.zone}


# POST /api/slots/detection 
@router.post("/detection")
def record_detection(
    event: DetectionEvent, 
    db: Session = Depends(get_db)
):
    """
    Log gate entry/exit events while managing active parking sessions
    """
    zone = db.query(ParkingZone).filter(ParkingZone.zone_key == event.zone).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    event_type = "Entry" if event.status == "Occupied" else "Exit"
    new_log = EntryExitLog(
        zone_id=zone.zone_id,
        event_type=event_type,
        plate_detected=event.plate,
        confidence_score=event.confidence,
        event_timestamp=datetime.fromisoformat(event.timestamp),
        auth_method="AI_LPR",
    )
    db.add(new_log)

    if event_type == "Entry":
        session = ParkingSession(
            zone_id=zone.zone_id,
            plate_number=event.plate,
            entry_time=datetime.fromisoformat(event.timestamp),
            status="IN",
            vehicle_type=getattr(event, 'vehicle_type', 'car')
        )
        db.add(session)
    else:
        active_session = (
            db.query(ParkingSession)
            .filter(
                ParkingSession.plate_number == event.plate,
                ParkingSession.status == "IN"
            )
            .order_by(ParkingSession.entry_time.desc())
            .first()
        )
        if active_session:
            active_session.status = "OUT"
            active_session.exit_time = datetime.fromisoformat(event.timestamp)

    db.commit()
    return {"message": "Detection event logged and session synced successfully"}


# GET /api/slots/logs
@router.get("/logs")
def get_logs(
    zone:  Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Retrieving historical vehicle entry and exit log data (Entry/Exit Log)
    """
    q = db.query(EntryExitLog)
    if zone:
        pz = db.query(ParkingZone).filter(ParkingZone.zone_key == zone).first()
        if pz:
            q = q.filter(EntryExitLog.zone_id == pz.zone_id)
    logs = q.order_by(EntryExitLog.event_timestamp.desc()).limit(limit).all()
    return [log.to_log_dict() for log in logs]


#
def push_slot_update(
    zone: str,
    slot_status: Dict[str, str],
    category_summary: Dict[str, dict],
    parking_map: dict,
) -> bool:
    """
    Helper function for transmitting full slot status update data from the edge device or local camera script to the main backend server
    """
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


#
def push_detection_event(zone: str, plate: str, confidence: float, status: str = "Occupied") -> bool:
    """
    Helper function for transmitting vehicle license plate reading events (LPR/OCR) to the backend API server
    """
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