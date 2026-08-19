"""
Usage: python -m scripts.test_plate_ocr <image_path>

Standalone detector+OCR test — runs a single static image through the same
YOLO + EasyOCR pipeline the live camera feed uses, without needing a camera
or a physical test plate. Point it at any photo of a car (a downloaded
picture, a screenshot, a phone photo) to see exactly what YOLO detects and
what EasyOCR reads off the plate crop, with the raw confidence score.
"""
import sys
from pathlib import Path

import cv2

PIPELINE_DIR = Path(__file__).resolve().parent.parent / "app" / "features" / "ocr" / "pipeline"
sys.path.insert(0, str(PIPELINE_DIR))

from pipeline import AIPSPipeline  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.test_plate_ocr <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Could not read image: {image_path}")
        sys.exit(1)

    pipeline = AIPSPipeline(use_pretrained=False)
    print(f"has_plate_class = {pipeline.has_plate_class}  (True = detector has a dedicated "
          f"license_plate class for tight crops; False = falls back to bottom-30%-of-vehicle-bbox)")

    results = pipeline.detector(frame, conf=0.25, verbose=False)[0]
    print(f"\nYOLO detections ({len(results.boxes)}):")
    for box in results.boxes:
        label = pipeline.detector.names[int(box.cls[0])]
        conf = float(box.conf[0])
        print(f"  {label:15s} conf={conf:.2f}")

    found_vehicle = False
    for box in results.boxes:
        label = pipeline.detector.names[int(box.cls[0])]
        if label not in ('car', 'motorcycle', 'truck', 'bus'):
            continue
        found_vehicle = True
        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
        plate_result = pipeline._run_ocr(frame, x1, y1, x2, y2, results)
        if plate_result:
            plate_text, conf = plate_result
            print(f"\n[{label}] plate='{plate_text}' confidence={conf:.1%}")
        else:
            print(f"\n[{label}] no readable plate text found in the crop")

    if not found_vehicle:
        print("\nNo vehicle (car/motorcycle/truck/bus) detected in this image at all — "
              "OCR never runs. Try a closer/clearer photo of a vehicle.")

    out_path = "ocr_test_output.jpg"
    cv2.imwrite(out_path, results.plot())
    print(f"\nAnnotated detections saved to {out_path}")


if __name__ == "__main__":
    main()
