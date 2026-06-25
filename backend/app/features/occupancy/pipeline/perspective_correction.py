from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# Bootstrap sys.path to find project modules regardless of execution CWD
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

from app.core.config import (
    HOMOGRAPHY_SRC, HOMOGRAPHY_W, HOMOGRAPHY_H, HOMOGRAPHY_MATRIX
)

_M: Optional[np.ndarray] = None 


def _dst_points() -> np.ndarray:
    return np.float32([
        [0, 0],
        [HOMOGRAPHY_W, 0],
        [HOMOGRAPHY_W, HOMOGRAPHY_H],
        [0, HOMOGRAPHY_H],
    ])


def compute_matrix(src_points: list) -> np.ndarray:
    """
    Compute 3x3 homography from four source corner points (TL→TR→BR→BL)
    """
    return cv2.getPerspectiveTransform(np.float32(src_points), _dst_points())


def save_matrix(M: np.ndarray, path: Path = HOMOGRAPHY_MATRIX) -> None:
    """
    Save the homography matrix to a .npy file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(path), M)
    print(f"[perspective] Matrix saved → {path}")


def load_matrix(path: Path = HOMOGRAPHY_MATRIX) -> Optional[np.ndarray]:
    """
    Load the homography matrix from a .npy file or return None if not found
    """
    return np.load(str(path)) if path.exists() else None


def to_bird_eye(frame: np.ndarray) -> np.ndarray:
    """
    Apply perspective transformation to get a bird's-eye view of the parking lot
    """
    global _M
    if HOMOGRAPHY_SRC is None:
        return frame
    if _M is None:
        _M = load_matrix()
        if _M is None and HOMOGRAPHY_SRC is not None:
            _M = compute_matrix(HOMOGRAPHY_SRC)
            save_matrix(_M)
        elif _M is None:
            return frame
    return cv2.warpPerspective(frame, _M, (HOMOGRAPHY_W, HOMOGRAPHY_H))


def interactive_calibrate(reference: np.ndarray) -> Optional[np.ndarray]:
    """
    Interactive calibration tool to compute homography matrix from user-selected corners
    """
    img = reference.copy()
    points = []
    LABELS = ["Top-Left", "Top-Right", "Bottom-Right", "Bottom-Left"]
    COLORS = [(0,255,0), (0,200,255), (0,0,255), (255,0,255)]

    def on_mouse(event, x, y):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
            points.append([x, y])
            i = len(points) - 1
            cv2.circle(img, (x, y), 8, COLORS[i], -1)
            cv2.putText(img, LABELS[i], (x+10, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS[i], 2)
            if len(points) > 1:
                cv2.line(img, tuple(points[-2]), tuple(points[-1]), (200,200,200), 1)
            if len(points) == 4:
                cv2.line(img, tuple(points[-1]), tuple(points[0]), (200,200,200), 1)

    win = "Calibration, click 4 corners, S: save | Q: quit"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, min(1280, reference.shape[1]), min(720, reference.shape[0]))
    cv2.setMouseCallback(win, on_mouse)

    result = None
    while True:
        cv2.imshow(win, img)
        key = cv2.waitKey(30) & 0xFF
        if key == ord("s") and len(points) == 4:
            M = compute_matrix(points)
            save_matrix(M)
            print(f"[perspective] Calibration done. "
                  f"Copy to config.py:\nHOMOGRAPHY_SRC = {points}")
            result = M
            break
        elif key == ord("q"):
            break

    cv2.destroyWindow(win)
    return result