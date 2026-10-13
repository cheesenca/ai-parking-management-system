from __future__ import annotations

<<<<<<< HEAD
import sys
import json
import time
import asyncio
import base64
import logging
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from ultralytics import YOLO
import torch

from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.core.models import EntryExitLog, OccupancySnapshot, ParkingSlot, ParkingZone
from app.features.occupancy.schemas.slots import CategoryInfo, ZoneUpdate, CapacityUpdate
from app.features.occupancy.services.occupancy import SlotSmoother, compute_iou
=======
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
>>>>>>> origin/master
from app.features.auth.endpoints import get_current_user
from app.features.ocr.pipeline.plate_utils import normalize_plate, is_valid_plate_format
from app.features.ocr.services.plate_lookup import find_vehicle_by_plate, resolve_or_create_vehicle
from app.features.ocr.services.session_tracking import record_entry, record_exit

<<<<<<< HEAD
=======
from app.features.occupancy.schemas.slots import CategoryInfo, ZoneUpdate, CapacityUpdate, DetectionEvent
from app.features.occupancy.services.layout import SLOT_LAYOUTS, ZONE_CAMERA_DEVICE, slot_category_map
from app.features.occupancy.services.detection import SlotSmoother, map_detections_to_slots
from app.features.occupancy.services import calibration as calib
from app.features.occupancy.services import camera as camera_svc
from app.features.occupancy.services import vision
from app.features.occupancy.services.persistence import persist_slot_update, sync_calibration_to_db

>>>>>>> origin/master
logger = logging.getLogger(__name__)

router = APIRouter()
ws_router = APIRouter(tags=["WebSocket"])

<<<<<<< HEAD
# Same YOLO_DEVICE knob the OCR pipeline respects, so both live camera paths
# stay consistent (and CPU can be forced for debugging without reinstalling).
_device = "cuda" if torch.cuda.is_available() and settings.YOLO_DEVICE.lower() != "cpu" else "cpu"

_slot_model = YOLO(str(settings.OCCUPANCY_MODEL_PATH))
_slot_model.to(_device)


def _bootstrap(f: str) -> None:
    """
    Bootstrap sys.path
    """
    p = Path(f).resolve()
    proj = None
    for parent in p.parents:
        if (parent / "requirements.txt").exists() and (parent / "app").is_dir():
            proj = parent
            break
    if proj and str(proj) not in sys.path:
        sys.path.insert(0, str(proj))

_bootstrap(__file__)


def _build_layout(prefix: str) -> list[dict]:
    """
    Slot layout mirrors frontend's slotData.ts grid
    """
    layout: list[dict] = []
    for c in range(1, 11): 
        layout.append({"id": f"{prefix}1-{c}", "category": "Employee"})
    for c in range(1, 11): 
        layout.append({"id": f"{prefix}2-{c}", "category": "Employee"})
    for c in range(1, 9): 
        layout.append({"id": f"{prefix}3-{c}", "category": "Vendor"})
    for c in range(1, 6): 
        layout.append({"id": f"{prefix}4-{c}", "category": "Visitor"})
    return layout

SLOT_LAYOUTS: dict[str, list[dict]] = {
    "west": _build_layout("W"), 
    "east": _build_layout("E"),
}
SLOT_LAYOUTS["eastwest"] = SLOT_LAYOUTS["west"] + SLOT_LAYOUTS["east"]

ZONE_CAMERA_DEVICE: dict[str, str] = {
    "west": "0",
    "east": "0",
    "eastwest": "0",
}

# Throttles how often _persist_slot_update writes an OccupancySnapshot row,
# independent of the real-time ParkingSlot/ParkingZone update cadence.
_last_snapshot_at: dict[str, float] = {}

COLOR_AVAIL = (30, 200, 60)
COLOR_OCC = (30, 60, 220)

CALIBRATION_DIR = Path(__file__).resolve().parent.parent / "data" / "calibration"
CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)

IOU_MATCH_THRESHOLD = 0.10


def _load_reference_thumb(zone_key: str):
    """
    Loads the stored calibration reference image and pre-computes keypoints and descriptors using the ORB algorithm
    """
    import cv2

    path = _reference_image_path(zone_key)
    if not path.exists():
        return None
    
    ref = cv2.imread(str(path))
    if ref is None:
        return None
    
    gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    thumb_scale = 480 / w
    gray = cv2.resize(gray, (480, int(h * thumb_scale)))
    orb = cv2.ORB_create(nfeatures=500)
    kp, des = orb.detectAndCompute(gray, None)
    return {"kp": kp, "des": des, "shape": gray.shape, "thumb_scale": thumb_scale}


def _estimate_alignment(frame, ref_data, min_good_matches: int = 12):
    """
    Checks if the current camera frame matches the calibration reference and computes the homography matrix
    """
    import cv2

    if ref_data is None or ref_data.get("des") is None:
        return False, 0, None

    h_frame, w_frame = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame_scale = 480 / w_frame
    gray_r = cv2.resize(gray, (480, int(h_frame * frame_scale)))

    orb = cv2.ORB_create(nfeatures=500)
    kp_f, des_f = orb.detectAndCompute(gray_r, None)
    if des_f is None or len(des_f) < 2:
        return False, 0, None

    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    matches = bf.knnMatch(ref_data["des"], des_f, k=2)
    good = [m for m, n in matches if m.distance < 0.75 * n.distance]
    if len(good) < min_good_matches:
        return False, len(good), None

    src_pts = np.float32([ref_data["kp"][m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp_f[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H_thumb, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if H_thumb is None or mask is None or int(mask.sum()) < min_good_matches:
        return False, len(good), None

    s_ref = ref_data["thumb_scale"]
    s_frame_inv = 1.0 / frame_scale
    S_ref = np.array([[s_ref, 0, 0], [0, s_ref, 0], [0, 0, 1]], dtype=np.float64)
    S_frame = np.array([[s_frame_inv, 0, 0], [0, s_frame_inv, 0], [0, 0, 1]], dtype=np.float64)
    H_full = S_frame @ H_thumb @ S_ref
    return True, len(good), H_full


def _warp_calibration(calibration: List[dict], H) -> List[dict]:
    """
    Transforms the calibrated parking slot polygon to align with the current live frame using the homography matrix
    """
    import cv2
    
    warped = []
    for s in calibration:
        pts = np.array(s["polygon"], dtype=np.float32).reshape(-1, 1, 2)
        warped_pts = cv2.perspectiveTransform(pts, H).reshape(-1, 2).tolist()
        warped.append({**s, "polygon": warped_pts})
    return warped


def _calibration_path(zone_key: str) -> Path:
    """
    Get the JSON file path where the calibrated slot polygon coordinates are stored
    """
    return CALIBRATION_DIR / f"{zone_key}.json"


def _reference_image_path(zone_key: str) -> Path:
    """
    Obtaining the file path of the image used as the reference for the initial calibration photo
    """
    return CALIBRATION_DIR / f"{zone_key}_reference.jpg"


def _load_calibration(zone_key: str) -> Optional[List[dict]]:
    """
    Loads stored parking slot polygon calibration data from a JSON file
    """
    path = _calibration_path(zone_key)
    if not path.exists():
        return None
    
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        slots = data.get("slots", [])
        return slots if slots else None
    except Exception:
        return None


def _save_calibration(zone_key: str, slots: List[dict]) -> None:
    """
    Save the newly calibrated parking slot polygon coordinate data to a JSON file
    """
    _calibration_path(zone_key).write_text(
        json.dumps({"zone": zone_key, "slots": slots}, indent=2), encoding="utf-8"
    )


def _map_to_slots_calibrated(dets: List[dict], calibration: List[dict]) -> Dict[str, str]:
    """
    Maps detected bounding boxes to calibrated parking slots based on Intersection over Union (IoU)
    """
    status = {s["id"]: "Available" for s in calibration}
    best_iou_for_slot: Dict[str, float] = {}

    for d in dets:
        bbox = [d["x1"], d["y1"], d["x2"], d["y2"]]

        best_slot_id = None
        best_iou = 0.0
        for s in calibration:
            iou = compute_iou(s["polygon"], bbox)
            if iou > best_iou:
                best_iou = iou
                best_slot_id = s["id"]

        if best_slot_id is None or best_iou < IOU_MATCH_THRESHOLD:
            continue

        if best_iou > best_iou_for_slot.get(best_slot_id, -1.0):
            best_iou_for_slot[best_slot_id] = best_iou
            status[best_slot_id] = d["label"]

    return status


def _get_slot_model():
    """
    Lazily load and cache the YOLOv8 occupancy model
    """
    global _slot_model
    if _slot_model is not None:
        return _slot_model
    
    try:
        from ultralytics import YOLO
        from app.core.config import OCCUPANCY_MODEL_PATH

        _slot_model = YOLO(str(OCCUPANCY_MODEL_PATH))
        logger.info("Occupancy model loaded successfully")
        return _slot_model
    except Exception as exc:
        logger.error(f"Occupancy model unavailable: {exc}")
        return None


def _enhance(frame):
    """
    Dynamically enhancing local image contrast using the CLAHE method in the LAB color space
    """
    import cv2

    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def _draw_calibrated_slots(frame, calibration: List[dict], status: Dict[str, str]):
    """
    Drawing calibrated parking slot polygons onto the live frame based on availability status
    """
    import cv2

    out = frame.copy()
    for s in calibration:
        pts = [(int(x), int(y)) for x, y in s["polygon"]]
        label = status.get(s["id"], "Available")
        color = COLOR_AVAIL if label == "Available" else COLOR_OCC

        ov = out.copy()
        cv2.fillPoly(ov, [np.array(pts, dtype=np.int32)], color)
        cv2.addWeighted(ov, 0.28, out, 0.72, 0, out)
        cv2.polylines(out, [np.array(pts, dtype=np.int32)], True, color, 2)

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        cx, cy = sum(xs) // len(xs), sum(ys) // len(ys)
        slot_w = max(xs) - min(xs)
        slot_h = max(ys) - min(ys)

        font_scale = max(0.28, min(0.42, min(slot_w, slot_h) / 90))
        txt = str(s["id"])
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        tx, ty = cx - tw // 2, cy + th // 2

        cv2.putText(out, txt, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, txt, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def _draw_notice(frame, message: str):
    """
    Displays a notification message in the center of the screen while dimming the entire camera video frame
    """
    import cv2

    out = (frame.astype(np.float32) * 0.35).astype(np.uint8)
    h, w = out.shape[:2]
    (tw, th), _ = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
    tx, ty = max(10, (w - tw) // 2), h // 2
    cv2.putText(out, message, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def _persist_slot_update(zone_key: str, status: dict[str, str], layout: list[dict]) -> None:
    """
    Storing or updating live status data from parking slot detection directly into the database
    """
    id2cat = {s["id"]: s["category"] for s in layout}
    db = SessionLocal()
    try:
        zone = db.query(ParkingZone).filter(ParkingZone.zone_key == zone_key).first()
        if not zone:
            return

        cat_total: dict[str, int] = {}
        for s in layout:
            cat_total[s["category"]] = cat_total.get(s["category"], 0) + 1

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

        now = time.time()
        if now - _last_snapshot_at.get(zone_key, 0) >= settings.OCCUPANCY_SNAPSHOT_INTERVAL_SEC:
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
                f"zone={zone_key} OccupancySnapshot written: "
                f"{total_occupied}/{zone.total_capacity} occupied ({rate:.1f}%)"
            )

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database write failed: {e}")
    finally:
        db.close()


# WebSocket /ws/slots
=======
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


>>>>>>> origin/master
@ws_router.websocket("/ws/slots")
async def slots_camera_ws(
    websocket: WebSocket,
    zone: str = Query(default="west"),
    camera_index: Optional[str] = Query(default=None),
    conf: float = Query(default=0.25),
):
<<<<<<< HEAD
    """
    WebSocket endpoint for streaming live visualizations of parking slot occupancy status in real-time and asynchronous
    """
=======
    """WebSocket endpoint to stream live camera feed with slot occupancy detection"""
>>>>>>> origin/master
    await websocket.accept()
    loop = asyncio.get_event_loop()

    layout = SLOT_LAYOUTS.get(zone)
    if not layout:
        await websocket.send_json({"error": f"Unknown zone '{zone}'", "conn": "disconnected"})
        await websocket.close()
        return

<<<<<<< HEAD
    model = await loop.run_in_executor(None, _get_slot_model)
=======
    model = await loop.run_in_executor(None, vision.get_slot_model)
>>>>>>> origin/master
    if model is None:
        await websocket.send_json({"error": "Occupancy model failed to load.", "conn": "disconnected"})
        await websocket.close()
        return

    resolved_source = camera_index if camera_index is not None else ZONE_CAMERA_DEVICE.get(zone, "0")
<<<<<<< HEAD

    import cv2
    source = int(resolved_source) if str(resolved_source).isdigit() else resolved_source

    def _open_camera():
        """
        Internal function to open the camera hardware or a video stream file
        """
        import time

        c = None
        for attempt in range(4):
            if isinstance(source, int):
                c = cv2.VideoCapture(source, cv2.CAP_DSHOW)
                if not c.isOpened():
                    c.release()
                    c = cv2.VideoCapture(source)
            else:
                c = cv2.VideoCapture(source)

            if c.isOpened():
                for _ in range(5):
                    ok, _ = c.read()
                    if ok:
                        return c
                    time.sleep(0.15)
                c.release()

            logger.warning(f"Camera '{source}' open attempt {attempt + 1}/4 failed, retrying...")
            time.sleep(0.4)
        return c

    cap = await loop.run_in_executor(None, _open_camera)
=======
    source = camera_svc.resolve_source(str(resolved_source))
    cap = await loop.run_in_executor(None, camera_svc.open_camera, source)
>>>>>>> origin/master
    if not cap or not cap.isOpened():
        await websocket.send_json({"error": f"Camera/Video '{resolved_source}' unavailable.", "conn": "disconnected"})
        await websocket.close()
        return

<<<<<<< HEAD
    calibration = _load_calibration(zone)
    ref_thumb = await loop.run_in_executor(None, _load_reference_thumb, zone) if calibration else None
    slot_ids = [s["id"] for s in (calibration or layout)]
    smoother = SlotSmoother(slot_ids, window=8, min_votes_to_flip=5)

    if not calibration:
        logger.warning(
            f"zone={zone} NOT CALIBRATED — open Slot Calibration, save a layout, "
            f"then reconnect. DB writes (ParkingSlot/OccupancySnapshot) are skipped until then."
        )
    elif ref_thumb is None:
        logger.warning(
            f"zone={zone} calibrated but reference image is missing/unreadable — "
            f"re-save calibration. DB writes are skipped until alignment can be checked."
        )
    else:
        logger.info(f"zone={zone} calibration loaded ({len(calibration)} slots), reference image OK.")

    try:
        last_push = 0.0
        last_align_log = 0.0
        consecutive_failures = 0
        while True:
            ret, frame = await loop.run_in_executor(None, cap.read)
            if not ret:
                consecutive_failures += 1
                logger.warning(f"Frame read failed ({consecutive_failures}/10).")
                if consecutive_failures >= 10:
                    logger.error("Too many consecutive failed reads, disconnecting.")
                    break
                await asyncio.sleep(0.1)
                continue
            consecutive_failures = 0

            aligned = False
            align_score = None
            live_calibration = None
            if calibration and ref_thumb is not None:
                aligned, align_score, H = await loop.run_in_executor(None, _estimate_alignment, frame, ref_thumb)
                if aligned and H is not None:
                    live_calibration = await loop.run_in_executor(None, _warp_calibration, calibration, H)
            use_calibration = bool(calibration and live_calibration)

            if align_score is not None and (loop.time() - last_align_log) >= 1.0:
                logger.info(
                    f"zone={zone} good_feature_matches={align_score} "
                    f"(need >= 12, aligned={use_calibration})"
                )
                last_align_log = loop.time()
            elif calibration and ref_thumb is None and (loop.time() - last_align_log) >= 5.0:
                logger.warning(f"zone={zone} skipping DB writes: no reference image loaded.")
                last_align_log = loop.time()

            if use_calibration:
                def _infer():
                    enhanced = _enhance(frame)
                    h0, w0 = enhanced.shape[:2]
                    scale = 640 / w0
                    inf_f = cv2.resize(enhanced, (640, int(h0 * scale)))
                    results = model(inf_f, conf=conf, iou=0.45, agnostic_nms=True, device=_device, verbose=False)
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
                raw_status = _map_to_slots_calibrated(dets, live_calibration)
                status = smoother.update(raw_status)
            else:
                dets = []
                status = {}


            def _encode():
                """
                Drawing a visual graphic overlay onto an image and compressing it into a base64-encoded JPEG string
                """
                if use_calibration:
                    drawn = _draw_calibrated_slots(frame, live_calibration, status)
                elif calibration is None:
                    drawn = _draw_notice(frame, f"Zone '{zone}' has not been calibrated yet.")
                else:
                    drawn = _draw_notice(frame, "Camera not aligned with calibrated view.")
                _, buf = cv2.imencode(".jpg", drawn, [cv2.IMWRITE_JPEG_QUALITY, 65])
                return base64.b64encode(buf.tobytes()).decode()

            frame_b64 = await loop.run_in_executor(None, _encode)

            now = loop.time()
            if use_calibration and now - last_push >= 0.5:
                await loop.run_in_executor(None, _persist_slot_update, zone, status, calibration)
                last_push = now

            occ = sum(1 for v in status.values() if v == "Occupied")
            try:
                await websocket.send_json({
                    "frame": frame_b64,
                    "detections": len(dets),
                    "occupied": occ,
                    "available": (len(status) - occ) if status else 0,
                    "calibrated": bool(calibration),
                    "calibration_active": bool(use_calibration),
                    "align_score": align_score,
                })
            except Exception:
                # Any send failure (not just a clean WebSocketDisconnect) means
                # the client is gone — stop looping instead of retrying forever
                # against a dead socket while still holding the camera open.
                logger.info(f"zone={zone} send failed, treating as disconnect.")
                break
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        logger.info("Client disconnected.")
    except Exception:
        logger.exception(f"zone={zone} slots websocket loop crashed")
=======
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
>>>>>>> origin/master
    finally:
        cap.release()


<<<<<<< HEAD
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
=======
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
>>>>>>> origin/master

    return {
        "zone": zone,
        "timestamp": datetime.now().isoformat(),
        "slots": [
            {"id": s.slot_label, "status": s.current_status, "category": s.category}
            for s in slots
        ],
        "category_summary": dashboard["category_summary"],
        "total_capacity": dashboard["total_capacity"],
<<<<<<< HEAD
        "total_occupied": total_occupied,
=======
        "total_occupied": dashboard["total_occupied"],
>>>>>>> origin/master
        "total_available": dashboard["total_available"],
        "overall_rate_pct": dashboard["overall_rate_pct"],
    }


<<<<<<< HEAD
# GET /api/slots/calibration/{zone_key}/snapshot
@router.get("/calibration/{zone_key}/snapshot")
def calibration_snapshot(zone_key: str, current_user=Depends(get_current_user)):
    """
    Grabs a single still frame from the zone's configured camera
    """
    if zone_key not in SLOT_LAYOUTS:
        raise HTTPException(status_code=404, detail=f"Unknown zone '{zone_key}'")

    import cv2
    resolved_source = ZONE_CAMERA_DEVICE.get(zone_key, "0")
    source = int(resolved_source) if str(resolved_source).isdigit() else resolved_source

    if isinstance(source, int):
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(source)
    else:
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        cap.release()
        raise HTTPException(status_code=503, detail=f"Camera/Video '{resolved_source}' unavailable.")

    try:
        frame = None
        for _ in range(5):
            ok, f = cap.read()
            if ok:
                frame = f
                break
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
            "default_slots": SLOT_LAYOUTS[zone_key],
        }
    finally:
        cap.release()


# GET /api/slots/calibration/{zone_key}/defaults
@router.get("/calibration/{zone_key}/defaults")
def calibration_defaults(zone_key: str, current_user=Depends(get_current_user)):
    """
    Retrieving default slot layout data and stored slot polygon calibration data for a specific zone 
    """
    if zone_key not in SLOT_LAYOUTS:
        raise HTTPException(status_code=404, detail=f"Unknown zone '{zone_key}'")
    return {
        "zone": zone_key,
        "default_slots": SLOT_LAYOUTS[zone_key],
        "slots": _load_calibration(zone_key) or [],
    }


# GET /api/slots/calibration/{zone_key}
@router.get("/calibration/{zone_key}")
def get_calibration(zone_key: str, current_user=Depends(get_current_user)):
    """
    Returns the currently saved polygon calibration for a zone, if any
    """
    if zone_key not in SLOT_LAYOUTS:
        raise HTTPException(status_code=404, detail=f"Unknown zone '{zone_key}'")
    slots = _load_calibration(zone_key) or []
    return {"zone": zone_key, "slots": slots, "calibrated": len(slots) > 0}


# POST /api/slots/calibration/{zone_key}
@router.post("/calibration/{zone_key}")
def save_calibration(zone_key: str, payload: dict, current_user=Depends(get_current_user)):
    """
    Stores parking slot polygon coordinates and reference photos in Base64 format
    """
    if getattr(current_user, "role", None) != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can save slot calibration")
    
    if zone_key not in SLOT_LAYOUTS:
        raise HTTPException(status_code=404, detail=f"Unknown zone '{zone_key}'")
=======
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
>>>>>>> origin/master

    slots = payload.get("slots")
    if not isinstance(slots, list) or not slots:
        raise HTTPException(status_code=400, detail="`slots` must be a non-empty list")
<<<<<<< HEAD
    
    for s in slots:
        if not all(k in s for k in ("id", "category", "polygon")):
            raise HTTPException(status_code=400, detail="Each slot needs id, category, and polygon")
        
=======
    for s in slots:
        if not all(k in s for k in ("id", "category", "polygon")):
            raise HTTPException(status_code=400, detail="Each slot needs id, category, and polygon")
>>>>>>> origin/master
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
<<<<<<< HEAD
    except Exception:
        raise HTTPException(status_code=400, detail="`reference_image` must be valid base64")

    _save_calibration(zone_key, slots)
    _reference_image_path(zone_key).write_bytes(ref_bytes)

    db = SessionLocal()
    try:
        zone = db.query(ParkingZone).filter(ParkingZone.zone_key == zone_key).first()
        if zone:
            for s in slots:
                slot = db.query(ParkingSlot).filter(
                    ParkingSlot.zone_id == zone.zone_id,
                    ParkingSlot.slot_label == s["id"],
                ).first()
                if slot:
                    slot.coordinates_polygon = s["polygon"]
                    slot.category = s["category"]
                else:
                    db.add(ParkingSlot(
                        zone_id=zone.zone_id, slot_label=s["id"], category=s["category"],
                        current_status="Available", coordinates_polygon=s["polygon"],
                    ))
            db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to sync calibration polygons to DB: {e}")
    finally:
        db.close()
=======
    except Exception as exc:
        raise HTTPException(status_code=400, detail="`reference_image` must be valid base64") from exc

    calib.save_calibration(zone_key, slots)
    calib.reference_image_path(zone_key).write_bytes(ref_bytes)
    sync_calibration_to_db(zone_key, slots)
>>>>>>> origin/master

    return {"zone": zone_key, "saved": len(slots), "calibrated": True}


<<<<<<< HEAD
# PATCH /api/slots/zones/{zone_key}/capacity
=======
>>>>>>> origin/master
@router.patch("/zones/{zone_key}/capacity")
def update_zone_capacity(
    zone_key: str,
    payload: CapacityUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
<<<<<<< HEAD
    """
    Partially update parking slot allocation capacities for each category within a zone
    """
=======
    """Update the capacity of a specific parking zone"""
>>>>>>> origin/master
    if getattr(current_user, "role", None) != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can change zone capacity")

    zone = db.query(ParkingZone).filter(ParkingZone.zone_key == zone_key).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_key}' not found")

    if payload.employee_capacity is not None:
        zone.employee_capacity = payload.employee_capacity
<<<<<<< HEAD

    if payload.vendor_capacity is not None:
        zone.vendor_capacity = payload.vendor_capacity

=======
    if payload.vendor_capacity is not None:
        zone.vendor_capacity = payload.vendor_capacity
>>>>>>> origin/master
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


<<<<<<< HEAD
# POST /api/slots/update 
@router.post("/update")
def update_parking_slots(
    payload: ZoneUpdate, 
    db: Session = Depends(get_db)
):
    """
    Receives status updates for each parking slot from the AI camera system
    """
=======
@router.post("/update")
def update_parking_slots(payload: ZoneUpdate, db: Session = Depends(get_db)):
    """Update the occupancy status of parking slots for a specific zone"""
>>>>>>> origin/master
    zone = db.query(ParkingZone).filter(ParkingZone.zone_key == payload.zone).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{payload.zone}' not found")

<<<<<<< HEAD
    for slot_data in payload.slots:
        slot = db.query(ParkingSlot).filter(
            ParkingSlot.zone_id   == zone.zone_id,
            ParkingSlot.slot_label == slot_data.id,
        ).first()
=======
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
>>>>>>> origin/master
        if slot:
            slot.current_status = slot_data.status
            slot.category = slot_data.category
        else:
<<<<<<< HEAD
            db.add(ParkingSlot(
=======
            new_slots.append(ParkingSlot(
>>>>>>> origin/master
                zone_id=zone.zone_id,
                slot_label=slot_data.id,
                category=slot_data.category,
                current_status=slot_data.status,
                coordinates_polygon=[],
            ))

<<<<<<< HEAD
=======
    if new_slots:
        db.bulk_save_objects(new_slots)

>>>>>>> origin/master
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
<<<<<<< HEAD
        employee_used=emp.used, 
        employee_total=emp.total,
        vendor_used=ven.used, 
        vendor_total=ven.total,
        visitor_used=vis.used, 
        visitor_total=vis.total,
=======
        employee_used=emp.used, employee_total=emp.total,
        vendor_used=ven.used, vendor_total=ven.total,
        visitor_used=vis.used, visitor_total=vis.total,
>>>>>>> origin/master
    ))

    zone.used_capacity = total_occ
    zone.employee_used = emp.used
    zone.vendor_used = ven.used
    zone.visitor_used = vis.used

    db.commit()
    return {"message": "Slots updated successfully", "zone": payload.zone}


<<<<<<< HEAD
# POST /api/slots/detection
@router.post("/detection")
def record_detection(
    event: DetectionEvent, 
    db: Session = Depends(get_db)
):
    """
    Log gate entry/exit events while managing active parking sessions
    """
=======
@router.post("/detection")
def record_detection(event: DetectionEvent, db: Session = Depends(get_db)):
    """Record a new detection event"""
>>>>>>> origin/master
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
<<<<<<< HEAD
    new_log = EntryExitLog(
=======
    db.add(EntryExitLog(
>>>>>>> origin/master
        zone_id=zone.zone_id,
        event_type=event_type,
        plate_detected=plate_norm[:20],
        confidence_score=event.confidence,
        event_timestamp=event_ts,
        auth_method="AI_LPR",
<<<<<<< HEAD
    )
    db.add(new_log)
=======
    ))
>>>>>>> origin/master

    if event_type == "Entry":
        record_entry(db, vehicle.vehicle_id, zone.zone_id, event_ts)
    else:
        record_exit(db, vehicle.vehicle_id, event_ts)

    db.commit()
    return {"message": "Detection event logged and session synced successfully"}


<<<<<<< HEAD
# GET /api/slots/logs
@router.get("/logs")
def get_logs(
    zone:  Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Retrieving historical vehicle entry and exit log data
    """
=======
@router.get("/logs")
def get_logs(
    zone: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get the latest entry/exit logs"""
>>>>>>> origin/master
    q = db.query(EntryExitLog)
    if zone:
        pz = db.query(ParkingZone).filter(ParkingZone.zone_key == zone).first()
        if pz:
            q = q.filter(EntryExitLog.zone_id == pz.zone_id)
<<<<<<< HEAD
            
    logs = q.order_by(EntryExitLog.event_timestamp.desc()).limit(limit).all()
    return [log.to_log_dict() for log in logs]
=======
    logs = q.order_by(EntryExitLog.event_timestamp.desc()).limit(limit).all()
    return [log.to_log_dict() for log in logs]
>>>>>>> origin/master
