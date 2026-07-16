from __future__ import annotations

import sys
import json
import asyncio
import base64
import logging
import requests
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from ultralytics import YOLO

from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.core.models import EntryExitLog, OccupancySnapshot, ParkingSlot, ParkingZone, ParkingSession
from app.features.occupancy.schemas.slots import CategoryInfo, DetectionEvent, SlotItem, ZoneUpdate, CapacityUpdate
from app.features.occupancy.services.occupancy import SlotSmoother
from app.features.auth.api import get_current_user

logger = logging.getLogger(__name__)

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

# Slot layout mirrors frontend's slotData.ts grid
def _build_layout(prefix: str) -> list[dict]:
    layout: list[dict] = []
    for c in range(1, 11): layout.append({"id": f"{prefix}1-{c}", "category": "Employee"})
    for c in range(1, 11): layout.append({"id": f"{prefix}2-{c}", "category": "Employee"})
    for c in range(1, 9): layout.append({"id": f"{prefix}3-{c}", "category": "Vendor"})
    for c in range(1, 6): layout.append({"id": f"{prefix}4-{c}", "category": "Visitor"})
    return layout

SLOT_LAYOUTS: dict[str, list[dict]] = {"west": _build_layout("W"), "east": _build_layout("E")}
SLOT_LAYOUTS["eastwest"] = SLOT_LAYOUTS["west"] + SLOT_LAYOUTS["east"]

# --- Camera routing per zone -------------------------------------------------
# Today there is physically only ONE slot-scanner camera (device "0"), so every
# zone is routed to it. The mapping exists so adding a real East Plant / East&
# West Plant camera later is a one-line change here (nowhere else) - the
# frontend zone switcher, the WS route, and the DB writes are already
# zone-aware and don't need to change.
ZONE_CAMERA_DEVICE: dict[str, str] = {
    "west": "0",
    "east": "0",      # TODO: point to the East Plant camera once installed
    "eastwest": "0",  # TODO: point to the East&West Plant camera once installed
}

CATEGORY_TOTAL = {"Employee": 100, "Vendor": 20, "Visitor": 10}
COLOR_AVAIL = (30, 200, 60)
COLOR_OCC = (30, 60, 220)

CALIBRATION_DIR = Path(__file__).resolve().parent.parent / "data" / "calibration"
CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)


def _load_reference_thumb(zone_key: str):
    """
    Loads the saved calibration reference image and precomputes ORB
    keypoints/descriptors for it, so each incoming frame only needs to
    compute its own descriptors and match against these cached ones.
    Also remembers how much the reference was downscaled for ORB, so
    calibration-space polygon points (drawn against the FULL-size
    reference image) can later be mapped into this same coordinate space.
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
    Checks whether the current camera frame looks like the same physical
    scene the calibration reference photo was taken from, AND - if so -
    computes a homography that maps points from the calibration reference
    image's pixel space directly into the CURRENT frame's pixel space.

    Uses ORB feature matching (keypoints + descriptors + Lowe's ratio test)
    rather than raw pixel-to-pixel correlation, which is extremely fragile
    in practice: even a few degrees of rotation or a couple percent of zoom
    - completely normal when a camera drifts or is repositioned - collapses
    a raw correlation score toward zero even though it's obviously the same
    place. Feature matching instead looks for the same distinctive visual
    landmarks (corners, edges, textures) regardless of their exact pixel
    position, and RANSAC then fits the actual rotation/scale/translation
    (even mild perspective skew) between the two views. That transform is
    what lets the fixed calibrated polygons "follow" the parking lot as the
    camera drifts, instead of staying glued to the exact pixels they were
    originally drawn at.

    Returns (aligned, good_match_count, homography|None). homography maps a
    point in the ORIGINAL full-size reference image (the same coordinate
    space the saved slot polygons are stored in) to a point in the current
    frame at its own full resolution.
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

    # Compose: full-size calibration image px -> resized ref-thumb px
    # (via the reference's own downscale) -> resized frame-thumb px (via
    # the ORB homography) -> full-size CURRENT frame px (via the inverse
    # of this frame's downscale). Net result maps calibration-space points
    # straight to where they now sit in the raw, full-resolution frame.
    s_ref = ref_data["thumb_scale"]
    s_frame_inv = 1.0 / frame_scale
    S_ref = np.array([[s_ref, 0, 0], [0, s_ref, 0], [0, 0, 1]], dtype=np.float64)
    S_frame = np.array([[s_frame_inv, 0, 0], [0, s_frame_inv, 0], [0, 0, 1]], dtype=np.float64)
    H_full = S_frame @ H_thumb @ S_ref
    return True, len(good), H_full


def _warp_calibration(calibration: List[dict], H) -> List[dict]:
    """Warps each saved slot polygon through the homography so it lands on
    the parking lot's actual current position/orientation in the live frame."""
    import cv2
    warped = []
    for s in calibration:
        pts = np.array(s["polygon"], dtype=np.float32).reshape(-1, 1, 2)
        warped_pts = cv2.perspectiveTransform(pts, H).reshape(-1, 2).tolist()
        warped.append({**s, "polygon": warped_pts})
    return warped


def _calibration_path(zone_key: str) -> Path:
    return CALIBRATION_DIR / f"{zone_key}.json"


def _reference_image_path(zone_key: str) -> Path:
    return CALIBRATION_DIR / f"{zone_key}_reference.jpg"


def _load_calibration(zone_key: str) -> Optional[List[dict]]:
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
    _calibration_path(zone_key).write_text(
        json.dumps({"zone": zone_key, "slots": slots}, indent=2), encoding="utf-8"
    )


def _point_in_polygon(x: float, y: float, polygon: List[List[float]]) -> bool:
    """Standard ray-casting point-in-polygon test."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def _map_to_slots_calibrated(dets: List[dict], calibration: List[dict]) -> Dict[str, str]:
    """Assign each detection to the fixed slot polygon its box-center falls inside."""
    status = {s["id"]: "Available" for s in calibration}
    best_conf: Dict[str, float] = {}
    for d in dets:
        cx, cy = (d["x1"] + d["x2"]) / 2, (d["y1"] + d["y2"]) / 2
        for s in calibration:
            if _point_in_polygon(cx, cy, s["polygon"]):
                if d["conf"] > best_conf.get(s["id"], -1.0):
                    best_conf[s["id"]] = d["conf"]
                    status[s["id"]] = d["label"]
                break
    return status

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
        logger.info("[SLOT WS] Occupancy model loaded successfully")
        return _slot_model
    except Exception as exc:
        logger.error(f"[SLOT WS] Occupancy model unavailable: {exc}")
        return None


def _enhance(frame):
    import cv2
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def _draw_calibrated_slots(frame, calibration: List[dict], status: Dict[str, str]):
    """
    Draws the FIXED calibrated slot polygons (not the raw, wobbly YOLO boxes).
    Each slot polygon stays glued to the same pixels every frame - only its
    fill color/label changes with the smoothed status - so the on-screen
    overlay is as stable as the calibration itself.
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

        txt = f'{s["id"]} · {label}'
        tx, ty = pts[0]
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(out, (tx, max(0, ty - th - 8)), (tx + tw + 6, ty), color, -1)
        cv2.putText(out, txt, (tx + 3, ty - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    return out


def _draw_notice(frame, message: str):
    """
    Shown whenever we do NOT have a trustworthy, calibrated read on the
    scene - the zone has never been calibrated, or the camera isn't
    currently pointed at the same view the calibration was made from.

    Deliberately does NOT run the detector or draw any boxes here. A
    general-purpose slot model pointed at an unexpected scene (a hand, an
    empty desk, a different angle) will happily produce confident-looking
    "Available"/"Occupied" boxes on things that aren't parking slots at
    all - so once a zone is calibrated, that raw/free-floating detection
    path is retired entirely. A dimmed frame + a plain status message is
    more honest than a bounding box the operator has no way to trust.
    """
    import cv2
    out = (frame.astype(np.float32) * 0.35).astype(np.uint8)
    h, w = out.shape[:2]
    (tw, th), _ = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
    tx, ty = max(10, (w - tw) // 2), h // 2
    cv2.putText(out, message, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return out


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
        logger.error(f"[SLOT WS] DB write failed: {e}")
    finally:
        db.close()


# WebSocket /ws/slots
@ws_router.websocket("/ws/slots")
async def slots_camera_ws(
    websocket: WebSocket,
    zone: str = Query(default="west"),
    camera_index: Optional[str] = Query(default=None),
    conf: float = Query(default=0.25),
):
    """
    Streams the parking-slot camera feed with live occupancy bounding boxes
    (YOLOv8 / pklot.pt) and persists the detected status into the database,
    so the existing GET /api/slots/live polling reflects it automatically.

    Camera source is resolved from `ZONE_CAMERA_DEVICE[zone]` rather than
    blindly trusting whatever `camera_index` the client passes. Right now
    every zone maps to the single physical camera (device "0"); once East
    Plant / East&West Plant get their own cameras, only that mapping needs
    to change. `camera_index` is still accepted as an explicit override for
    testing (e.g. against a video file) but is no longer required.
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

    resolved_source = camera_index if camera_index is not None else ZONE_CAMERA_DEVICE.get(zone, "0")

    import cv2
    source = int(resolved_source) if str(resolved_source).isdigit() else resolved_source

    def _open_camera():
        # On Windows, OpenCV defaults to the MSMF backend for webcams, which
        # is known to open successfully but then fail on the very first
        # cap.read() with an opaque error (-1072875772) on many consumer
        # webcams/drivers. DirectShow (CAP_DSHOW) is far more reliable for
        # this - it's what the offline pipeline.py already uses, which is
        # why that one was stable while this live endpoint wasn't.
        if isinstance(source, int):
            c = cv2.VideoCapture(source, cv2.CAP_DSHOW)
            if not c.isOpened():
                c.release()
                c = cv2.VideoCapture(source)  # fall back to default backend
        else:
            c = cv2.VideoCapture(source)
        if c.isOpened():
            # Some webcams need a brief moment after opening before they can
            # actually deliver a frame - warm up with a few throwaway reads
            # instead of trusting isOpened() alone.
            import time
            for _ in range(5):
                ok, _ = c.read()
                if ok:
                    break
                time.sleep(0.15)
        return c

    cap = await loop.run_in_executor(None, _open_camera)
    if not cap.isOpened():
        await websocket.send_json({"error": f"Camera/Video '{resolved_source}' unavailable.", "conn": "disconnected"})
        await websocket.close()
        return

    # Smooths raw per-frame detections into a stable status per slot so the
    # overlay stops flip-flopping between Occupied/Available frame to frame -
    # a slot only changes once the new state has been consistently observed.
    calibration = _load_calibration(zone)
    ref_thumb = await loop.run_in_executor(None, _load_reference_thumb, zone) if calibration else None
    slot_ids = [s["id"] for s in (calibration or layout)]
    smoother = SlotSmoother(slot_ids, window=8, min_votes_to_flip=5)

    try:
        last_push = 0.0
        last_align_log = 0.0
        consecutive_failures = 0
        while True:
            ret, frame = await loop.run_in_executor(None, cap.read)
            if not ret:
                consecutive_failures += 1
                logger.warning(f"[SLOT WS] Frame read failed ({consecutive_failures}/10).")
                if consecutive_failures >= 10:
                    logger.error("[SLOT WS] Too many consecutive failed reads. Disconnecting.")
                    break
                await asyncio.sleep(0.1)
                continue
            consecutive_failures = 0

            # Only trust/show the calibrated polygons once the camera is
            # actually pointed at the same scene that was calibrated. If a
            # reference photo isn't available, we CANNOT verify alignment, so
            # we default to NOT aligned rather than trusting it blindly - a
            # calibration without a reference photo should never be shown as
            # "active" just because we have no way to check it.
            aligned = False
            align_score = None
            live_calibration = None
            if calibration and ref_thumb is not None:
                aligned, align_score, H = await loop.run_in_executor(None, _estimate_alignment, frame, ref_thumb)
                if aligned and H is not None:
                    live_calibration = await loop.run_in_executor(None, _warp_calibration, calibration, H)
            use_calibration = bool(calibration and live_calibration)

            # Surface the match count (throttled to ~once/sec) so an
            # operator aiming the camera at the calibrated scene can see
            # exactly how close they are to the 12-match threshold in the
            # backend console, instead of only getting a silent pass/fail.
            if align_score is not None and (loop.time() - last_align_log) >= 1.0:
                logger.info(
                    f"[SLOT WS] zone={zone} good_feature_matches={align_score} "
                    f"(need >= 12, aligned={use_calibration})"
                )
                last_align_log = loop.time()

            # The detector only ever runs once we know it's looking at the
            # calibrated scene. No calibration yet, or camera not aligned ->
            # skip inference completely, don't draw anything the operator
            # can't trust, and don't touch the DB with guessed statuses.
            if use_calibration:
                def _infer():
                    enhanced = _enhance(frame)
                    h0, w0 = enhanced.shape[:2]
                    scale = 640 / w0
                    inf_f = cv2.resize(enhanced, (640, int(h0 * scale)))
                    results = model(inf_f, conf=conf, iou=0.45, agnostic_nms=True, verbose=False)
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
            await websocket.send_json({
                "frame": frame_b64,
                "detections": len(dets),
                "occupied": occ,
                "available": (len(status) - occ) if status else 0,
                "calibrated": bool(calibration),
                "calibration_active": bool(use_calibration),
                "align_score": align_score,
            })
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        logger.info("[SLOT WS] Client disconnected.")
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
        logger.warning(f"[ALERT] Zone {zone}: Detection of {ghost_count} unidentified vehicles/vehicles that bypassed OCR in the parking area!")

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


# GET /api/slots/calibration/{zone_key}/defaults
@router.get("/calibration/{zone_key}/defaults")
def calibration_defaults(zone_key: str, current_user=Depends(get_current_user)):
    """
    Returns the zone's slot-ID/category list plus any already-saved
    calibration, without touching the camera. Used when the admin calibrates
    from an uploaded photo instead of a live snapshot.
    """
    if zone_key not in SLOT_LAYOUTS:
        raise HTTPException(status_code=404, detail=f"Unknown zone '{zone_key}'")
    return {
        "zone": zone_key,
        "default_slots": SLOT_LAYOUTS[zone_key],
        "slots": _load_calibration(zone_key) or [],
    }


# NOTE: the old GET /calibration/{zone_key}/snapshot endpoint (grabbing a
# frame directly from the camera for calibration) has been removed. It was
# opening the same physical camera device the live Slot Occupancy feature
# uses, which caused the two to lock each other out. Calibration now only
# supports the "Upload Photo" flow (see /calibration/{zone_key}/defaults
# below), which never touches the camera - so the camera stays fully
# available to Slot Occupancy at all times.


# GET /api/slots/calibration/{zone_key}
@router.get("/calibration/{zone_key}")
def get_calibration(zone_key: str, current_user=Depends(get_current_user)):
    """Returns the currently saved polygon calibration for a zone, if any."""
    if zone_key not in SLOT_LAYOUTS:
        raise HTTPException(status_code=404, detail=f"Unknown zone '{zone_key}'")
    slots = _load_calibration(zone_key) or []
    return {"zone": zone_key, "slots": slots, "calibrated": len(slots) > 0}


# POST /api/slots/calibration/{zone_key}
@router.post("/calibration/{zone_key}")
def save_calibration(zone_key: str, payload: dict, current_user=Depends(get_current_user)):
    """
    Saves the fixed slot polygons drawn by an admin. Body: {"slots": [...],
    "reference_image": "<base64 jpeg, no data: prefix>"}. The reference image
    is what the camera view looked like at calibration time - it's stored so
    the live feed can later be compared against it and the overlay only
    shown once the camera is actually pointed at the same parking area
    (see `_estimate_alignment` / usage in the WS loop below).
    """
    if getattr(current_user, "role", None) != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can save slot calibration")
    if zone_key not in SLOT_LAYOUTS:
        raise HTTPException(status_code=404, detail=f"Unknown zone '{zone_key}'")

    slots = payload.get("slots")
    if not isinstance(slots, list) or not slots:
        raise HTTPException(status_code=400, detail="`slots` must be a non-empty list")
    for s in slots:
        if not all(k in s for k in ("id", "category", "polygon")):
            raise HTTPException(status_code=400, detail="Each slot needs id, category, and polygon")
        if not isinstance(s["polygon"], list) or len(s["polygon"]) < 3:
            raise HTTPException(status_code=400, detail=f"Slot '{s.get('id')}' polygon needs at least 3 points")

    # A reference image is mandatory - without it the live WS loop has no way
    # to verify the camera is actually pointed at the calibrated scene, and
    # would otherwise never be able to show the calibrated overlay (aligned
    # defaults to False when there's nothing to compare against). Rejecting
    # here prevents saving a "blind" calibration that can never activate.
    ref_b64 = payload.get("reference_image")
    if not ref_b64:
        raise HTTPException(
            status_code=400,
            detail="`reference_image` is required so the camera view can later be verified against it",
        )
    try:
        ref_bytes = base64.b64decode(ref_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="`reference_image` must be valid base64")

    _save_calibration(zone_key, slots)
    _reference_image_path(zone_key).write_bytes(ref_bytes)

    return {"zone": zone_key, "saved": len(slots), "calibrated": True}


# PATCH /api/slots/zones/{zone_key}/capacity
@router.patch("/zones/{zone_key}/capacity")
def update_zone_capacity(
    zone_key: str,
    payload: CapacityUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Lets an Admin edit how many Employee/Vendor/Visitor slots a zone has.
    Backs the "Set Capacity" button on the Parking Tracker page and writes
    straight into the `parking_zone` table (total_capacity is kept in sync
    as the sum of the three category capacities).
    """
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