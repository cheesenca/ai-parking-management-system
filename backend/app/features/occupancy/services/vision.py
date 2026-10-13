from __future__ import annotations

import numpy as np
import logging
import cv2
import torch
import base64
from ultralytics import YOLO
from typing import Dict, List

from app.core.config import settings

logger = logging.getLogger(__name__)

COLOR_AVAILABLE = (30, 200, 60)
COLOR_OCCUPIED = (30, 60, 220)
INFERENCE_WIDTH = 640

_model = None
_device = None

def get_slot_model():
    """Lazily load and cache the YOLO occupancy model"""
    global _model, _device
    if _model is not None:
        return _model

    try:
        _device = "cuda" if torch.cuda.is_available() and settings.YOLO_DEVICE.lower() != "cpu" else "cpu"
        _model = YOLO(str(settings.OCCUPANCY_MODEL_PATH))
        _model.to(_device)
        logger.info("Occupancy model loaded successfully on device=%s", _device)
        return _model
    except Exception as exc:
        logger.error("Occupancy model unavailable: %s", exc)
        return None


def enhance(frame):
    """Dynamically enhancing local image contrast using the CLAHE method in the LAB color space"""
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def run_inference(frame, model, conf: float, device: str) -> List[dict]:
    """Run YOLO on one (enhanced) frame, return detections in original-frame coordinates"""
    enhanced = enhance(frame)
    h0, w0 = enhanced.shape[:2]
    scale = INFERENCE_WIDTH / w0
    inf_frame = cv2.resize(enhanced, (INFERENCE_WIDTH, int(h0 * scale)))

    results = model(inf_frame, conf=conf, iou=0.45, agnostic_nms=True, device=device, verbose=False)
    dets: List[dict] = []
    for box in (results[0].boxes or []):
        cls_id = int(box.cls[0])
        x1, y1, x2, y2 = [v / scale for v in box.xyxy[0].tolist()]
        dets.append({
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "label": "Available" if cls_id == 0 else "Occupied",
            "conf": float(box.conf[0]),
        })
    return dets


def draw_calibrated_slots(frame, calibration: List[dict], status: Dict[str, str]):
    """Draw slot polygons on the frame, colored by availability"""
    out = frame.copy()
    for s in calibration:
        pts = [(int(x), int(y)) for x, y in s["polygon"]]
        label = status.get(s["id"], "Available")
        color = COLOR_AVAILABLE if label == "Available" else COLOR_OCCUPIED

        overlay = out.copy()
        cv2.fillPoly(overlay, [np.array(pts, dtype=np.int32)], color)
        cv2.addWeighted(overlay, 0.28, out, 0.72, 0, out)
        cv2.polylines(out, [np.array(pts, dtype=np.int32)], True, color, 2)

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        cx, cy = sum(xs) // len(xs), sum(ys) // len(ys)
        slot_w, slot_h = max(xs) - min(xs), max(ys) - min(ys)

        font_scale = max(0.28, min(0.42, min(slot_w, slot_h) / 90))
        txt = str(s["id"])
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        tx, ty = cx - tw // 2, cy + th // 2

        cv2.putText(out, txt, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, txt, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def draw_notice(frame, message: str):
    """Displays a notification message in the center of the screen while dimming the entire camera video frame"""
    out = (frame.astype(np.float32) * 0.35).astype(np.uint8)
    h, w = out.shape[:2]
    (tw, th), _ = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
    tx, ty = max(10, (w - tw) // 2), h // 2
    cv2.putText(out, message, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def encode_jpeg_b64(frame, quality: int = 65) -> str:
    """Encode a frame as a JPEG image"""
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf.tobytes()).decode()