import cv2

MAX_INDEX = 5          
SHOW_PREVIEW = True     
PREVIEW_SECONDS = 3   


def check_camera(index: int) -> dict:
    """
    Check if a camera at the given index can be opened and retrieve its properties
    """
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        return {"index": index, "opened": False}

    ok, frame = cap.read()
    if not ok:
        cap.release()
        return {"index": index, "opened": False}

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    result = {
        "index": index,
        "opened": True,
        "width": width,
        "height": height,
        "fps": round(fps, 2) if fps else None,
    }

    if SHOW_PREVIEW:
        print(f"Showing preview for camera index {index}. Press 'q' to proceed to the next camera")
        frame_count = 0
        max_frames = int(PREVIEW_SECONDS * (fps if fps and fps > 0 else 30))
        window_name = f"Preview - index {index}"
        
        while frame_count < max_frames:
            ok, frame = cap.read()
            if not ok:
                print(f"Lost frame connection to camera {index} during preview")
                break
                
            cv2.putText(
                frame,
                f"Camera index: {index} (press 'q' to skip)",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )
            cv2.imshow(window_name, frame)
            frame_count += 1
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
                
        try:
            cv2.destroyWindow(window_name)
        except cv2.error:
            pass

    cap.release()
    return result


def main():
    print(f"Checking camera indices 0 to {MAX_INDEX - 1}...\n")
    available = []

    for i in range(MAX_INDEX):
        print(f"[Index {i}] Attempting to open camera...")
        info = check_camera(i)
        if info["opened"]:
            print(
                f"Index {i} is available | "
                f"Resolution: {info['width']}x{info['height']} | "
                f"FPS: {info['fps']}"
            )
            available.append(info)
        else:
            print(f"Index {i} could not be opened / no camera found.")
        print()

    print("=" * 50)
    if available:
        print("Summary of available cameras:")
        for info in available:
            print(
                f"  - Index {info['index']}: "
                f"{info['width']}x{info['height']} @ {info['fps']} FPS"
            )
    else:
        print("No cameras detected on this system")
    print("=" * 50)

    if SHOW_PREVIEW:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
