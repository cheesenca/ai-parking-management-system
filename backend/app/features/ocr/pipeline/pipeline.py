"""
AIPS Model — Main Inference Pipeline
Combines YOLOv8 tracking + EasyOCR + direction detection into one
callable function that the FastAPI server uses.

Run standalone for testing:
    python pipeline/pipeline.py
"""

from __future__ import annotations

import cv2
import numpy as np
import easyocr
from ultralytics import YOLO
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from plate_utils import preprocess_plate, clean_plate_text, average_plate_readings
from direction_detector import DirectionDetector

# ── Paths ─────────────────────────────────────────────────────────────────────
MODEL_DIR = Path(__file__).parent.parent / "models"
DETECTOR_PATH = MODEL_DIR / "parkwise_detector.pt"

# ── Constants ─────────────────────────────────────────────────────────────────
CONF_THRESHOLD  = 0.70   # minimum OCR confidence for auto-grant
YOLO_CONF       = 0.50   # minimum YOLO detection confidence
TRIPWIRE_Y      = 320    # ← SET THIS per your camera. Run test_camera.py first.
VEHICLE_CLASSES = ('car', 'motorcycle', 'truck', 'bus')


class AIPSPipeline:
    """
    Main pipeline class. Instantiate once and call process_frame() per frame.

    If your trained model (parkwise_detector.pt) is not ready yet,
    set use_pretrained=True to use the base YOLOv8 model which can
    detect vehicles but not license plates specifically.
    """

    def __init__(self, use_pretrained: bool = False):
        print("[AIPS] Loading models...")

        # Load YOLO model
        if use_pretrained or not DETECTOR_PATH.exists():
            print("[AIPS]   YOLOv8 — using base pretrained model (no custom training yet)")
            print("[AIPS]   Train your model first, then set use_pretrained=False")
            self.detector = YOLO("yolov8s.pt")
            self.has_plate_class = False
        else:
            print(f"[AIPS]   YOLOv8 — loading {DETECTOR_PATH}")
            self.detector = YOLO(str(DETECTOR_PATH))
            self.has_plate_class = 'license_plate' in self.detector.names.values()

        # Load EasyOCR (downloads language models on first run ~500MB)
        print("[AIPS]   EasyOCR — loading (first run downloads language models)...")
        self.ocr = easyocr.Reader(['en', 'id'], gpu=False)
        print("[AIPS]   EasyOCR ready")

        # Direction detector
        self.direction_detector = DirectionDetector(tripwire_y=TRIPWIRE_Y)

        # Per-track plate reading buffer (for multi-frame averaging)
        self.plate_buffer: dict[int, list[str]] = defaultdict(list)

        print("[AIPS] Pipeline ready.\n")

    def process_frame(self, frame: np.ndarray) -> dict:
        """
        Process one camera frame.

        Returns:
        {
            'events':   list of detection events (one per vehicle crossing),
            'vehicles': list of currently tracked vehicles in frame,
            'frame':    annotated frame (numpy array),
        }

        Each event in 'events':
        {
            'plate':        str,
            'confidence':   float (0.0–1.0),
            'vehicle_type': str,
            'event_type':   'entry' | 'exit',
            'timestamp':    str (ISO format),
            'status':       'detected' | 'low_confidence' | 'no_plate',
        }
        """
        events   = []
        vehicles = []
        annotated = frame.copy()

        h, w = frame.shape[:2]

        # ── Draw tripwire ──────────────────────────────────────────────────────
        cv2.line(annotated, (0, TRIPWIRE_Y), (w, TRIPWIRE_Y), (0, 255, 255), 2)
        cv2.putText(annotated, "GATE LINE", (10, TRIPWIRE_Y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        # ── Run YOLO with tracking ─────────────────────────────────────────────
        results = self.detector.track(frame, persist=True, conf=YOLO_CONF,
                                      verbose=False)[0]

        if results.boxes.id is None:
            return {'events': [], 'vehicles': [], 'frame': annotated}

        active_ids = set()

        for box in results.boxes:
            track_id  = int(box.id[0])
            cls_id    = int(box.cls[0])
            det_conf  = float(box.conf[0])
            label     = self.detector.names[cls_id]
            x1,y1,x2,y2 = [int(v) for v in box.xyxy[0].tolist()]
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            active_ids.add(track_id)

            # ── Vehicle tracks ────────────────────────────────────────────────
            if label in VEHICLE_CLASSES:
                # Check direction crossing
                direction = self.direction_detector.update(track_id, cx, cy)

                # Run OCR when vehicle is near the tripwire
                plate_text  = None
                ocr_conf    = 0.0

                if self.direction_detector.is_near_tripwire(cy):
                    plate_result = self._run_ocr(frame, x1, y1, x2, y2, results)
                    if plate_result:
                        plate_text, ocr_conf = plate_result
                        if plate_text:
                            self.plate_buffer[track_id].append(plate_text)
                            # Keep buffer at max 10 readings
                            if len(self.plate_buffer[track_id]) > 10:
                                self.plate_buffer[track_id].pop(0)

                # Fire event when vehicle crosses the line
                if direction:
                    final_plate = average_plate_readings(self.plate_buffer.get(track_id, []))
                    status = (
                        'detected'        if final_plate and ocr_conf >= CONF_THRESHOLD else
                        'low_confidence'  if final_plate else
                        'no_plate'
                    )
                    events.append({
                        'plate':        final_plate or '',
                        'confidence':   round(ocr_conf, 3),
                        'vehicle_type': label,
                        'event_type':   direction,
                        'timestamp':    datetime.now().isoformat(),
                        'status':       status,
                        'track_id':     track_id,
                    })
                    # Clear buffer after event fires
                    self.plate_buffer.pop(track_id, None)
                    print(f"[EVENT] {direction.upper()} | {label} | "
                          f"plate={final_plate or '?'} | conf={ocr_conf:.0%} | {status}")

                vehicles.append({
                    'track_id':     track_id,
                    'vehicle_type': label,
                    'bbox':         [x1, y1, x2, y2],
                    'centroid':     (cx, cy),
                    'det_conf':     round(det_conf, 2),
                })

                # ── Annotate frame ────────────────────────────────────────────
                color = (0, 255, 0) if direction == 'entry' else \
                        (0, 0, 255) if direction == 'exit'  else (255, 165, 0)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

                disp_plate = average_plate_readings(self.plate_buffer.get(track_id, []))
                label_txt  = f"ID:{track_id} {label}"
                if disp_plate:
                    label_txt += f" | {disp_plate}"
                cv2.putText(annotated, label_txt, (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

                # Draw centroid trail
                trail = self.direction_detector.get_trail(track_id)
                for i in range(1, len(trail)):
                    cv2.line(annotated,
                             (int(trail[i-1][0]), int(trail[i-1][1])),
                             (int(trail[i][0]),   int(trail[i][1])),
                             (200, 200, 200), 1)

            # ── Plate box (if model has plate class) ──────────────────────────
            elif label == 'license_plate':
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 255, 0), 2)

        # Cleanup stale tracks
        self.direction_detector.cleanup_lost_tracks(active_ids)

        # HUD
        cv2.putText(annotated, f"Tracking: {len(active_ids)} objects",
                    (w - 220, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(annotated, datetime.now().strftime("%H:%M:%S"),
                    (w - 100, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150, 150, 150), 1)

        return {'events': events, 'vehicles': vehicles, 'frame': annotated}

    def _run_ocr(self, frame, vx1, vy1, vx2, vy2, results) -> tuple[str, float] | None:
        """
        Finds the plate crop and runs EasyOCR on it.
        Prefers a dedicated license_plate detection box if available,
        falls back to the bottom 30% of the vehicle bounding box.
        """
        plate_crop = None

        # Try to find a plate box from YOLO
        if self.has_plate_class:
            for box in results.boxes:
                if self.detector.names[int(box.cls[0])] == 'license_plate':
                    px1,py1,px2,py2 = [int(v) for v in box.xyxy[0].tolist()]
                    plate_crop = frame[py1:py2, px1:px2]
                    break

        # Fallback: crop bottom 30% of vehicle bbox (where plates usually are)
        if plate_crop is None or plate_crop.size == 0:
            plate_y_start = vy1 + int((vy2 - vy1) * 0.65)
            plate_crop = frame[plate_y_start:vy2, vx1:vx2]

        if plate_crop is None or plate_crop.size == 0:
            return None

        # Preprocess and OCR
        processed = preprocess_plate(plate_crop)
        ocr_out   = self.ocr.readtext(processed)

        if not ocr_out:
            return None

        best       = max(ocr_out, key=lambda x: x[2])
        plate_text = clean_plate_text(best[1])
        confidence = best[2]

        return (plate_text, confidence) if plate_text else None


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys

    pipeline = AIPSPipeline(use_pretrained=False)

    source = sys.argv[1] if len(sys.argv) > 1 else 0
    # source can be: 0 (webcam), 1 (second cam), or 'path/to/video.mp4'
    try:
        source = int(source)
    except ValueError:
        pass

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Could not open source: {source}")
        sys.exit(1)

    print("Pipeline running. Press Q to quit.")
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        output = pipeline.process_frame(frame)

        cv2.imshow("AIPS Pipeline", output['frame'])
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
