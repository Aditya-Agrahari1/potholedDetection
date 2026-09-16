# Build Prompt for Google Antigravity


---

Build a backend REST API for a **Pothole Detection & Change-Tracking System**. This API will be consumed by a separate mobile/web app (built by another team), so it must be well-documented, predictable, and easy to integrate against.

## Tech Stack
- **Framework**: Python, FastAPI
- **Database**: SQLite, accessed via SQLAlchemy ORM (structure the code so swapping to PostgreSQL later only requires changing the connection string — don't hardcode SQLite-specific SQL)
- **AI**: Google Gemini API (use the `google-genai` Python SDK) for both pothole detection and image comparison/report generation
- **File storage**: Store uploaded photos locally in a `/uploads` directory for now; structure the storage access behind a simple interface/function so it can be swapped for cloud storage (e.g. S3) later
- **PDF generation**: Use a Python PDF library (e.g. `reportlab` or `fpdf2`) to generate report PDFs
- **Docs**: Rely on FastAPI's built-in automatic OpenAPI/Swagger docs (`/docs`) — make sure every endpoint has clear request/response models (Pydantic) with descriptions, since another team will integrate against this without talking to me directly

## Core Concept

A user submits a photo of a road pothole along with **latitude, longitude (manually entered, not device GPS), and a timestamp**.

- If this is the **first photo at this location**, run pothole detection on it, generate a report, and store it.
- If a **previous photo already exists near this location** (within a configurable radius, e.g. 15 meters, using the Haversine formula — no PostGIS needed), pass **both the old and new photo** to Gemini together, and have it determine whether the pothole has **worsened, improved, persisted (no meaningful change), or resolved**. Generate a comparison report reflecting that.

## Database Schema

```
locations
  id            INTEGER PRIMARY KEY
  latitude      FLOAT NOT NULL
  longitude     FLOAT NOT NULL
  created_at    DATETIME

reports
  id                INTEGER PRIMARY KEY
  location_id       INTEGER FK -> locations.id
  photo_path        TEXT NOT NULL
  timestamp         DATETIME NOT NULL
  detection_data    JSON          -- raw structured output from Gemini
  status            TEXT          -- 'new' | 'worsened' | 'improved' | 'persistent' | 'resolved'
  compared_to_id    INTEGER FK -> reports.id, NULLABLE
  pdf_path          TEXT
  created_at        DATETIME
```

## Matching Logic

When a new report is submitted:
1. Query all existing `locations` and compute distance via the Haversine formula against the submitted lat/long.
2. If the nearest existing location is within the radius threshold (make this a configurable constant, default 15 meters), treat it as the same location — use its `location_id` and fetch its most recent `report` as the "previous" photo for comparison.
3. If no location is within the threshold, create a new `location` row.

## Gemini Integration

### Detection prompt (new location, single photo)
Send the image to Gemini and require **strict JSON output only** (no markdown fences, no prose) matching:
```json
{
  "potholes_detected": true,
  "count": 2,
  "detections": [
    {
      "bbox": [0.1, 0.2, 0.4, 0.5],
      "severity": "low | medium | high",
      "estimated_area_percent": 12.5,
      "description": "short description"
    }
  ],
  "overall_severity": "low | medium | high"
}
```

### Comparison prompt (existing location, two photos)
Send both images (label which is earlier/later by timestamp) and require strict JSON output matching:
```json
{
  "status": "worsened | improved | persistent | resolved",
  "area_change_percent": 23.5,
  "severity_change": "increased | decreased | same",
  "reasoning": "1-2 sentence explanation",
  "report_summary": "3-4 sentence paragraph suitable for inclusion in a PDF report"
}
```

**Important**: Write a robust JSON-parsing helper that strips ```json code fences if present and handles malformed responses gracefully (retry once on parse failure, then return a clear 502 error if it still fails — don't let the whole request crash silently).

## API Endpoints

### `POST /api/v1/reports`
Multipart form data: `photo` (file), `latitude` (float), `longitude` (float), `timestamp` (ISO8601 string)

Runs the full flow (matching → detection or comparison → PDF generation → save) and returns:
```json
{
  "report_id": 42,
  "location_id": 7,
  "status": "new",
  "compared_to_report_id": null,
  "detection": { ... },
  "pdf_url": "/reports/42/pdf",
  "created_at": "2026-09-16T10:30:00Z"
}
```

### `GET /api/v1/reports/{report_id}`
Returns full report details.

### `GET /api/v1/reports/{report_id}/pdf`
Streams/downloads the generated PDF.

### `GET /api/v1/locations/{location_id}/reports`
Returns all reports for a location, ordered oldest → newest (the full history/timeline for that pothole).

### `GET /api/v1/reports`
List/filter reports. Query params: `status`, `from_date`, `to_date`, pagination (`limit`, `offset`).

## PDF Report Contents
Each generated PDF should include:
- Location (lat/long) and timestamp
- The submitted photo(s) embedded in the PDF
- Detection/comparison results (severity, area, status)
- The `report_summary` text from Gemini
- A simple header/footer identifying it as an automated pothole report

## Processing Mode
Keep this **synchronous** for now — the API call does detection/comparison/PDF generation inline and returns the final result in one response. Don't build async/polling/webhooks; keep it simple for the team to integrate.

## Environment & Config
- Load the Gemini API key from an environment variable (`GEMINI_API_KEY`), never hardcode it.
- Make the matching radius threshold and Gemini model name configurable via environment variables or a config file, with sensible defaults.
- Include a `.env.example` file listing required environment variables.

## Deliverables
1. Working FastAPI project with the endpoints above
2. SQLAlchemy models matching the schema
3. Gemini integration module (detection + comparison, with JSON parsing/retry logic)
4. PDF generation module
5. Auto-generated Swagger docs accessible at `/docs`
6. A `README.md` explaining how to run the project locally, required environment variables, and a sample `curl` request for the main endpoint
7. Basic error handling: invalid image uploads, missing fields, Gemini API failures, and malformed lat/long values should all return clear 4xx/5xx responses with helpful error messages — not stack traces

Please scaffold the project structure first, show me the plan, then implement it file by file so I can review as you go.