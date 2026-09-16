# Pothole Detection & Change-Tracking System API

A backend REST API built with **FastAPI**, **SQLAlchemy**, **Google Gemini AI**, and **ReportLab**. Designed for civil infrastructure monitoring, this service enables mobile and web applications to log road surface defect photos with geographic coordinates, automatically track defect progression over time, and generate official civil engineering inspection PDF reports.

---

## Architecture & Core Concepts

```
                  ┌─────────────────────────────────────────┐
                  │          Client (Mobile / Web)          │
                  └────────────────────┬────────────────────┘
                                       │ POST photo, lat, lon, timestamp
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │         FastAPI Application             │
                  │   (/api/v1/reports, /api/v1/locations)  │
                  └────────────┬───────────────┬────────────┘
                               │               │
        Proximity Search       ▼               ▼   Image Storage
    (Haversine Formula ≤ 15m)  ┌───────────────┐   ┌─────────────────┐
    ──────────────────────────►│ Location      │   │ StorageService  │
                               │ Matcher       │   │ (Local/Cloud S3)│
                               └───────┬───────┘   └─────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
       [No Match > 15m]                               [Match ≤ 15m]
     Initial Detection                              Sequential Comparison
   (Single-Image Analysis)                         (Two-Image Change Tracking)
                │                                             │
                └──────────────────────┬──────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │   Google Gemini 2.5 Flash   │
                        │    (google-genai SDK)       │
                        └──────────────┬──────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │    ReportLab PDF Engine     │
                        │ (Inspection Report with Img)│
                        └──────────────┬──────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │   SQLAlchemy ORM (SQLite/PG)│
                        └─────────────────────────────┘
```

1. **Geolocation Matching (Haversine Formula)**:
   - When a user submits an inspection photo with latitude and longitude, the system computes the great-circle distance against all previously recorded locations using the Haversine formula.
   - If a monitored location exists within a configurable radius (default **15 meters**), the system links the report to that location and loads its previous inspection photo.
   - If no location is within the threshold, a new location record is created.

2. **Multimodal AI with Gemini (`google-genai` SDK)**:
   - **New Location (Single Photo)**: Gemini detects potholes, returns bounding boxes (`bbox`), defect counts, severity (`low`, `medium`, `high`), estimated road surface area percent, and an executive summary.
   - **Existing Location (Two Photos)**: Both the baseline and latest photos are sent together with timestamps. Gemini analyzes defect progression: `worsened`, `improved`, `persistent` (no change), or `resolved`, along with estimated area change percent and reasoning.
   - **Robust JSON Parsing & 1-Attempt Retry**: Automatically strips markdown fences (````json ... ````), extracts JSON payloads, and retries once if formatting is malformed. Returns clear HTTP 502 error responses if the upstream AI fails.
   - **Offline / Mock Mode**: Supports `GEMINI_API_KEY=mock` for testing and local development without consuming live AI quota.

3. **Engineering PDF Generation**:
   - Compiles an official civil inspection PDF report embedding the photos (single photo or side-by-side Before/After comparison), status badges, GPS coordinates, severity metrics, and the AI executive summary.

4. **Database Agnostic**:
   - Uses SQLAlchemy declarative ORM. Switching from the default SQLite database to PostgreSQL only requires updating `DATABASE_URL` in `.env`.

---

## Tech Stack

- **Language**: Python 3.10+
- **API Framework**: FastAPI 0.112+ (ASGI, Pydantic v2)
- **Database ORM**: SQLAlchemy 1.4+ / 2.0+ (SQLite default, PostgreSQL ready)
- **AI Model**: Google Gemini 2.5 Flash via official `google-genai` SDK
- **PDF Generation**: ReportLab 5.0+ with Pillow
- **Interactive Documentation**: Swagger UI (`/docs`) and ReDoc (`/redoc`)

---

## Project Structure

```
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, CORS, error handlers, router registration
│   ├── config.py                # Environment configuration (Pydantic Settings)
│   ├── database.py              # SQLAlchemy engine, session maker, get_db dependency
│   ├── models/
│   │   ├── __init__.py
│   │   ├── location.py          # Location SQLAlchemy model
│   │   └── report.py            # Report SQLAlchemy model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── location.py          # Pydantic schemas for locations and timelines
│   │   ├── report.py            # Pydantic schemas for detection, comparison, reports
│   │   └── common.py            # Standard ErrorResponse schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gemini.py            # Gemini integration, retry logic, fence stripping, mock mode
│   │   ├── storage.py           # StorageService interface & LocalStorageService
│   │   ├── matcher.py           # Haversine distance calculator and location finder
│   │   └── pdf.py               # ReportLab PDF report generator
│   └── routers/
│       ├── __init__.py
│       ├── reports.py           # POST/GET reports, PDF download, photo stream
│       └── locations.py         # GET locations and location timeline
├── tests/
│   ├── conftest.py              # Test fixtures (SQLite in-memory DB, sample images)
│   ├── test_matcher.py          # Haversine distance and threshold tests
│   ├── test_gemini.py           # JSON parsing, code fence removal, mock tests
│   ├── test_pdf.py              # PDF generator unit tests
│   └── test_api.py              # Complete integration test suite (all endpoints)
├── uploads/
│   ├── photos/                  # Stored road defect photographs
│   └── reports/                 # Stored PDF inspection reports
├── .env.example                 # Example environment configuration
├── requirements.txt             # Locked project dependencies
└── README.md
```

---

## Quickstart Guide

### 1. Prerequisites
- Python 3.10 or higher
- `pip` package manager

### 2. Installation
Clone or navigate to the project directory and install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
copy .env.example .env   # Windows
# or
cp .env.example .env     # Linux / macOS
```

Configure your `.env` settings:
```ini
# Gemini API Key (Get from https://aistudio.google.com/)
# Set to 'mock' for offline testing / local development
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Database URL
DATABASE_URL=sqlite:///./potholes.db

# Location Matching Radius in Meters (default: 15.0m)
MATCHING_RADIUS_METERS=15.0

# Storage Directory
STORAGE_DIR=./uploads
```

### 4. Run Server
Start the development server with Uvicorn:
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Base**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **Alternative ReDoc**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/health`

---

## Switching from SQLite to PostgreSQL

The codebase is built entirely using standard SQLAlchemy ORM abstractions without vendor-specific SQL. To switch to PostgreSQL:

1. Install psycopg2:
   ```bash
   pip install psycopg2-binary
   ```
2. Update `DATABASE_URL` in your `.env`:
   ```ini
   DATABASE_URL=postgresql+psycopg2://username:password@localhost:5432/potholes_db
   ```
3. Restart the server. SQLAlchemy will automatically create tables via `init_db()`.

---

## API Endpoints Reference

### 1. Submit Inspection Report
`POST /api/v1/reports` (Multipart Form Data)

**Parameters:**
- `photo`: Image file (`image/jpeg`, `image/png`, or `image/webp`)
- `latitude`: Float between `-90.0` and `90.0`
- `longitude`: Float between `-180.0` and `180.0`
- `timestamp`: ISO 8601 string (e.g. `2026-09-16T10:30:00Z`)

**Response (201 Created):**
```json
{
  "report_id": 1,
  "location_id": 1,
  "status": "new",
  "compared_to_report_id": null,
  "detection": {
    "potholes_detected": true,
    "count": 1,
    "detections": [
      {
        "bbox": [0.25, 0.3, 0.65, 0.7],
        "severity": "medium",
        "estimated_area_percent": 15.0,
        "description": "Noticeable asphalt erosion and crater defect"
      }
    ],
    "overall_severity": "medium",
    "report_summary": "Automated visual inspection identified a medium-severity pothole..."
  },
  "pdf_url": "/api/v1/reports/1/pdf",
  "created_at": "2026-09-16T10:30:00"
}
```

---

### 2. Retrieve Report Details
`GET /api/v1/reports/{report_id}`

**Response (200 OK):**
```json
{
  "id": 1,
  "location_id": 1,
  "latitude": 37.7749,
  "longitude": -122.4194,
  "photo_path": "uploads/photos/abc123.jpg",
  "photo_url": "/api/v1/reports/1/photo",
  "timestamp": "2026-09-16T10:30:00",
  "detection_data": { ... },
  "status": "new",
  "compared_to_id": null,
  "pdf_path": "uploads/reports/report_1.pdf",
  "pdf_url": "/api/v1/reports/1/pdf",
  "created_at": "2026-09-16T10:30:00"
}
```

---

### 3. Download Official PDF Report
`GET /api/v1/reports/{report_id}/pdf`

Returns `application/pdf` stream with embedded photos, metadata, severity badges, and executive summary.

---

### 4. Location Report History / Timeline
`GET /api/v1/locations/{location_id}/reports`

Returns all reports recorded at this geographic location ordered **oldest to newest** to track defect lifecycle.

**Response (200 OK):**
```json
{
  "location_id": 1,
  "latitude": 37.7749,
  "longitude": -122.4194,
  "created_at": "2026-09-01T10:00:00",
  "reports": [
    {
      "id": 1,
      "location_id": 1,
      "status": "new",
      "timestamp": "2026-09-01T10:00:00",
      ...
    },
    {
      "id": 2,
      "location_id": 1,
      "status": "worsened",
      "timestamp": "2026-09-16T10:00:00",
      ...
    }
  ]
}
```

---

### 5. List and Filter Reports
`GET /api/v1/reports`

**Query Parameters:**
- `status`: Filter by status (`new`, `worsened`, `improved`, `persistent`, `resolved`)
- `from_date`: ISO 8601 date string filter
- `to_date`: ISO 8601 date string filter
- `limit`: Page size (default `20`, max `100`)
- `offset`: Offset (default `0`)

---

## Sample `curl` Commands

### Submit Initial Report (New Pothole)
```bash
curl -X POST "http://localhost:8000/api/v1/reports" \
  -F "photo=@/path/to/road_photo.jpg;type=image/jpeg" \
  -F "latitude=37.7749" \
  -F "longitude=-122.4194" \
  -F "timestamp=2026-09-16T10:00:00Z"
```

### Submit Follow-Up Report at Same Location (Triggers AI Comparison)
```bash
curl -X POST "http://localhost:8000/api/v1/reports" \
  -F "photo=@/path/to/followup_photo.jpg;type=image/jpeg" \
  -F "latitude=37.77495" \
  -F "longitude=-122.4194" \
  -F "timestamp=2026-09-20T14:30:00Z"
```

### Download Generated PDF Report
```bash
curl -O -J "http://localhost:8000/api/v1/reports/1/pdf"
```

### Fetch Location Timeline
```bash
curl "http://localhost:8000/api/v1/locations/1/reports"
```

### Filter Reports by Status
```bash
curl "http://localhost:8000/api/v1/reports?status=worsened&limit=10"
```

## Deploying to Render

This project is pre-configured for **Render** deployment with both [Procfile](file:///c:/Users/agrah/OneDrive/Desktop/New%20folder%20%284%29/Procfile) and [render.yaml](file:///c:/Users/agrah/OneDrive/Desktop/New%20folder%20%284%29/render.yaml) blueprints.

### Crucial Things to Know for Render:

1. **Database Persistence (Use Render PostgreSQL)**:
   - On Render's free tier, the local filesystem is **ephemeral** (wiped when the service sleeps or redeploys). If you use SQLite, your data resets on redeploy.
   - **Solution**: Create a **Free PostgreSQL Database** on Render:
     1. Click **New +** -> **PostgreSQL**.
     2. Copy the **Internal Database URL** (e.g. `postgres://user:pass@dpg-.../db`).
     3. Add it as an environment variable: `DATABASE_URL=<your_postgres_url>`.
     4. *Note: Our code automatically rewrites Render's `postgres://` to `postgresql://` so modern SQLAlchemy 1.4/2.0 never crashes!*

2. **Photo & PDF Storage**:
   - **Render Free Tier**: Photos and PDFs in `./uploads` are accessible as long as the service is active, but reset on redeploy/spin-down.
   - **For Long-Term Persistence**:
     - Either attach a **Render Persistent Disk** mounted at `/uploads` (e.g., set `STORAGE_DIR=/var/data/uploads` in Render settings).
     - Or swap `StorageService` for a free S3-compatible cloud bucket (e.g. AWS S3, Cloudinary, or Supabase Storage).

3. **CORS for Your Team's Frontend**:
   - The API comes with open CORS (`allow_origins=["*"]`), allowing your mobile app, React, Vue, Flutter, or Next.js team to call the Render API from `localhost` or any production domain without CORS errors.

4. **Render Environment Variables**:
   In the Render dashboard under **Environment**:
   - `GEMINI_API_KEY`: Your Google AI Studio API key
   - `DATABASE_URL`: Your PostgreSQL connection string (or leave unset for default SQLite)
   - `GEMINI_MODEL`: `gemini-2.5-flash` (optional)
   - `MATCHING_RADIUS_METERS`: `15.0` (optional)

5. **Render Service Settings**:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`

---

## Running the Automated Test Suite

The test suite covers location proximity matching, Gemini JSON extraction and retry logic, PDF rendering, and all API endpoints:

```bash
pytest -v
```

Expected output:
```
======================== 26 passed in 1.57s ========================
```
