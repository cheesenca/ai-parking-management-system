from __future__ import annotations

from typing import Dict, List

IOU_MATCH_THRESHOLD = 0.10

def compute_iou(slot_polygon_pts: list, det_bbox: list) -> float:
    """Intersection-over-union between a slot polygon and a detection bbox"""
    try:
        from shapely.geometry import Polygon, box as shapely_box
    except ImportError as exc:
        raise ImportError("shapely library not found") from exc

    slot_poly = Polygon(slot_polygon_pts)
    det_poly = shapely_box(*det_bbox)

    if not slot_poly.is_valid or not det_poly.is_valid:
        return 0.0

    intersection = slot_poly.intersection(det_poly).area
    union = slot_poly.union(det_poly).area
    return intersection / union if union > 0 else 0.0


def map_detections_to_slots(dets: List[dict], calibration: List[dict]) -> Dict[str, str]:
    """Map detected bounding boxes to parking slots based on IoU with calibration polygons"""
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


class SlotSmoother:
    """Simple temporal smoothing for parking slot occupancy status"""
    def __init__(self, slot_ids: List[str], window: int = 8, min_votes_to_flip: int = 5):
        """Initialize the SlotSmoother with a list of slot IDs"""
        self.window = window
        self.min_votes_to_flip = min_votes_to_flip
        self.history: Dict[str, List[str]] = {sid: [] for sid in slot_ids}
        self.stable: Dict[str, str] = {sid: "Available" for sid in slot_ids}


    def update(self, raw_status: Dict[str, str]) -> Dict[str, str]:
        """Feed one frame's raw per-slot status, return the smoothed status"""
        for sid, status in raw_status.items():
            hist = self.history.setdefault(sid, [])
            hist.append(status)
            if len(hist) > self.window:
                hist.pop(0)

            occupied_votes = hist.count("Occupied")
            current = self.stable.get(sid, "Available")

            if current == "Available" and occupied_votes >= self.min_votes_to_flip:
                self.stable[sid] = "Occupied"
            elif current == "Occupied" and (len(hist) - occupied_votes) >= self.min_votes_to_flip:
                self.stable[sid] = "Available"
        return self.stable


    def reset(self, slot_ids: List[str]) -> None:
        """Reset the smoother's history and stable status for a new set of slot IDs"""
        self.history = {sid: [] for sid in slot_ids}
        self.stable = {sid: "Available" for sid in slot_ids}