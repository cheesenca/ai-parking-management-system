"""
AIPS Model — Environment Test
Run this first after installing dependencies to verify everything is working.
"""

print("=" * 50)
print("AIPS Model — Environment Check")
print("=" * 50)

errors = []

# YOLOv8
try:
    from ultralytics import YOLO
    print("✓ Ultralytics (YOLOv8)")
except ImportError as e:
    print("✗ Ultralytics:", e)
    errors.append("ultralytics")

# EasyOCR
try:
    import easyocr
    print("✓ EasyOCR")
except ImportError as e:
    print("✗ EasyOCR:", e)
    errors.append("easyocr")

# OpenCV
try:
    import cv2
    print(f"✓ OpenCV {cv2.__version__}")
except ImportError as e:
    print("✗ OpenCV:", e)
    errors.append("opencv-python")

# PyTorch
try:
    import torch
    print(f"✓ PyTorch {torch.__version__}")
    print(f"  └─ GPU available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  └─ GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("  └─ Running on CPU (fine for development)")
except ImportError as e:
    print("✗ PyTorch:", e)
    errors.append("torch")

# TorchVision
try:
    import torchvision
    print(f"✓ TorchVision {torchvision.__version__}")
except ImportError as e:
    print("✗ TorchVision:", e)
    errors.append("torchvision")

# FastAPI
try:
    import fastapi
    print(f"✓ FastAPI {fastapi.__version__}")
except ImportError as e:
    print("✗ FastAPI:", e)
    errors.append("fastapi")

# Others
for pkg, name in [
    ("numpy",    "NumPy"),
    ("shapely",  "Shapely"),
    ("PIL",      "Pillow"),
    ("requests", "Requests"),
]:
    try:
        mod = __import__(pkg)
        ver = getattr(mod, "__version__", "ok")
        print(f"✓ {name} {ver}")
    except ImportError as e:
        print(f"✗ {name}: {e}")
        errors.append(pkg)

print("=" * 50)
if not errors:
    print("✅  All good — environment ready.")
    print("    Next step: run  python pipeline/test_camera.py")
else:
    print(f"❌  Fix these packages:  pip install {' '.join(errors)}")
print("=" * 50)
