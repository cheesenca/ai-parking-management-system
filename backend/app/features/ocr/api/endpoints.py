"""
AIPS Model — FastAPI Backend
Serves the AI pipeline via REST + WebSocket to the ParkWise dashboard.
"""

import asyncio
import base64
import sys
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

# Add pipeline directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))
from pipeline import AIPSPipeline

# ── App setup ─────────────────────────────────────────────────────────────────
router = APIRouter()
ws_router = APIRouter() # ADDED: Separate router for WebSockets

# ── Lazy-load pipeline (only once, on first connection) ───────────────────────
_pipeline: AIPSPipeline | None = None

def get_pipeline() -> AIPSPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = AIPSPipeline(use_pretrained=True)
    return _pipeline


# ── Health check (HTTP) ───────────────────────────────────────────────────────
@router.get("/api/health")
def health():
    return {"status": "ok", "model": "loaded" if _pipeline else "not_loaded"}


# ── Manual trigger endpoint (HTTP) ───────────────────────────────────────────
@router.post("/api/scan/simulate")
def simulate_scan():
    """
    Simulates a detection event. Useful for testing the dashboard
    integration before your camera/model is ready.
    """
    import random, string
    fake_plate = (
        random.choice(['B','D','F','E']) + ' ' +
        str(random.randint(1000, 9999)) + ' ' +
        ''.join(random.choices(string.ascii_uppercase, k=3))
    )
    return {
        "plate_detected": fake_plate,
        "confidence":     round(random.uniform(0.72, 0.99), 2),
        "vehicle_type":   random.choice(['car', 'motorcycle']),
        "event_type":     random.choice(['entry', 'exit']),
        "timestamp":      __import__('datetime').datetime.now().isoformat(),
        "status":         "detected",
    }


# ── WebSocket endpoint (WebSocket) ────────────────────────────────────────────
@ws_router.websocket("/ws/camera")  # CHANGED: Now uses ws_router
async def camera_feed(
    websocket: WebSocket,
    camera_index: int = Query(default=0),
    gate_type: str    = Query(default="entry"),   # override from dashboard
):
    """
    Connect from the ParkWise dashboard Parking Tracer page.
    Streams detection results in real time.
    """
    await websocket.accept()
    print(f"[WS] Client connected | camera={camera_index}")

    pipeline = get_pipeline()
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        await websocket.send_json({"error": f"Cannot open camera {camera_index}"})
        await websocket.close()
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                await websocket.send_json({"error": "Camera read failed"})
                break

            output = pipeline.process_frame(frame)

            # Encode annotated frame as base64 JPEG for browser display
            _, buf   = cv2.imencode('.jpg', output['frame'], [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_b64 = base64.b64encode(buf).decode('utf-8')

            # Build payload
            payload = {
                "frame":    frame_b64,
                "vehicles": output['vehicles'],
                "events":   output['events'],
            }

            # If there are crossing events, enrich with full detection data
            if output['events']:
                ev = output['events'][0]   # take first event per frame
                payload["detection"] = {
                    "plate_detected": ev['plate'],
                    "confidence":     ev['confidence'],
                    "vehicle_type":   ev['vehicle_type'],
                    "event_type":     ev['event_type'],
                    "timestamp":      ev['timestamp'],
                    "status":         ev['status'],
                }

            await websocket.send_json(payload)

            # ~15 FPS to the browser
            await asyncio.sleep(0.067)

    except WebSocketDisconnect:
        print("[WS] Client disconnected")
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        cap.release()
        print("[WS] Camera released")