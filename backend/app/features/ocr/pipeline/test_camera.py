import cv2
import sys

def test_camera(index: int = 0):
    print(f"Opening camera index {index}...")
    cap = cv2.VideoCapture(index)

    if not cap.isOpened():
        print(f"✗ Could not open camera {index}.")
        print("  Try a different index: python pipeline/test_camera.py 1")
        sys.exit(1)

    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = cap.get(cv2.CAP_PROP_FPS)
    print(f"✓ Camera opened — {width}x{height} @ {fps:.0f}fps")
    print("  Press Q to quit.")

    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            print("✗ Failed to read frame.")
            break

        frame_count += 1
        cv2.putText(frame, f"AIPS Camera Test  |  Frame {frame_count}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"{width}x{height} @ {fps:.0f}fps",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        cv2.putText(frame, "Press Q to quit",
                    (10, height - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        cv2.imshow("AIPS Camera Test", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"✓ Camera test complete. Captured {frame_count} frames.")


if __name__ == "__main__":
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    test_camera(idx)