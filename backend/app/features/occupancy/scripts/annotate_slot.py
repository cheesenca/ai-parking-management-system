from __future__ import annotations

import argparse
import json
import string
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


from app.core.config import PARKING_MAP_JSON


def _slot_label(idx: int) -> str:
    return f"{string.ascii_uppercase[idx % 26]}{idx // 26 + 1}"


def _load_ref(args: argparse.Namespace) -> np.ndarray:
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


def run_annotator(
    reference: np.ndarray,
    zone: str = "west",
    camera_id: str = "CAM_WEST_01",
    save_path: Path = PARKING_MAP_JSON,
) -> Optional[dict]:
    slots = []
    wip = []
    mouse_pos = [(0, 0)]
    grid_cols = [5]

    def on_mouse(event, x, y, _):
        mouse_pos[0] = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            wip.append([x, y])
        elif event == cv2.EVENT_RBUTTONDOWN:
            if len(wip) >= 3:
                slots.append({
                    "id": _slot_label(len(slots)),
                    "category": "Employee",
                    "polygon": [pt[:] for pt in wip],
                })
            wip.clear()
        elif event == cv2.EVENT_MBUTTONDOWN:
            wip.clear()


    def render() -> np.ndarray:
        out = reference.copy()
        for s in slots:
            pts = np.array(s["polygon"], np.int32)
            cv2.polylines(out, [pts], True, (0, 220, 0), 2)
            M = cv2.moments(pts)
            if M["m00"]:
                cv2.putText(out, s["id"], (int(M["m10"]/M["m00"])-10, int(M["m01"]/M["m00"])+5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1)
        if len(wip) >= 2:
            cv2.polylines(out, [np.array(wip, np.int32)], False, (0,165,255), 2)
        if wip:
            cv2.line(out, tuple(wip[-1]), mouse_pos[0], (255,255,0), 1)
            for v in wip:
                cv2.circle(out, tuple(v), 4, (0,165,255), -1)
        h = out.shape[0]
        cv2.putText(out, f"Slots: {len(slots)}, L=vertex R=close G=grid U=undo S=save Q=quit", (8, h-12), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (200,200,200), 1)
        return out

    def auto_grid():
        slots.clear()
        fh, fw = reference.shape[:2]
        cols = max(1, grid_cols[0])
        rows = max(1, fh // 60)
        sw, sh = fw // cols, fh // rows
        for r in range(rows):
            for c in range(cols):
                x, y = c * sw, r * sh
                slots.append({
                    "id": _slot_label(len(slots)),
                    "category": "Employee",
                    "polygon": [[x,y],[x+sw-4,y],[x+sw-4,y+sh-4],[x,y+sh-4]]
                })

    win = "Annotate Slots, S: save | Q: quit"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, min(1280, reference.shape[1]), min(720, reference.shape[0]))
    cv2.setMouseCallback(win, on_mouse)

    result = None
    while True:
        cv2.imshow(win, render())
        key = cv2.waitKey(30) & 0xFF
        if key == ord("s"):
            pm = {"zone": zone, "camera_id": camera_id, "slots": slots}
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w") as f:
                json.dump(pm, f, indent=2)
            print(f"\n✓ Saved {len(slots)} slot(s) → {save_path}")
            result = pm
            break
        elif key == ord("q"):
            break
        elif key == ord("u") and slots:
            slots.pop()
        elif key == ord("c"):
            slots.clear()
        elif key == ord("g"):
            auto_grid()
        elif key == ord("+"):
            grid_cols[0] = min(20, grid_cols[0] + 1)
        elif key == ord("-"):
            grid_cols[0] = max(1, grid_cols[0] - 1)

    cv2.destroyWindow(win)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Stage 1 — Annotate parking-slot polygons",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--image", type=Path)
    src.add_argument("--webcam", type=int, default=None)
    src.add_argument("--video", type=Path)
    parser.add_argument("--zone", default="west")
    parser.add_argument("--camera", default="CAM_WEST_01", dest="camera_id")
    parser.add_argument("--output", type=Path, default=PARKING_MAP_JSON)
    parser.add_argument("--calibrate-perspective", action="store_true", help="After annotation, also run perspective calibration")
    args = parser.parse_args()

    if all(x is None for x in [args.image, args.webcam, args.video]):
        print("[INFO] No source given — using blank 640×480 canvas.")
        ref = np.full((480, 640, 3), 40, dtype=np.uint8)
    else:
        ref = _load_ref(args)

    run_annotator(ref, zone=args.zone, camera_id=args.camera_id, save_path=args.output)

    if args.calibrate_perspective:
        from pipeline.perspective_correction import interactive_calibrate
        print("\n[perspective] Click 4 boundary corners: TL→TR→BR→BL")
        interactive_calibrate(ref)


if __name__ == "__main__":
    main()