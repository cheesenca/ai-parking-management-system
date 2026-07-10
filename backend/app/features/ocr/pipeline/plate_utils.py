from __future__ import annotations
import cv2
import numpy as np


def preprocess_plate(crop: np.ndarray) -> np.ndarray:
    """
    Takes a raw crop of the license plate region and returns a cleaned-up grayscale image ready for EasyOCR
    """
    # Upscale 
    scale = max(1, int(200 / crop.shape[0]))  
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    # Convert to grayscale
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Bilateral filter 
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    # Adaptive threshold 
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    return thresh


def clean_plate_text(raw: str) -> str:
    """
    Removes noise characters from OCR output
    """
    import re
    
    # Keep only letters, digits, spaces
    cleaned = re.sub(r'[^A-Z0-9 ]', '', raw.upper().strip())
    # Collapse multiple spaces
    cleaned = re.sub(r' +', ' ', cleaned)
    return cleaned.strip()


def average_plate_readings(readings: list[str]) -> str:
    """
    When OCR is run on multiple frames of the same stopped vehicle,
    returns the most frequently occurring plate text — filters out
    single-frame OCR errors
    """
    from collections import Counter

    if not readings:
        return ''
    counts = Counter(readings)
    return counts.most_common(1)[0][0]
