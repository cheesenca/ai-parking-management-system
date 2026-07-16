from __future__ import annotations
import sys
import cv2
import json
import numpy as np
from pathlib import Path
from typing import Dict, List
from app.core.config import (
    OCCUPANCY_MODEL_PATH, 
    YOLO_BASE_MODEL,
    YOLO_CONF, 
    YOLO_IOU_NMS, 
    YOLO_DEVICE, 
    YOLO_IMGSZ,
    VEHICLE_CLASSES, 
    IOU_THRESHOLD,
    PARKING_MAP_JSON, 
    FEATURE_ROOT,
)

CAPACITY_CONFIG_JSON = FEATURE_ROOT / "data" / "capacity_config.json" 
_yolo = None

# Bootstrap sys.path
def _bootstrap(f: str) -> None:
    p = Path(f).resolve()
    feat = proj = None
    for parent in p.parents:
        if parent.name == "parking-slot-occupancy" and feat is None:
            feat = parent
        if (parent / "requirements.txt").exists() and (parent / "app").is_dir() and proj is None:
            proj = parent
        if feat and proj:
            break
    for root in filter(None, [str(proj), str(feat)]):
        if root not in sys.path:
            sys.path.insert(0, root)
_bootstrap(__file__)


def load_capacity_config(path: Path = CAPACITY_CONFIG_JSON) -> dict:
    """
    Load capacity_config.json which defines total slots per category for each zone
    """
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def get_category_summary(
    parking_map: dict,
    slot_status: Dict[str, str],
    capacity_config: dict | None = None,
) -> Dict[str, dict]:
    """
    Compute summary of used/available slots and occupancy rate per category
    """
    if capacity_config is None:
        capacity_config = load_capacity_config()

    zone = parking_map.get("zone", "west")
    zone_capacity = capacity_config.get(zone, {})

    # Count occupied slots per category from parking_map polygons
    occupied_by_cat: Dict[str, int] = {}
    for slot in parking_map["slots"]:
        cat = slot.get("category", "Employee")
        if slot_status.get(slot["id"]) == "Occupied":
            occupied_by_cat[cat] = occupied_by_cat.get(cat, 0) + 1

    # Build summary 
    summary: Dict[str, dict] = {}
    for cat, total in zone_capacity.items():
        used = occupied_by_cat.get(cat, 0)
        available = max(0, total - used)
        rate = round(used / total * 100, 1) if total else 0.0
        summary[cat] = {
            "used": used,
            "total": total,
            "available": available,
            "rate_pct": rate,
        }

    # Also add categories present in parking_map but not in capacity_config
    for slot in parking_map["slots"]:
        cat = slot.get("category", "Employee")
        if cat not in summary:
            used = occupied_by_cat.get(cat, 0)
            summary[cat] = {
                "used": used,
                "total": used,   
                "available": 0,
                "rate_pct": 100.0 if used else 0.0,
            }

    return summary


class SlotSmoother:
    """
    Tracks recent status history per slot and only reports a status once it
    has been the majority result for the last `window` frames. This is what
    keeps the overlay from flickering Occupied/Available back and forth when
    a single frame's detection is noisy - the slot only "flips" once the new
    state has been consistently seen, and stays put otherwise.
    """
    def __init__(self, slot_ids: List[str], window: int = 8, min_votes_to_flip: int = 5):
        self.window = window
        self.min_votes_to_flip = min_votes_to_flip
        self.history: Dict[str, List[str]] = {sid: [] for sid in slot_ids}
        self.stable: Dict[str, str] = {sid: "Available" for sid in slot_ids}

    def update(self, raw_status: Dict[str, str]) -> Dict[str, str]:
        for sid, status in raw_status.items():
            hist = self.history.setdefault(sid, [])
            hist.append(status)
            if len(hist) > self.window:
                hist.pop(0)

            occupied_votes = hist.count("Occupied")
            current = self.stable.get(sid, "Available")

            # Only flip the reported state once enough consistent votes have
            # accumulated - a single noisy frame can no longer toggle a slot.
            if current == "Available" and occupied_votes >= self.min_votes_to_flip:
                self.stable[sid] = "Occupied"
            elif current == "Occupied" and (len(hist) - occupied_votes) >= self.min_votes_to_flip:
                self.stable[sid] = "Available"
        return self.stable

    def reset(self, slot_ids: List[str]) -> None:
        self.history = {sid: [] for sid in slot_ids}
        self.stable = {sid: "Available" for sid in slot_ids}


def _get_yolo():
    """
    Lazy-load YOLOv8 model on first use
    """
    global _yolo
    if _yolo is None:
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError("ultralytics library not found")
        model_path = str(OCCUPANCY_MODEL_PATH) if OCCUPANCY_MODEL_PATH.exists() else YOLO_BASE_MODEL
        print(f"Loading YOLOv8: {model_path}")
        _yolo = YOLO(model_path)
    return _yolo


def load_parking_map(path: Path = PARKING_MAP_JSON) -> dict:
    """
    Load parking_map.json which defines slot polygons and metadata
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Parking map not found: {path}\n"
            "Run first: python scripts/annotate_slots.py --image reference_frame.jpg"
        )
    with open(path) as f:
        return json.load(f)


def compute_iou(slot_polygon_pts: list, det_bbox: list) -> float:
    """
    Compute Intersection over Union between a slot polygon and a detection bbox
    """
    try:
        from shapely.geometry import Polygon, box as shapely_box
    except ImportError:
        raise ImportError("shapely library not found")

    slot_poly = Polygon(slot_polygon_pts)
    det_poly  = shapely_box(*det_bbox)

    if not slot_poly.is_valid or not det_poly.is_valid:
        return 0.0

    intersection = slot_poly.intersection(det_poly).area
    union = slot_poly.union(det_poly).area
    return intersection / union if union > 0 else 0.0


def detect_occupancy(
    frame: np.ndarray,
    parking_map: dict,
    iou_thresh:  float = IOU_THRESHOLD,
) -> Dict[str, str]:
    """
    Detect vehicle presence and map to parking slots
    """
    yolo = _get_yolo()
    results = yolo(
        frame,
        classes = VEHICLE_CLASSES,
        conf = YOLO_CONF,
        iou = YOLO_IOU_NMS,
        imgsz = YOLO_IMGSZ,
        device = YOLO_DEVICE,
        verbose = False,
    )

    detections: List[List[float]] = []
    for box in (results[0].boxes or []):
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        detections.append([x1, y1, x2, y2])

    slot_status: Dict[str, str] = {}
    for slot in parking_map["slots"]:
        occupied = any(
            compute_iou(slot["polygon"], det) >= iou_thresh
            for det in detections
        )
        slot_status[slot["id"]] = "Occupied" if occupied else "Available"

    return slot_status


def detect_occupancy_from_results(
    yolo_results,
    parking_map: dict,
    iou_thresh:  float = IOU_THRESHOLD,
) -> Dict[str, str]:
    """
    Map pre-computed YOLO results to parking slots
    """
    detections: List[List[float]] = []
    for box in (yolo_results[0].boxes or []):
        cls_id = int(box.cls[0])
        if cls_id in VEHICLE_CLASSES:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append([x1, y1, x2, y2])

    slot_status: Dict[str, str] = {}
    for slot in parking_map["slots"]:
        occupied = any(
            compute_iou(slot["polygon"], det) >= iou_thresh
            for det in detections
        )
        slot_status[slot["id"]] = "Occupied" if occupied else "Available"

    return slot_status


def draw_occupancy(
    frame: np.ndarray,
    parking_map: dict,
    slot_status: Dict[str, str],
    alpha: float = 0.35,
) -> np.ndarray:
    """
    Draw parking slots with color coding and occupancy summary overlay
    """
    out = frame.copy()
    for slot in parking_map["slots"]:
        pts = np.array(slot["polygon"], dtype=np.int32).reshape(-1, 1, 2)
        status = slot_status.get(slot["id"], "Available")
        colour = (0, 0, 220) if status == "Occupied" else (0, 220, 0)

        overlay = out.copy()
        cv2.fillPoly(overlay, [pts], colour)
        cv2.addWeighted(overlay, alpha, out, 1 - alpha, 0, out)
        cv2.polylines(out, [pts], True, colour, 2)

        M = cv2.moments(pts)
        if M["m00"]:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            cv2.putText(out, slot["id"], (cx - 10, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

    total = len(parking_map["slots"])
    occupied = sum(1 for s in slot_status.values() if s == "Occupied")
    available = total - occupied
    rate = occupied / total * 100 if total else 0.0

    ov = out.copy()
    cv2.rectangle(ov, (0, 0), (out.shape[1], 42), (20, 20, 20), -1)
    cv2.addWeighted(ov, 0.72, out, 0.28, 0, out)
    zone = parking_map.get("zone", "Zone")
    cv2.putText(out, f"{zone.upper()} — Occupied: {occupied}/{total}  Free: {available}  ({rate:.1f}%)", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255, 255, 255), 1)
    return out