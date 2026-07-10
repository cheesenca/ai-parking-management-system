from __future__ import annotations
import sys
import cv2
import json
import string
import argparse
import numpy as np
from pathlib import Path
from typing import Optional
from app.core.config import PARKING_MAP_JSON, OCCUPANCY_MODEL_PATH

# Bootstrap sys.path
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


def _slot_label(idx: int) -> str:
    """Sequential Excel-style label (A1, B1, ..., A2, ...)."""
    return f"{string.ascii_uppercase[idx % 26]}{idx // 26 + 1}"


def _load_ref(args: argparse.Namespace) -> np.ndarray:
    """Grab a single reference frame from image / webcam / video."""
    if args.image:
        f = cv2.imread(str(args.image))
        if f is None:
            print(f"[ERROR] Cannot read: {args.image}")
            sys.exit(1)
        return f
    src = int(args.webcam) if args.webcam is not None else str(args.video)
    cap = cv2.VideoCapture(src)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        print("Cannot read frame from source")
        sys.exit(1)
    return frame


def _nms_boxes(boxes: list[dict], iou_thresh: float = 0.35) -> list[dict]:
    """Simple NMS so overlapping detections don't create duplicate slots."""
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: b["conf"], reverse=True)
    keep: list[dict] = []

    def iou(a, b):
        xa1, ya1 = max(a["x1"], b["x1"]), max(a["y1"], b["y1"])
        xa2, ya2 = min(a["x2"], b["x2"]), min(a["y2"], b["y2"])
        inter = max(0, xa2 - xa1) * max(0, ya2 - ya1)
        area_a = (a["x2"] - a["x1"]) * (a["y2"] - a["y1"])
        area_b = (b["x2"] - b["x1"]) * (b["y2"] - b["y1"])
        union = area_a + area_b - inter
        return inter / union if union else 0

    for b in boxes:
        if all(iou(b, k) < iou_thresh for k in keep):
            keep.append(b)
    return keep


def auto_detect_slots(
    reference: np.ndarray,
    model_path: Path,
    conf: float = 0.25,
    category: str = "Employee",
) -> list[dict]:
    """
    Runs the YOLO parking-spot model (e.g. pklot.pt) once on a reference frame
    and converts every detected bounding box directly into a slot polygon.
    No manual clicking is required - the AI provides the coordinates.
    """
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    results = model(reference, conf=conf, verbose=False)

    raw: list[dict] = []
    for box in (results[0].boxes or []):
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
        raw.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "conf": float(box.conf[0])})

    raw = _nms_boxes(raw)

    # Sort top-to-bottom, left-to-right so IDs read naturally like a grid
    raw.sort(key=lambda b: (round((b["y1"] + b["y2"]) / 2 / 40), (b["x1"] + b["x2"]) / 2))

    slots = []
    for i, b in enumerate(raw):
        x1, y1, x2, y2 = int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"])
        slots.append({
            "id": _slot_label(i),
            "category": category,
            "polygon": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
            "confidence": round(b["conf"], 3),
        })
    return slots


def review_and_edit(reference: np.ndarray, slots: list[dict]) -> list[dict]:
    """
    Optional fallback: shows the AI's auto-detected boxes so a human can
    delete false positives (D + click) or nudge a corner if needed -
    still far faster than annotating every slot from scratch.
    Keys: S = save & exit review, Q = discard box under cursor, U = undo delete.
    """
    removed_stack: list[dict] = []

    def on_mouse(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN:
            for s in list(slots):
                xs = [p[0] for p in s["polygon"]]
                ys = [p[1] for p in s["polygon"]]
                if min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys):
                    slots.remove(s)
                    removed_stack.append(s)
                    break

    win = "Review AI-detected slots  |  click=remove  U=undo  S=save  Q=quit-without-saving"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, min(1280, reference.shape[1]), min(720, reference.shape[0]))
    cv2.setMouseCallback(win, on_mouse)

    while True:
        out = reference.copy()
        for s in slots:
            pts = np.array(s["polygon"], np.int32)
            cv2.polylines(out, [pts], True, (0, 220, 0), 2)
            M = cv2.moments(pts)
            if M["m00"]:
                cx, cy = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                cv2.putText(out, s["id"], (cx - 10, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        h = out.shape[0]
        cv2.putText(out, f"AI-detected slots: {len(slots)}  (click a box to drop a false positive)",
                    (8, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (200, 200, 200), 1)
        cv2.imshow(win, out)
        key = cv2.waitKey(30) & 0xFF
        if key == ord("s"):
            break
        if key == ord("u") and removed_stack:
            slots.append(removed_stack.pop())
        if key == ord("q"):
            break
    cv2.destroyWindow(win)
    return slots


def main():
    parser = argparse.ArgumentParser(
        description="Auto-detect parking-slot polygons with AI (no manual corner-clicking)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", type=Path)
    src.add_argument("--webcam", type=int, default=None)
    src.add_argument("--video", type=Path)
    parser.add_argument("--zone", default="west")
    parser.add_argument("--camera", default="CAM_WEST_01", dest="camera_id")
    parser.add_argument("--category", default="Employee", help="Default category assigned to auto-detected slots")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--model", type=Path, default=OCCUPANCY_MODEL_PATH,
                         help="YOLO weights trained to find parking spots, e.g. models/pklot.pt")
    parser.add_argument("--output", type=Path, default=PARKING_MAP_JSON)
    parser.add_argument("--no-review", action="store_true",
                         help="Skip the review window and save AI output as-is")
    args = parser.parse_args()

    ref = _load_ref(args)
    h, w = ref.shape[:2]

    print(f"[AI] Detecting slots with {args.model} (conf={args.conf}) ...")
    slots = auto_detect_slots(ref, args.model, conf=args.conf, category=args.category)
    print(f"[AI] Found {len(slots)} candidate slot(s).")

    if not args.no_review:
        slots = review_and_edit(ref, slots)

    payload = {
        "zone": args.zone,
        "camera_id": args.camera_id,
        "frame": {"w": w, "h": h},
        "slots": [{k: v for k, v in s.items() if k != "confidence"} for s in slots],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved {len(slots)} AI-detected slot(s) → {args.output}")


if __name__ == "__main__":
    main()