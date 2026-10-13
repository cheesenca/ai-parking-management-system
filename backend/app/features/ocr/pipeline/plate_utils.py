from __future__ import annotations

import cv2
import numpy as np


def preprocess_plate(crop: np.ndarray) -> np.ndarray:
    """
    Takes a raw crop of the license plate region and returns
    a cleaned-up grayscale image ready for EasyOCR.
    """
    # 1. Upscale — EasyOCR works much better on larger images
    scale = max(1, int(200 / crop.shape[0]))  # target ~200px height
    crop = cv2.resize(crop, None, fx=scale, fy=scale,
                      interpolation=cv2.INTER_CUBIC)

    # 2. Convert to grayscale
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # 3. Bilateral filter — removes noise while preserving plate character edges
    gray = cv2.bilateralFilter(gray, 11, 17, 17)

    # 4. Adaptive threshold — handles uneven lighting across the plate
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    return thresh


def clean_plate_text(raw: str) -> str:
    """
    Removes noise characters from OCR output.
    Indonesian plates are: [1-2 letters] [1-4 digits] [2-3 letters]
    e.g.  B 1234 ABC  |  D 5678 XY  |  F 999 ZZZ
    """
    import re
    # Keep only letters, digits, spaces
    cleaned = re.sub(r'[^A-Z0-9 ]', '', raw.upper().strip())
    # Collapse multiple spaces
    cleaned = re.sub(r' +', ' ', cleaned)
    return cleaned.strip()


def normalize_plate(raw: str) -> str:
    """
    Canonical form used for both DB lookups and format validation, since OCR
    spacing is unreliable: cleaned, uppercased, with all whitespace stripped.
    """
    import re
    return re.sub(r'\s+', '', clean_plate_text(raw))


def is_valid_plate_format(plate: str) -> bool:
    """
    Indonesian plate grammar: [1-2 letters][1-4 digits][2-3 letters],
    checked against the space-stripped normalized form.
    """
    import re
    return bool(re.fullmatch(r'[A-Z]{1,2}\d{1,4}[A-Z]{2,3}', plate))


def format_plate_display(plate_compact: str) -> str:
    """
    Reinserts spaces into a normalized plate for display/storage, matching
    the seed data convention (e.g. "B1234ABC" -> "B 1234 ABC"). Returns the
    input unchanged if it doesn't match the expected grammar.
    """
    import re
    m = re.fullmatch(r'([A-Z]{1,2})(\d{1,4})([A-Z]{2,3})', plate_compact)
    if not m:
        return plate_compact
    return f"{m.group(1)} {m.group(2)} {m.group(3)}"


def average_plate_readings(readings: list[str]) -> str:
    """
    When OCR is run on multiple frames of the same stopped vehicle,
    returns the most frequently occurring plate text — filters out
    single-frame OCR errors.
    """
    from collections import Counter
    if not readings:
        return ''
    counts = Counter(readings)
    return counts.most_common(1)[0][0]