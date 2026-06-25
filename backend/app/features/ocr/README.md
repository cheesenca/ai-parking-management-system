# AIPS Model — AI Parking System
## Vehicle Detection + License Plate OCR + Direction Detection

---

## Folder Structure

```
aips-model/
├── datasets/               ← put your Roboflow dataset ZIP here
├── models/                 ← put your trained .pt model here after training
├── pipeline/
│   ├── pipeline.py         ← main inference engine (start here)
│   ├── direction_detector.py
│   ├── plate_utils.py
│   └── test_camera.py
├── api/
│   └── main.py             ← FastAPI server (connects to ParkWise dashboard)
├── notebooks/
│   └── train_detector.ipynb ← Google Colab training notebook
├── tests/
├── requirements.txt
└── test_env.py
```

---

## Step-by-Step Development Guide

### PHASE 1 — Environment Setup (Do this first)

**Step 1: Open this folder in VS Code**
```
File → Open Folder → select aips-model/
```

**Step 2: Open the terminal (Ctrl + ~) and create virtual environment**
```bash
python -m venv venv
```

**Step 3: Activate it**
```bash
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```
You should see `(venv)` at the start of your terminal.

**Step 4: Install all dependencies**
```bash
pip install -r requirements.txt
```
This takes 5–10 minutes. EasyOCR alone is ~500MB.

**Step 5: Verify environment**
```bash
python test_env.py
```
Expected output: `✅  All good — environment ready.`

**Step 6: Test your camera**
```bash
python pipeline/test_camera.py
```
A window should open showing your webcam feed. Press Q to close.

---

### PHASE 2 — Dataset Collection on Roboflow

1. Go to **roboflow.com** and create a free account
2. Create a new project → Object Detection
3. Search **Roboflow Universe** for these and add to your project:
   - "Indonesian license plate" → aim for 500+ images
   - "vehicle detection" → aim for 300+ per class
4. Your annotation classes must be exactly:
   ```
   car
   motorcycle
   truck
   bus
   license_plate
   ```
5. Split: 80% train / 10% valid / 10% test
6. Apply augmentations: Brightness, Blur, Rotation (±15°)
7. Export → **YOLOv8 format** → Download ZIP
8. Put the ZIP in the `datasets/` folder

---

### PHASE 3 — Train the Model (Google Colab)

1. Upload the dataset ZIP to **Google Drive** (any folder)
2. Open `notebooks/train_detector.ipynb` in **Google Colab**
   (drag and drop the .ipynb file onto colab.research.google.com)
3. Set runtime to GPU: **Runtime → Change runtime type → T4 GPU**
4. Run all cells in order
5. Training takes ~1–2 hours
6. Target accuracy: **mAP50 ≥ 0.80**
7. Download `parkwise_detector.pt` from your Drive
8. Put it in `aips-model/models/`

---

### PHASE 4 — Run the Pipeline

**Before your trained model is ready** (uses base YOLOv8, no plate detection):
```bash
python pipeline/pipeline.py
```

**After putting parkwise_detector.pt in models/:**
Edit `pipeline/pipeline.py` line 1, change:
```python
pipeline = AIPSPipeline(use_pretrained=True)
```
to:
```python
pipeline = AIPSPipeline(use_pretrained=False)
```
Then run again.

**Important: Set your tripwire Y coordinate**
Open `pipeline/pipeline.py` and find:
```python
TRIPWIRE_Y = 320
```
Run `test_camera.py` first, note the frame height (usually 480),
then set TRIPWIRE_Y to roughly the middle of your gate in the frame.

---

### PHASE 5 — Connect to the ParkWise Dashboard

**Start the API server:**
```bash
uvicorn api.main:app --reload --port 8000
```

**Test it's running:**
Open http://localhost:8000/api/health in your browser.
Should return: `{"status": "ok"}`

**Connect from the dashboard:**
In your `parkwise` website folder, open:
`app/dashboard/tracker/page.tsx`

Find the `simulateScan` function and replace it with:
```typescript
useEffect(() => {
  const ws = new WebSocket('ws://localhost:8000/ws/camera?camera_index=0');

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.detection) {
      const det = data.detection;
      setPlate(det.plate_detected);
      setConfidence(det.confidence);
      setStatus(det.confidence >= 0.70 ? 'granted' : 'denied');
      setLatestIn(new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }));
      // det.vehicle_type, det.event_type also available
    }
  };

  ws.onerror = () => console.error('AI WebSocket error');
  return () => ws.close();
}, [selectedZone]);
```

---

## Demo Credentials (ParkWise website)

| Username | Password     | Role     |
|----------|--------------|----------|
| admin    | admin123     | Admin    |
| westsec  | security123  | Security |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `pip install` fails on torch | Install PyTorch manually from pytorch.org first |
| EasyOCR download hangs | It downloads ~500MB on first run, just wait |
| Camera not found (index 0) | Try `python pipeline/test_camera.py 1` |
| YOLO tracks not persisting | Make sure you're calling `model.track(..., persist=True)` |
| Low OCR accuracy | Increase lighting, ensure plate is at least 80px wide in frame |
| Dashboard not receiving events | Check CORS — API must be running on port 8000 |
