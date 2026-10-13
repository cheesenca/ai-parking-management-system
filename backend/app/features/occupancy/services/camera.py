from __future__ import annotations

import logging
import time
import cv2
from typing import Optional, Union

logger = logging.getLogger(__name__)

CAMERA_OPEN_ATTEMPTS = 4
CAMERA_WARMUP_READS = 5
CAMERA_RETRY_DELAY_SEC = 0.4


def resolve_source(raw_source: str) -> Union[int, str]:
    """A numeric string means a local device index; anything else is a stream URL/path"""
    return int(raw_source) if str(raw_source).isdigit() else raw_source


def open_camera(source: Union[int, str]):
    """Open a camera source with retries and warmup reads"""
    cap = None
    for attempt in range(CAMERA_OPEN_ATTEMPTS):
        if isinstance(source, int):
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(source)
        else:
            cap = cv2.VideoCapture(source)

        if cap.isOpened():
            for _ in range(CAMERA_WARMUP_READS):
                ok, _ = cap.read()
                if ok:
                    return cap
                time.sleep(0.15)
            cap.release()

        logger.warning(
            "Camera '%s' open attempt %d/%d failed, retrying...",
            source, attempt + 1, CAMERA_OPEN_ATTEMPTS,
        )
        time.sleep(CAMERA_RETRY_DELAY_SEC)
    return cap


def capture_single_frame(source: Union[int, str], attempts: int = CAMERA_WARMUP_READS) -> Optional["object"]:
    """Open a camera just long enough to grab one frame"""
    cap = open_camera(source)
    if not cap or not cap.isOpened():
        if cap:
            cap.release()
        return None
    try:
        for _ in range(attempts):
            ok, frame = cap.read()
            if ok:
                return frame
        return None
    finally:
        cap.release()