from __future__ import annotations

import asyncio
import base64
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import EntryExitLog, ParkingSession, ParkingZone, Vehicle


def _bootstrap(f: str) -> None:
    p = Path(f).resolve()
    proj = None
    for parent in p.parents:
        if (parent / "requirements.txt").exists() and (parent / "app").is_dir():
            proj = parent
            break
    if proj and str(proj) not in sys.path:
        sys.path.insert(0, str(proj))
    # Also add the ocr/pipeline directory so "from pipeline.pipeline import …" works
    ocr_pipeline = p.parent / "pipeline"
    if ocr_pipeline.is_dir() and str(ocr_pipeline.parent) not in sys.path:
        sys.path.insert(0, str(ocr_pipeline.parent))

_bootstrap(__file__)

# ── Dua router terpisah ────────────────────────────────────────────────────────
# router   → /api/ocr/*  (REST, di-include dengan prefix)
# ws_router→ /ws/*       (WebSocket, tanpa prefix agar path = /ws/camera)
router    = APIRouter(prefix="/api/ocr", tags=["OCR License Plate"])
ws_router = APIRouter(tags=["WebSocket"])


# ── Lazy-load AIPS pipeline ────────────────────────────────────────────────────
_pipeline_instance = None

def _get_pipeline():
    """
    Load pipeline sekali saja. Return None jika model / library belum tersedia
    sehingga WebSocket otomatis masuk simulation mode (camera not connected).
    """
    global _pipeline_instance
    if _pipeline_instance is not None:
        return _pipeline_instance
    try:
        # Add pipeline dir to sys.path so relative imports inside pipeline work
        pipeline_dir = Path(__file__).parent / "pipeline"
        if str(pipeline_dir) not in sys.path:
            sys.path.insert(0, str(pipeline_dir))
        from pipeline.pipeline import AIPSPipeline  # noqa: PLC0415
        _pipeline_instance = AIPSPipeline(use_pretrained=True)
        print("[OCR WS] Pipeline loaded successfully")
        return _pipeline_instance
    except Exception as exc:
        print(f"[OCR WS] Pipeline unavailable → simulation mode: {exc}")
        return None


# ── Data simulasi (plate sama dengan mockData.ts agar member lookup cocok) ────
_SIM_PLATES = [
    ("B 1234 ABC", "car",        0.97),
    ("D 4321 DEF", "car",        0.94),
    ("B 9876 GHI", "motorcycle", 0.91),
    ("F 1111 JKL", "car",        0.98),
    ("B 3333 PQR", "car",        0.88),
    ("E 4444 STU", "motorcycle", 0.96),
    ("B 5555 VWX", "car",        0.93),
    ("D 6666 YZA", "car",        0.89),
    ("B 7777 BCD", "motorcycle", 0.95),
    ("B 8888 EFG", "car",        0.97),
    ("B 1010 KLM", "car",        0.91),
    ("F 3030 QRS", "motorcycle", 0.85),
    ("B 4040 TUV", "car",        0.99),
    ("B 5050 WXY", "car",        0.96),
    ("???",        "car",        0.21),   # unknown plate
]
_sim_tick = 0


def _make_sim_detection(gate_type: Optional[str]) -> dict:
    global _sim_tick
    _sim_tick += 1
    is_unknown = (_sim_tick % 7 == 0)
    plate, vtype, base_conf = _SIM_PLATES[-1 if is_unknown else (_sim_tick % (len(_SIM_PLATES) - 1))]
    conf = min(0.999, base_conf * (0.95 + random.random() * 0.08)) if not is_unknown \
           else 0.15 + random.random() * 0.2
    etype  = gate_type if gate_type else ("entry" if _sim_tick % 2 == 0 else "exit")
    status = "detected" if conf >= 0.70 else ("low_confidence" if plate != "???" else "no_plate")
    return {
        "plate_detected": plate,
        "confidence":     round(conf, 3),
        "vehicle_type":   vtype,
        "event_type":     etype,
        "timestamp":      datetime.now().isoformat(),
        "status":         status,
    }


# ── WebSocket /ws/camera ───────────────────────────────────────────────────────
@ws_router.websocket("/ws/camera")
async def camera_websocket(
    websocket:    WebSocket,
    camera_index: int           = Query(default=0),
    gate_type:    Optional[str] = Query(default=None),
):
    """
    WebSocket untuk live vehicle detection.
    Dipakai frontend api.ts → useLiveDetection() hook.

    URL: ws://<LPR_HOST>/ws/camera?camera_index=0[&gate_type=entry|exit]

    Payload per frame:
    {
        "frame":     "<base64-jpeg> | null",
        "vehicles":  [...],
        "detection": { ... }   ← hanya saat kendaraan melintas garis
    }
    """
    await websocket.accept()
    loop     = asyncio.get_event_loop()
    pipeline = await loop.run_in_executor(None, _get_pipeline)

    # ── Coba buka kamera fisik ─────────────────────────────────────────────────
    use_real_camera = False
    cap = None
    if pipeline is not None:
        try:
            import cv2
            cap = await loop.run_in_executor(None, lambda: cv2.VideoCapture(camera_index))
            use_real_camera = cap.isOpened()
            if not use_real_camera:
                print(f"[OCR WS] Camera {camera_index} unavailable → simulation mode")
        except Exception:
            pass

    # ── LIVE mode ─────────────────────────────────────────────────────────────
    if use_real_camera and cap is not None:
        import cv2
        try:
            while True:
                ret, frame = await loop.run_in_executor(None, cap.read)
                if not ret:
                    break

                output = await loop.run_in_executor(None, pipeline.process_frame, frame)

                def _encode():
                    _, buf = cv2.imencode(
                        ".jpg", output["frame"], [cv2.IMWRITE_JPEG_QUALITY, 65]
                    )
                    return base64.b64encode(buf.tobytes()).decode()

                frame_b64 = await loop.run_in_executor(None, _encode)

                payload: dict = {
                    "frame":    frame_b64,
                    "vehicles": output.get("vehicles", []),
                }
                if output.get("events"):
                    e = output["events"][0]
                    payload["detection"] = {
                        "plate_detected": e.get("plate", ""),
                        "confidence":     e.get("confidence", 0),
                        "vehicle_type":   e.get("vehicle_type", "car"),
                        "event_type":     e.get("event_type", "entry"),
                        "timestamp":      e.get("timestamp", datetime.now().isoformat()),
                        "status":         e.get("status", "detected"),
                    }

                await websocket.send_json(payload)
                await asyncio.sleep(0.05)   # ~20 fps

        except WebSocketDisconnect:
            pass
        finally:
            cap.release()

    # ── SIMULATION mode ────────────────────────────────────────────────────────
    else:
        try:
            tick = 0
            while True:
                tick += 1
                payload: dict = {
                    "frame":    None,
                    "vehicles": [{"track_id": 1, "vehicle_type": "car", "det_conf": 0.85}],
                }
                # Kirim detection setiap ~4.2 detik (84 tick × 50 ms)
                if tick % 84 == 0:
                    payload["detection"] = _make_sim_detection(gate_type)
                await websocket.send_json(payload)
                await asyncio.sleep(0.05)
        except WebSocketDisconnect:
            pass


# ── POST /api/ocr/scan ─────────────────────────────────────────────────────────
@router.post("/scan")
def process_scanned_plate(
    plate_number: str,
    zone_id:      int,
    db: Session = Depends(get_db),
):
    """Manual plate scan (KPK card atau override security)."""
    zone = db.query(ParkingZone).filter(ParkingZone.zone_id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    # Cek apakah kendaraan sedang di dalam (ada sesi aktif)
    vehicle    = db.query(Vehicle).filter(Vehicle.plate_number == plate_number).first()
    event_type = "Entry"
    if vehicle:
        active_session = db.query(ParkingSession).filter(
            ParkingSession.vehicle_id == vehicle.vehicle_id,
            ParkingSession.status     == "IN",
        ).first()
        if active_session:
            active_session.status    = "OUT"
            active_session.exit_time = datetime.now()
            event_type               = "Exit"

    db.add(EntryExitLog(
        zone_id=zone_id,
        event_type=event_type,
        plate_detected=plate_number,
        confidence_score=1.0,      # scan manual = confidence penuh
        event_timestamp=datetime.now(),
        auth_method="KPK_Scan",
    ))
    db.commit()

    return {
        "message":    f"Plate {event_type.lower()} logged successfully",
        "plate":      plate_number,
        "event_type": event_type,
    }