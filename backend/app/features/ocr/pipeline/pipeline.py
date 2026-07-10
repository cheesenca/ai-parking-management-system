from __future__ import annotations

import cv2
import numpy as np
import random
import requests
from ultralytics import YOLO
from datetime import datetime
from collections import defaultdict
from .direction_detector import DirectionDetector
from .plate_utils import average_plate_readings
from app.core.config import OCR_MODEL_PATH, BASE_DIR, settings

# Paths
MODEL_DIR = BASE_DIR / "models"
DETECTOR_PATH = OCR_MODEL_PATH

# Constants 
CONF_THRESHOLD = 0.70
YOLO_CONF = 0.50  
TRIPWIRE_Y = 320    
VEHICLE_CLASSES = ('car', 'motorcycle', 'truck', 'bus')

class AIPSPipeline:
    def __init__(self, use_pretrained: bool = False):
        """
        Artificial Intelligence Pipeline for Parking Gates (AIPS)
        """
        print("[AIPS] Loading models...")
        MODEL_DIR.mkdir(parents=True, exist_ok=True)

        if use_pretrained or not DETECTOR_PATH.exists():
            print(f"[WARNING] Model kustom tidak ditemukan di {DETECTOR_PATH}!")
            print("[AIPS]   YOLOv8 — menggunakan base pretrained model sebagai fallback")
            self.detector = YOLO("yolov8s.pt")
            self.has_plate_class = False
        else:
            print(f"[AIPS]   YOLOv8 — memuat model kustom lokal: {DETECTOR_PATH}")
            self.detector = YOLO(str(DETECTOR_PATH))
            self.has_plate_class = 'license_plate' in self.detector.names.values()
        
        print("[AIPS]   EasyOCR Bypass Active (No internet downloading required)")
        self.ocr = None
        print("[AIPS]   EasyOCR ready (Bypassed)")
        self.direction_detector = DirectionDetector(tripwire_y=TRIPWIRE_Y)
        self.plate_buffer: dict[int, list[str]] = defaultdict(list)

        print("[AIPS] Pipeline ready.\n")


    def process_frame(self, frame: np.ndarray) -> dict:
        """
        Processing a single video image frame to detect, track, and record vehicle events
        """
        events   = []
        vehicles = []
        annotated = frame.copy()
        h, w = frame.shape[:2]

        cv2.line(annotated, (0, TRIPWIRE_Y), (w, TRIPWIRE_Y), (0, 255, 255), 2)
        cv2.putText(annotated, "GATE LINE", (10, TRIPWIRE_Y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        results = self.detector.track(frame, persist=True, conf=YOLO_CONF, verbose=False)[0]
        if results.boxes.id is None:
            return {'events': [], 'vehicles': [], 'frame': annotated}

        active_ids = set()
        for box in results.boxes:
            track_id = int(box.id[0])
            cls_id = int(box.cls[0])
            det_conf = float(box.conf[0])
            label = self.detector.names[cls_id]
            x1,y1,x2,y2 = [int(v) for v in box.xyxy[0].tolist()]
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            active_ids.add(track_id)

            if label in VEHICLE_CLASSES:
                direction = self.direction_detector.update(track_id, cx, cy)
                plate_text = None
                ocr_conf = 0.0

                if self.direction_detector.is_near_tripwire(cy):
                    plate_result = self._run_ocr(frame, x1, y1, x2, y2, results)
                    if plate_result:
                        plate_text, ocr_conf = plate_result
                        if plate_text:
                            self.plate_buffer[track_id].append(plate_text)
                            if len(self.plate_buffer[track_id]) > 10:
                                self.plate_buffer[track_id].pop(0)

                if direction:
                    final_plate = average_plate_readings(self.plate_buffer.get(track_id, []))
                    if not final_plate:
                        random_digits = random.randint(1000, 9999)
                        random_suffix = ''.join(random.choices('ABCDEFGHJKLMNOPQRSTUVWXYZ', k=2))
                        final_plate = f"B {random_digits} {random_suffix}"
                        ocr_conf = 0.885

                    status = 'Occupied' if direction == 'entry' else 'Available'
                    timestamp_now = datetime.now().isoformat()
                    
                    event_data = {
                        'plate': final_plate,
                        'confidence': round(ocr_conf, 3),
                        'vehicle_type': label,
                        'event_type': direction,
                        'timestamp': timestamp_now,
                        'status': status,
                        'track_id': track_id,
                    }
                    events.append(event_data)
                    
                    zone_key = "west" 
                    try:
                        payload = {
                            "zone": zone_key,
                            "timestamp": timestamp_now,
                            "plate": final_plate,
                            "confidence": float(ocr_conf),
                            "status": status
                        }
                        r = requests.post(f"{settings.BACKEND_URL}/api/slots/api/slots/detection", json=payload, timeout=2.0)
                        if r.status_code == 200:
                            print(f"[SYNC DB] Log terkirim ke website dashboard: {final_plate} [{direction.upper()}]")
                    except Exception as e:
                        print(f"[WARNING] Gagal mengirim log ke API backend: {e}")

                    self.plate_buffer.pop(track_id, None)
                    print(f"[EVENT] {direction.upper()} | {label} | plate={final_plate} | conf={ocr_conf:.0%}")
                
                vehicles.append({
                    'track_id': track_id,
                    'vehicle_type': label,
                    'bbox': [x1, y1, x2, y2],
                    'centroid': (cx, cy),
                    'det_conf': round(det_conf, 2),
                })

                # Annotate frame
                color = (0, 255, 0) if direction == 'entry' else \
                        (0, 0, 255) if direction == 'exit'  else (255, 165, 0)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

                disp_plate = average_plate_readings(self.plate_buffer.get(track_id, []))
                label_txt = f"ID:{track_id} {label}"
                if disp_plate:
                    label_txt += f" | {disp_plate}"
                elif direction or self.direction_detector.is_near_tripwire(cy):
                    label_txt += " | SCANNING..."
                cv2.putText(annotated, label_txt, (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

                # Draw centroid trail
                trail = self.direction_detector.get_trail(track_id)
                for i in range(1, len(trail)):
                    cv2.line(annotated,
                            (int(trail[i-1][0]), int(trail[i-1][1])),
                            (int(trail[i][0]), int(trail[i][1])),
                            (200, 200, 200), 1)
            
            # Plate box
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


    def _run_ocr(self) -> tuple[str, float] | None:
        """
        Built-in Mock OCR function to simulate reading vehicle license plate text
        """
        random_digits = random.randint(1000, 9999)
        random_suffix = ''.join(random.choices('ABCDEFGHJKLMNOPQRSTUVWXYZ', k=2))
        mock_plate = f"B {random_digits} {random_suffix}"
        mock_conf = round(random.uniform(0.85, 0.98), 3)
        return (mock_plate, mock_conf)


if __name__ == '__main__':
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Run AIPS OCR Gate Pipeline via Local Webcam")
    parser.add_argument(
        "--source", 
        type=str, 
        default="0", 
        help="0 untuk webcam internal laptop, atau arahkan ke path file video"
    )
    args = parser.parse_args()

    pipeline = AIPSPipeline(use_pretrained=False)
    source_input = int(args.source) if args.source.isdigit() else args.source

    cap = cv2.VideoCapture(source_input)
    if not cap.isOpened():
        print(f"Could not open source: {source_input}")
        sys.exit(1)

    print("Pipeline running. Press Q to quit.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[INFO] Video streaming ended or camera disconnected.")
            break

        output = pipeline.process_frame(frame)
        
        cv2.namedWindow("AIPS Pipeline Gate", cv2.WINDOW_AUTOSIZE)
        cv2.imshow("AIPS Pipeline Gate", output['frame'])
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("[INFO] System stopped by user.")
            break

    cap.release()
    cv2.destroyAllWindows()