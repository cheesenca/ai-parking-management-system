from __future__ import annotations

import json
import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional

from app.core.config import BASE_DIR

CALIBRATION_DIR = BASE_DIR / "data" / "occupancy" / "calibration"
CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)

MIN_GOOD_MATCHES = 12

# Resize reference image to accelerate the computation process 
ORB_THUMB_WIDTH = 480

def calibration_path(zone_key: str) -> Path:
    """Get the JSON file path where the calibrated slot polygon coordinates are stored"""
    return CALIBRATION_DIR / f"{zone_key}.json"


def reference_image_path(zone_key: str) -> Path:
    """Obtaining the file path of the image used as the reference for the initial calibration photo"""
    return CALIBRATION_DIR / f"{zone_key}_reference.jpg"


def load_calibration(zone_key: str) -> Optional[List[dict]]:
    """Loads stored parking slot polygon calibration data from a JSON file"""
    path = calibration_path(zone_key)
    if not path.exists():
        return None
    
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        slots = data.get("slots", [])
        return slots if slots else None
    except (json.JSONDecodeError, OSError):
        return None


def save_calibration(zone_key: str, slots: List[dict]) -> None:
    """Save the newly calibrated parking slot polygon coordinate data to a JSON file"""
    calibration_path(zone_key).write_text(
        json.dumps({"zone": zone_key, "slots": slots}, indent=2), encoding="utf-8"
    )


def load_reference_thumb(zone_key: str) -> Optional[dict]:
    """Loads the stored calibration reference image, pre-computes keypoints, and descriptors using the ORB algorithm"""
    path = reference_image_path(zone_key)
    if not path.exists():
        return None

    ref = cv2.imread(str(path))
    if ref is None:
        return None

    gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    thumb_scale = ORB_THUMB_WIDTH / w
    gray = cv2.resize(gray, (ORB_THUMB_WIDTH, int(h * thumb_scale)))
    orb = cv2.ORB_create(nfeatures=500)
    kp, des = orb.detectAndCompute(gray, None)
    return {
        "kp": kp, 
        "des": des, 
        "shape": gray.shape, 
        "thumb_scale": thumb_scale,
    }


def estimate_alignment(frame, ref_data: Optional[dict], min_good_matches: int = MIN_GOOD_MATCHES):
    """Checks if the current camera frame matches the calibration reference and computes the homography matrix"""
    if ref_data is None or ref_data.get("des") is None:
        return False, 0, None

    h_frame, w_frame = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame_scale = ORB_THUMB_WIDTH / w_frame
    gray_r = cv2.resize(gray, (ORB_THUMB_WIDTH, int(h_frame * frame_scale)))

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
    homography_thumb, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if homography_thumb is None or mask is None or int(mask.sum()) < min_good_matches:
        return False, len(good), None

    s_ref = ref_data["thumb_scale"]
    scale_ref = np.array([
        [s_ref, 0, 0], 
        [0, s_ref, 0], 
        [0, 0, 1]
    ], dtype=np.float64)

    s_frame_inv = 1.0 / frame_scale
    scale_frame = np.array([
        [s_frame_inv, 0, 0], 
        [0, s_frame_inv, 0], 
        [0, 0, 1]
    ], dtype=np.float64)

    homography_full = scale_frame @ homography_thumb @ scale_ref
    return True, len(good), homography_full


def warp_calibration(calibration: List[dict], homography) -> List[dict]:
    """Transforms the calibrated parking slot polygon to align with the current live frame using the homography matrix"""
    warped = []
    for s in calibration:
        pts = np.array(s["polygon"], dtype=np.float32).reshape(-1, 1, 2)
        warped_pts = cv2.perspectiveTransform(pts, homography).reshape(-1, 2).tolist()
        warped.append({**s, "polygon": warped_pts})
    return warped