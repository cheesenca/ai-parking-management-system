import sys
import cv2
import time
import argparse
from pathlib import Path

# Bootstrap sys.path to find project modules regardless of execution CWD
def _bootstrap(f: str) -> None:
    p = Path(f).resolve()
    feat = proj = None
    for parent in p.parents:
        if parent.name in ["parking-slot-occupancy", "parking_slot_occupancy"] and feat is None:
            feat = parent
        if (parent / "requirements.txt").exists() and (parent / "app").is_dir() and proj is None:
            proj = parent
        if feat and proj:
            break
    for root in filter(None, [str(proj), str(feat)]):
        if root not in sys.path:
            sys.path.insert(0, root)
_bootstrap(__file__)

from app.core.config import PARKING_MAP_JSON
from app.features.parking_slot_occupancy.services.occupancy import (
    analyze_occupancy, draw_occupancy, load_parking_map, get_category_summary
)
from app.features.parking_slot_occupancy.api.endpoints import push_slot_update


def run_pipeline(source: str):
    print(f"[INFO] Loading parking configuration from {PARKING_MAP_JSON}")
    parking_map = load_parking_map(PARKING_MAP_JSON)
    zone_name = parking_map.get("zone", "west")
    
    video_source = int(source) if source.isdigit() else source
    cap = cv2.VideoCapture(video_source)
    
    if not cap.isOpened():
        print(f"Failed to open video source: {source}")
        return

    print(f"Starting AI Parking System in Zone: {zone_name.upper()}...")
    
    last_update_time = time.time()
    update_interval = 2.0 

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Video has finished or camera disconnected")
            break

        slot_status = analyze_occupancy(frame, parking_map)
        output_frame = draw_occupancy(frame, parking_map, slot_status)
        current_time = time.time()
        if current_time - last_update_time > update_interval:
            category_summary = get_category_summary(parking_map, slot_status)
            success = push_slot_update(zone_name, slot_status, category_summary, parking_map)
            
            if success:
                print(f"Send Update | Zona: {zone_name}")
            else:
                print("Failed to send data to Backend API (Make sure uvicorn server is running)")
                
            last_update_time = current_time

        cv2.imshow("AIPS - YOLOv8 Live Occupancy", output_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("System stopped by user")
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AI Parking System with YOLOv8")
    parser.add_argument(
        "--source", 
        type=str, 
        default="0", 
        help="Type video file path (e.g., video.mp4) or '0' for the built-in webcam"
    )
    args = parser.parse_args()
    
    run_pipeline(args.source)