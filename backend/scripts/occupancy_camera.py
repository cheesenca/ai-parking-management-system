from __future__ import annotations

import cv2
import logging
import numpy as np
import sys
import time
import argparse
import threading
import requests
from pathlib import Path
from datetime import datetime

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.models import ParkingZone
from app.features.occupancy.services.occupancy import load_parking_map, compute_iou

logger = logging.getLogger(__name__)

COLOR_AVAIL = (30, 200, 60)
COLOR_OCC = (30, 60, 220)
SMOOTHING_WINDOW = 5


def _bootstrap(f):
    """
    Bootstrap sys.path
    """
    for p in Path(f).resolve().parents:
        if (p / "requirements.txt").exists() and (p / "app").is_dir():
            if str(p) not in sys.path: sys.path.insert(0, str(p))
            break
        
_bootstrap(__file__)

try:
    import torch
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    DEVICE = "cpu"


class SlotSmoother:
    """
    Tracks recent status history per slot
    """
    def __init__(self, slot_ids: list[str], window: int = SMOOTHING_WINDOW):
        """
        SlotSmoother initialization
        """
        self.window = window
        self.history: dict[str, list[str]] = {sid: [] for sid in slot_ids}
        self.stable: dict[str, str] = {sid: "Available" for sid in slot_ids}


    def update(self, raw_status: dict[str, str]) -> dict[str, str]:
        """
        Updates status history and computes the stable status from a >50% majority
        """
        for sid, status in raw_status.items():
            hist = self.history.setdefault(sid, [])
            hist.append(status)
            if len(hist) > self.window:
                hist.pop(0)
            occupied_votes = hist.count("Occupied")
            self.stable[sid] = "Occupied" if occupied_votes > len(hist) / 2 else "Available"
        return self.stable


class Camera:
    def __init__(self, src):
        """
        Opens the video stream and immediately starts the background thread for reading frames
        """
        self.cap = cv2.VideoCapture(src, cv2.CAP_DSHOW if isinstance(src, int) else 0)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._f, self._lock, self._stop = None, threading.Lock(), threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()


    def _loop(self):
        """
        Continuous background frame capture cycle
        """
        while not self._stop.is_set():
            ret, f = self.cap.read()
            if ret:
                with self._lock: self._f = f
            else:
                time.sleep(0.01)


    def read(self):
        """
        Captures a copy of the latest frame without blocking the main thread
        """
        with self._lock:
            return self._f is not None, (self._f.copy() if self._f is not None else None)


    def release(self):
        """
        Stop the thread and release the camera hardware
        """
        self._stop.set(); self.cap.release()


def enhance(frame: np.ndarray) -> np.ndarray:
    """
    Enhancing local image contrast using the CLAHE method
    """
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def draw(frame: np.ndarray, parking_map: dict, slot_status: dict[str, str], fps: float) -> np.ndarray:
    """
    Draw the fixed slot polygons from parking_map.json colour-coded by their smoothed status
    """
    out = frame.copy()
    h, w = out.shape[:2]

    for slot in parking_map["slots"]:
        pts = np.array(slot["polygon"], dtype=np.int32).reshape(-1, 1, 2)
        status = slot_status.get(slot["id"], "Available")
        color = COLOR_OCC if status == "Occupied" else COLOR_AVAIL

        ov = out.copy()
        cv2.fillPoly(ov, [pts], color)
        cv2.addWeighted(ov, 0.25, out, 0.75, 0, out)
        cv2.polylines(out, [pts], True, color, 2)

        M = cv2.moments(pts)
        if M["m00"]:
            cx, cy = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
            cv2.putText(out, slot["id"], (cx - 12, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    total = len(parking_map["slots"])
    occupied = sum(1 for s in slot_status.values() if s == "Occupied")
    zone = parking_map.get("zone", "Zone")

    ov = out.copy()
    cv2.rectangle(ov, (0, 0), (w, 42), (20, 20, 20), -1)
    cv2.addWeighted(ov, 0.72, out, 0.28, 0, out)
    cv2.putText(out, f"{zone.upper()} - Occupied: {occupied}/{total}  Free: {total - occupied}", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    t = f"{fps:.0f} fps"
    (fw, fh), _ = cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    cv2.rectangle(out, (w-fw-8, h-fh-8), (w-2, h-2), (0, 0, 0), -1)
    cv2.putText(out, t, (w-fw-4, h-4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
    return out


def detect_slots(model, frame: np.ndarray, parking_map: dict, conf: float, iou_thresh: float) -> dict[str, str]:
    """
    Run YOLO on the full frame and map each vehicle detection to a fixed slot polygon using IoU overlap
    """
    results = model(
        frame,
        classes=settings.VEHICLE_CLASSES,
        conf=conf,
        iou=settings.YOLO_IOU_NMS,
        device=DEVICE,
        verbose=False,
    )

    detections = []
    for box in (results[0].boxes or []):
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        detections.append([x1, y1, x2, y2])

    raw_status: dict[str, str] = {}
    for slot in parking_map["slots"]:
        occupied = any(compute_iou(slot["polygon"], det) >= iou_thresh for det in detections)
        raw_status[slot["id"]] = "Occupied" if occupied else "Available"
    return raw_status


def get_category_totals(zone: str) -> dict[str, int]:
    """
    Retrieve total capacity datafor each category within a specific zone directly from the database
    """
    db = SessionLocal()
    try:
        z = db.query(ParkingZone).filter(ParkingZone.zone_key == zone).first()
        if not z:
            logger.warning(f"Zone '{zone}' not found in DB; category totals default to 0")
            return {"Employee": 0, "Vendor": 0, "Visitor": 0}
        return {
            "Employee": z.employee_capacity,
            "Vendor": z.vendor_capacity,
            "Visitor": z.visitor_capacity,
        }
    finally:
        db.close()


def push(zone: str, slot_status: dict[str, str], id2cat: dict[str, str], category_total: dict[str, int]):
    """
    Aggregating occupancy summaries by category and sending HTTP POST to the backend server API asynchronously
    """
    cats: dict[str, dict] = {}
    for sid, st in slot_status.items():
        cat = id2cat.get(sid, "Employee")
        if cat not in cats:
            cats[cat] = {"used": 0, "total": category_total.get(cat, 0), "available": 0, "rate_pct": 0}
        if st == "Occupied":
            cats[cat]["used"] += 1

    for cat, d in cats.items():
        d["available"] = max(0, d["total"] - d["used"])
        d["rate_pct"] = round(d["used"] / d["total"] * 100, 1) if d["total"] else 0.0

    try:
        r = requests.post(f"{settings.BACKEND_URL}/api/slots/update", timeout=0.8, json={
            "zone": zone,
            "timestamp": datetime.now().isoformat(),
            "slots": [{"id": k, "status": v, "category": id2cat.get(k, "Employee")} for k, v in slot_status.items()],
            "category_summary": cats,
        })
        if r.status_code == 200:
            occ = sum(1 for v in slot_status.values() if v == "Occupied")
            logger.info(f"push OK occupied={occ}/{len(slot_status)}")
    except Exception as e:
        logger.warning(f"failed to push: {e}")


def run(source: str, zone: str = "west", conf: float | None = None):
    """
    Main cycle of the Parking AI pipeline
    """
    conf = conf if conf is not None else settings.YOLO_CONF
    iou_thresh = settings.IOU_THRESHOLD

    logger.info(f"Device: {settings.DEVICE.upper()}")
    logger.info(f"Model: {settings.OCCUPANCY_MODEL_PATH}")
    logger.info(f"Conf: {conf}  IoU threshold: {iou_thresh}  Smoothing window: {SMOOTHING_WINDOW}")

    parking_map = load_parking_map(settings.PARKING_MAP_JSON)
    slot_ids = [s["id"] for s in parking_map["slots"]]
    id2cat = {s["id"]: s.get("category", "Employee") for s in parking_map["slots"]}
    smoother = SlotSmoother(slot_ids)

    category_total = get_category_totals(zone)
    logger.info(f"Category totals for zone '{zone}': {category_total}")

    from ultralytics import YOLO
    
    t0 = time.time()
    model = YOLO(str(settings.OCCUPANCY_MODEL_PATH))
    model.to(settings.DEVICE)
    logger.info(f"Model loaded {time.time()-t0:.1f}s")

    if settings.DEVICE == "cuda":
        model(np.zeros((480, 640, 3), dtype=np.uint8), device=settings.DEVICE, verbose=False)
        logger.info("GPU warm-up OK")

    src = int(source) if source.isdigit() else source
    cam = Camera(src)
    time.sleep(1.0)
    ret, test = cam.read()
    if not ret or test is None:
        logger.error(f"Can't open the camera: {source}")
        cam.release(); return

    logger.info("Active Camera. q=exit, +/-=confidence configuration")
    cv2.namedWindow("Live Occupancy Monitor", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Live Occupancy Monitor", 960, 540)

    last_push = 0.0
    fps_t = time.time(); fps_n = 0; fps = 0.0

    while True:
        ret, frame = cam.read()
        if not ret or frame is None:
            time.sleep(0.01); continue

        enhanced = enhance(frame)

        try:
            raw_status = detect_slots(model, enhanced, parking_map, conf, iou_thresh)
            stable_status = smoother.update(raw_status)
        except Exception as e:
            logger.warning(f"{e}")
            stable_status = smoother.stable

        fps_n += 1
        if fps_n >= 15:
            fps = fps_n / (time.time() - fps_t); fps_t = time.time(); fps_n = 0
        cv2.imshow("Live Occupancy Monitor", draw(frame, parking_map, stable_status, fps))

        now = time.time()
        if now - last_push >= 0.5:
            threading.Thread(target=push, args=(zone, stable_status, id2cat, category_total), daemon=True).start()
            last_push = now

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            logger.info("Stopped"); break
        elif key == ord('+') and conf < 0.95:
            conf = round(conf + 0.05, 2); logger.info(f"Confidence -> {conf}")
        elif key == ord('-') and conf > 0.05:
            conf = round(conf - 0.05, 2); logger.info(f"Confidence -> {conf}")

    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    from app.core.logging import setup_logging
    setup_logging()

    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0")
    ap.add_argument("--zone", default="west")
    ap.add_argument("--conf", type=float, default=None)
    args = ap.parse_args()
    run(args.source, args.zone, args.conf)
    