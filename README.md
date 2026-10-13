# AI Parking Management System

An enhanced parking management web application that helps admins monitor real-time slot occupancy, recognize license plates automatically, and forecast parking demand using AI — reducing manual monitoring effort across parking zones.

## **Overview**
AI Parking Management System leverages computer vision and machine learning to detect vehicle occupancy from camera feeds in real time. The platform also implements an OCR-based license-plate recognition pipeline to automatically log vehicle entries and exits, and a demand forecasting module that predicts future occupancy trends. Admins manage zones, members, and review flagged plate scans through a dedicated dashboard.

## **Contributor**
|          Name             |      StudentID      |                Task                  |
|---------------------------|---------------------|--------------------------------------|
| Kresnandityo Mahesa Suryo |     001202300068    | License Plate Recognition & Frontend |
| Kalvin Bernard Kabbi      |     012202300039    |   Forecasting Predictive Analytics   |
| Kevin Juan Carlos         |     001202300054    |   Parking Slot Occupancy & Backend   |

## **Features**
- License Plate Recognition
- Parking Slot Occupancy
- Forecasting Predictive Analytics
- Member Dashboard
- Slot Calibration

## **Folder Directory**
```
ai-parking-management-system/
├── backend/
│   ├── .venv/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py
│   │   │   └── router.py
│   │   ├── common/
│   │   │   ├── middleware/
│   │   │   │   ├── __init__.py
│   │   │   │   └── cors.py
│   │   │   ├── __init__.py
│   │   │   ├── exceptions_handler.py
│   │   │   └── exceptions.py
│   │   ├── core/
│   │   │   ├── settings/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py
│   │   │   │   ├── forecast.py
│   │   │   │   ├── occupancy.py
│   │   │   │   └── ocr.py
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── path.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   └── session.py
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   │   ├── __init__.py
│   │   │   │   └── endpoints.py
│   │   │   ├── forecast/
│   │   │   │   ├── api/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── endpoints.py
│   │   │   │   ├── services/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── model.py
│   │   │   │   │   └── retrain.py
│   │   │   │   ├── models.py
│   │   │   │   └── report.py
│   │   │   ├── members/
│   │   │   │   ├── __init__.py
│   │   │   │   └── endpoints.py
│   │   │   ├── occupancy/
│   │   │   │   ├── api/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── endpoints.py
│   │   │   │   ├── schemas/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── slots.py
│   │   │   │   └── services/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── calibration.py
│   │   │   │       ├── camera.py
│   │   │   │       ├── detection.py
│   │   │   │       ├── layout.py
│   │   │   │       ├── persistence.py
│   │   │   │       └── vision.py
│   │   │   └── ocr/
│   │   │       ├── api/
│   │   │       │   ├── __init__.py
│   │   │       │   └── endpoints.py
│   │   │       ├── pipeline/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── direction_detector.py
│   │   │       │   ├── pipeline.py
│   │   │       │   └── plate_utils.py
│   │   │       ├── schemas/
│   │   │       │   ├── __init__.py
│   │   │       │   └── detection.py
│   │   │       └── services/
│   │   │           ├── __init__.py
│   │   │           ├── plate_lookup.py
│   │   │           ├── review_queue.py
│   │   │           └── session_tracking.py
│   │   ├── __init__.py
│   │   └── main.py
│   ├── data/
│   │   └── occupancy/
│   │       └── calibration/
│   │           ├── east_reference.jpg
│   │           └── east.json
│   ├── ml/
│   │   ├── forecast/
│   │   │   ├── datasets/
│   │   │   │   ├── ParkingRecord_Preprocessed.c...
│   │   │   │   └── ParkingRecord_Updated.csv
│   │   │   ├── django_legacy/
│   │   │   ├── preprocessing/
│   │   │   │   ├── eda_complete.py
│   │   │   │   ├── eda_location.py
│   │   │   │   ├── eda.py
│   │   │   │   └── preprocessing.py
│   │   │   └── training/
│   │   │       └── experiment_outputs/
│   │   │           ├── daily_forecast_arima.csv
│   │   │           ├── daily_forecast_location_comp...csv
│   │   │           ├── daily_forecast_location_comp...csv
│   │   │           ├── daily_forecast_location_final_...csv
│   │   │           ├── daily_forecast_location_realis...csv
│   │   │           ├── daily_forecast_location.csv
│   │   │           ├── daily_forecast_prophet.csv
│   │   │           ├── daily_forecast_summary_reali...csv
│   │   │           ├── daily_forecast_summary.csv
│   │   │           ├── daily_forecast.csv
│   │   │           ├── monthly_forecast_location_v...csv
│   │   │           ├── monthly_forecast.csv
│   │   │           ├── weekly_forecast_location_fin...csv
│   │   │           ├── weekly_forecast_location_rea...csv
│   │   │           ├── weekly_forecast_location_var...csv
│   │   │           ├── weekly_forecast.csv
│   │   │           ├── daily_forecast_compare_fixed.py
│   │   │           ├── daily_forecast_compare.py
│   │   │           ├── daily_forecast_location_realisti...py
│   │   │           ├── daily_forecast_realistic.py
│   │   │           ├── daily_forecast_summary.py
│   │   │           ├── daily_forecast.py
│   │   │           ├── import_forecast_to_db.py
│   │   │           ├── monthly_forecast.py
│   │   │           ├── weekly_forecast_location_reali...py
│   │   │           ├── weekly_forecast_location.py
│   │   │           ├── weekly_forecast_realistic.py
│   │   │           ├── weekly_forecast_var.py
│   │   │           └── weekly_forecast.py
│   │   ├── occupancy/
│   │   │   ├── datasets/
│   │   │   │    └── custom/
│   │   │   │        └── dataset/
│   │   │   │            ├── train/
│   │   │   │            │   ├── empty/
│   │   │   │            │   └── occupied/
│   │   │   │            └── val/
│   │   │   │                ├── empty/
│   │   │   │                └── occupied/
│   │   │   └── notebooks/
│   │   │       └── parking_slot_occupancy.ipynb
│   │   └── ocr/
│   │       └── notebooks/
│   │           └── train_detector.ipynb
│   ├── models/
│   │   ├── joblib/
│   │   │   ├── arima.joblib
│   │   │   └── prophet.joblib
│   │   └── pytorch/
│   │       ├── parkwise_detector.pt
│   │       ├── pklot.pt
│   │       ├── yolov8s.pt
│   │       ├── craft_mlt_25k.pth
│   │       └── latin_g2.pth
│   ├── scripts/
│   │   ├── backfill_historical_data.py
│   │   ├── camera_index.py
│   │   ├── check_occupancy_data.py
│   │   ├── forecast_occupancy_integration.py
│   │   ├── forecast_seed.py
│   │   ├── generate_dummy_members.py
│   │   ├── occupancy_history_seed.py
│   │   ├── ocr_libraries.py
│   │   ├── retrain_prophet.py
│   │   └── test_plate_ocr.py
│   ├── seeds/
│   │   └── aips_db.sql
│   └── tests/
│       ├── integration/
│       │   └── __init__.py
│       └── unit/
│           ├── __init__.py
│           └── test_health.py
│
├── frontend/
│   ├── .next/
│   ├── node_modules/
│   ├── public/
│   ├── src/
│   │   ├── app/
│   │   │   ├── auth/
│   │   │   │   └── forgot-password/
│   │   │   │       └── page.tsx
│   │   │   ├── dashboard/
│   │   │   │   ├── analytics/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── calibration/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── list/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── members/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── pending-review/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── tracker/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── users/
│   │   │   │   │   └── page.tsx
│   │   │   │   └── layout.tsx
│   │   │   ├── favicon.ico
│   │   │   ├── globals.css
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   ├── components/
│   │   │   ├── CategoryStats.tsx
│   │   │   ├── ConnPill.tsx
│   │   │   ├── ForecastReportPrint.tsx
│   │   │   ├── LiveDetection.tsx
│   │   │   ├── ManualApprovalModal.tsx
│   │   │   ├── ModalPortal.tsx
│   │   │   ├── SetCapacityModal.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── SlotDetectionCamera.tsx
│   │   │   └── SlotMap.tsx
│   │   ├── context/
│   │   │   └── AuthContext.tsx
│   │   ├── hooks/
│   │   │   ├── useLiveDetection.ts
│   │   │   ├── useSlotDetection.ts
│   │   │   └── useSlotOccupancy.ts
│   │   ├── lib/
│   │   │   ├── backendApi.ts
│   │   │   └── slotData.ts
│   │   └── types/
│   │       └── index.ts
│   ├── .dockerignore
│   ├── .env
│   ├── .env.example
│   ├── .gitignore
│   ├── AGENTS.md
│   ├── CLAUDE.md
│   ├── Dockerfile
│   ├── eslint.config.mjs
│   ├── next-env.d.ts
│   ├── next.config.ts
│   ├── package-lock.json
│   ├── package.json
│   ├── postcss.config.mjs
│   ├── README.md
│   └── tsconfig.json
├── docker-compose.yaml
└── README.md
```

## **Setup Instruction**

### **Prerequisites**

Install the following before starting:

|  Tool                                              | Recommended Version |
|----------------------------------------------------|---------------------|
| Python                                             |        3.11+        |
| Node.js                                            |         20+         |
| npm                                                |         10+         |
| PostgreSQL (or Docker)                             |         15+         |
| Docker & Docker Compose (optional but recommended) |       latest        |
| Git                                                |       latest        |

### **1. Clone the Repository**

```bash
git clone <repository-url>
cd ai-parking-management-system
```

### **2. Backend Setup**

#### 2.1 Create and activate a virtual environment

```bash
cd backend
python -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate
```

#### 2.2 Install dependencies

```bash
pip install -r requirements.txt
```

#### 2.3 Configure environment variables

Copy the example env file and fill in the required values:

```bash
cp .env.example .env
```

Key variables typically needed (adjust to match `app/core/settings/`):

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/aips_db

# Auth
SECRET_KEY=change-me
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Forecast settings (app/core/settings/forecast.py)
FORECAST_MODEL_PATH=models/joblib/

# Occupancy / camera settings (app/core/settings/occupancy.py)
CAMERA_SOURCE=0

# OCR settings (app/core/settings/ocr.py)
OCR_MODEL_PATH=models/pytorch/
```

#### 2.4 Run the backend server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` (docs at `http://localhost:8000/docs`).

### **3. Database Setup**

#### 3.1 Create the database

```bash
# Using psql
createdb aips_db
```

#### 3.2 Load the seed schema

```bash
psql -U <user> -d aips_db -f backend/seeds/aips_db.sql
```

#### 3.3 Seed sample/demo data

Run the seed scripts from `backend/scripts/`:

```bash
cd backend
python scripts/generate_dummy_members.py
python scripts/occupancy_history_seed.py
python scripts/forecast_seed.py
python scripts/backfill_historical_data.py
```

#### 3.4 Verify data integrity

```bash
python scripts/check_occupancy_data.py
```

### **4. ML Models Setup**

The `backend/models/` directory holds the trained artifacts required at runtime:

```
models/
├── joblib/
│   ├── arima.joblib        # time-series forecast model
│   └── prophet.joblib      # time-series forecast model
└── pytorch/
    ├── parkwise_detector.pt  # custom slot occupancy detector
    ├── pklot.pt               # PKLot-trained detector
    ├── yolov8s.pt             # base YOLOv8 detector
    ├── craft_mlt_25k.pth      # CRAFT text detection (OCR)
    └── latin_g2.pth           # EasyOCR recognition weights
```

**If these files are not included in the repo** (e.g. excluded via `.gitignore` due to size), download them from the project's model storage (see internal docs/release assets) and place them in the matching subfolder above.

#### 4.1 Retraining models (optional)

```bash
cd backend
python scripts/retrain_prophet.py
```

Notebooks for training/evaluation live under:
- `ml/forecast/training/experiment_outputs/`
- `ml/occupancy/notebooks/parking_slot_occupancy.ipynb`
- `ml/occupancy/ocr/notebooks/train_detector.ipynb`

#### 4.2 Camera calibration

Occupancy detection uses per-camera calibration data stored at:

```
backend/app/data/occupancy/calibration/
├── east_reference.jpg
└── east.json
```

Use the calibration endpoints (`app/features/occupancy/services/calibration.py`) or the frontend's **Calibration** dashboard page to generate new calibration files for additional camera angles.

#### 4.3 License plate OCR test

```bash
cd backend
python scripts/test_plate_ocr.py
```

### **5. Frontend Setup**

#### 5.1 Install dependencies

```bash
cd frontend
npm install
```

#### 5.2 Configure environment variables

```bash
cp .env.example .env
```

Typical values:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

#### 5.3 Run the development server

```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`.

#### 5.4 Build for production

```bash
npm run build
npm start
```

### **6. Running with Docker**

A `docker-compose.yaml` is provided at the repo root to spin up both services (and the database, if configured) together.

```bash
docker compose up --build
```

This will typically start:
- `backend` — FastAPI service (port 8000)
- `frontend` — Next.js service (port 3000)
- `db` — PostgreSQL (if defined in `docker-compose.yaml`)

To stop:

```bash
docker compose down
```

To rebuild after dependency changes:

```bash
docker compose up --build --force-recreate
```

### **7. Verifying the Setup**

1. **Backend health check:**
   ```bash
   curl http://localhost:8000/health
   ```
2. **Run backend tests:**
   ```bash
   cd backend
   pytest tests/
   ```
3. **Frontend:** open `http://localhost:3000` and confirm the login/dashboard loads.
4. **Live detection:** navigate to the **Tracker** or **List** dashboard page and confirm camera feed / slot map renders (requires a connected camera or test video source).
5. **Forecast report:** open the **Analytics** dashboard page and confirm forecast charts load (requires seeded forecast data and model files).