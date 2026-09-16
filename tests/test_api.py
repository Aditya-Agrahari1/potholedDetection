import io
import pytest
from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    """Test /health returns healthy status."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"


def test_post_report_initial_baseline(client: TestClient, sample_image_bytes: bytes):
    """POST /api/v1/reports for a new location creates location and initial report."""
    files = {
        "photo": ("pothole.jpg", io.BytesIO(sample_image_bytes), "image/jpeg"),
    }
    data = {
        "latitude": 37.774900,
        "longitude": -122.419400,
        "timestamp": "2026-09-16T10:00:00Z",
    }

    res = client.post("/api/v1/reports", data=data, files=files)
    assert res.status_code == 201
    body = res.json()

    assert body["report_id"] is not None
    assert body["location_id"] is not None
    assert body["status"] == "new"
    assert body["compared_to_report_id"] is None
    assert "pdf_url" in body
    assert body["pdf_url"] == f"/api/v1/reports/{body['report_id']}/pdf"


def test_post_report_repeat_location_triggers_comparison(client: TestClient, sample_image_bytes: bytes):
    """POST /api/v1/reports within 15m radius matches existing location and runs comparison."""
    # 1. Submit initial report at baseline coordinates
    files1 = {
        "photo": ("pothole1.jpg", io.BytesIO(sample_image_bytes), "image/jpeg"),
    }
    data1 = {
        "latitude": 37.774900,
        "longitude": -122.419400,
        "timestamp": "2026-09-01T10:00:00Z",
    }
    res1 = client.post("/api/v1/reports", data=data1, files=files1)
    assert res1.status_code == 201
    rep1 = res1.json()

    # 2. Submit second report ~6 meters away (within 15m radius)
    files2 = {
        "photo": ("pothole2.jpg", io.BytesIO(sample_image_bytes), "image/jpeg"),
    }
    data2 = {
        "latitude": 37.774950,
        "longitude": -122.419400,
        "timestamp": "2026-09-16T10:00:00Z",
    }
    res2 = client.post("/api/v1/reports", data=data2, files=files2)
    assert res2.status_code == 201
    rep2 = res2.json()

    # Must match same location ID and compare to report 1
    assert rep2["location_id"] == rep1["location_id"]
    assert rep2["compared_to_report_id"] == rep1["report_id"]
    assert rep2["status"] in ("worsened", "improved", "persistent", "resolved")


def test_post_report_distant_location_creates_new_location(client: TestClient, sample_image_bytes: bytes):
    """POST /api/v1/reports at a distant location creates a distinct location."""
    # 1. Report at SF
    res1 = client.post(
        "/api/v1/reports",
        data={"latitude": 37.7749, "longitude": -122.4194, "timestamp": "2026-09-16T10:00:00Z"},
        files={"photo": ("p1.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")},
    )
    assert res1.status_code == 201
    loc1_id = res1.json()["location_id"]

    # 2. Report in Oakland (>10km away)
    res2 = client.post(
        "/api/v1/reports",
        data={"latitude": 37.8044, "longitude": -122.2712, "timestamp": "2026-09-16T10:00:00Z"},
        files={"photo": ("p2.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")},
    )
    assert res2.status_code == 201
    loc2_id = res2.json()["location_id"]

    assert loc1_id != loc2_id


def test_get_report_details(client: TestClient, sample_image_bytes: bytes):
    """GET /api/v1/reports/{id} returns full report details."""
    post_res = client.post(
        "/api/v1/reports",
        data={"latitude": 37.7749, "longitude": -122.4194, "timestamp": "2026-09-16T10:00:00Z"},
        files={"photo": ("p.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")},
    )
    report_id = post_res.json()["report_id"]

    res = client.get(f"/api/v1/reports/{report_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == report_id
    assert data["latitude"] == pytest.approx(37.7749)
    assert data["longitude"] == pytest.approx(-122.4194)
    assert "detection_data" in data


def test_get_report_not_found(client: TestClient):
    """GET /api/v1/reports/{id} returns 404 for invalid ID."""
    res = client.get("/api/v1/reports/99999")
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "REPORT_NOT_FOUND"


def test_download_report_pdf(client: TestClient, sample_image_bytes: bytes):
    """GET /api/v1/reports/{id}/pdf returns application/pdf content."""
    post_res = client.post(
        "/api/v1/reports",
        data={"latitude": 37.7749, "longitude": -122.4194, "timestamp": "2026-09-16T10:00:00Z"},
        files={"photo": ("p.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")},
    )
    report_id = post_res.json()["report_id"]

    pdf_res = client.get(f"/api/v1/reports/{report_id}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF")


def test_location_timeline_endpoint(client: TestClient, sample_image_bytes: bytes):
    """GET /api/v1/locations/{location_id}/reports returns timeline ordered oldest -> newest."""
    # First report
    client.post(
        "/api/v1/reports",
        data={"latitude": 37.7749, "longitude": -122.4194, "timestamp": "2026-09-01T10:00:00Z"},
        files={"photo": ("p1.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")},
    )
    # Second report at same location (newer timestamp)
    res2 = client.post(
        "/api/v1/reports",
        data={"latitude": 37.7749, "longitude": -122.4194, "timestamp": "2026-09-15T10:00:00Z"},
        files={"photo": ("p2.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")},
    )
    loc_id = res2.json()["location_id"]

    timeline_res = client.get(f"/api/v1/locations/{loc_id}/reports")
    assert timeline_res.status_code == 200
    data = timeline_res.json()
    assert data["location_id"] == loc_id
    assert len(data["reports"]) == 2
    # Oldest first
    assert data["reports"][0]["timestamp"] < data["reports"][1]["timestamp"]


def test_list_reports_with_filters(client: TestClient, sample_image_bytes: bytes):
    """GET /api/v1/reports supports filtering and pagination."""
    # Create 2 reports
    client.post(
        "/api/v1/reports",
        data={"latitude": 37.7749, "longitude": -122.4194, "timestamp": "2026-09-01T10:00:00Z"},
        files={"photo": ("p1.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")},
    )
    client.post(
        "/api/v1/reports",
        data={"latitude": 37.7749, "longitude": -122.4194, "timestamp": "2026-09-15T10:00:00Z"},
        files={"photo": ("p2.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")},
    )

    # Filter by status="new"
    res = client.get("/api/v1/reports?status=new")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item["status"] == "new"

    # Pagination limit
    res_page = client.get("/api/v1/reports?limit=1&offset=0")
    assert res_page.status_code == 200
    assert len(res_page.json()["items"]) == 1


def test_validation_invalid_latitude(client: TestClient, sample_image_bytes: bytes):
    """POST /api/v1/reports returns 400 when latitude exceeds bounds."""
    res = client.post(
        "/api/v1/reports",
        data={"latitude": 150.0, "longitude": -122.4194, "timestamp": "2026-09-16T10:00:00Z"},
        files={"photo": ("p.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")},
    )
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "INVALID_COORDINATES"


def test_validation_invalid_timestamp(client: TestClient, sample_image_bytes: bytes):
    """POST /api/v1/reports returns 400 when timestamp format is corrupt."""
    res = client.post(
        "/api/v1/reports",
        data={"latitude": 37.7749, "longitude": -122.4194, "timestamp": "not-a-valid-date"},
        files={"photo": ("p.jpg", io.BytesIO(sample_image_bytes), "image/jpeg")},
    )
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "INVALID_TIMESTAMP"


def test_validation_unsupported_image_type(client: TestClient):
    """POST /api/v1/reports returns 400 when file is not an allowed image format."""
    files = {
        "photo": ("document.txt", io.BytesIO(b"Plain text file content here"), "text/plain"),
    }
    data = {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "timestamp": "2026-09-16T10:00:00Z",
    }
    res = client.post("/api/v1/reports", data=data, files=files)
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "INVALID_IMAGE_TYPE"
