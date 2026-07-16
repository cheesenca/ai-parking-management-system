from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Dict, List

from app.core.config import settings

CAPACITY_CONFIG_JSON = settings.SLOT_ROOT / "data" / "capacity_config.json" 

def _bootstrap(f: str) -> None:
    """
    Bootstrap sys.path
    """
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


class SlotSmoother:
    """
    Tracks recent status history per slot 
    """
    def __init__(self, slot_ids: List[str], window: int = 8, min_votes_to_flip: int = 5):
        """
        SlotSmoother initialization
        """
        self.window = window
        self.min_votes_to_flip = min_votes_to_flip
        self.history: Dict[str, List[str]] = {sid: [] for sid in slot_ids}
        self.stable: Dict[str, str] = {sid: "Available" for sid in slot_ids}


    def update(self, raw_status: Dict[str, str]) -> Dict[str, str]:
        """
        Updating status history with the latest detection data
        """
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
        """
        Reset the status for a specific list of slots to the initial state
        """
        self.history = {sid: [] for sid in slot_ids}
        self.stable = {sid: "Available" for sid in slot_ids}


def load_capacity_config(path: Path = CAPACITY_CONFIG_JSON) -> dict:
    """
    Load capacity_config.json which defines total slots per category for each zone
    """
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def load_parking_map(path: Path = settings.PARKING_MAP_JSON) -> dict:
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