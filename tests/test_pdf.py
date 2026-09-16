import os
from datetime import datetime, timezone
from app.services.pdf import generate_pdf_report


def test_generate_pdf_single_photo(temp_dir, sample_image_bytes):
    """Test generating a PDF report for a new location (single photo)."""
    photo_file = os.path.join(temp_dir, "test_pothole.jpg")
    with open(photo_file, "wb") as f:
        f.write(sample_image_bytes)

    detection_data = {
        "potholes_detected": True,
        "count": 1,
        "detections": [
            {
                "bbox": [0.2, 0.3, 0.6, 0.7],
                "severity": "medium",
                "estimated_area_percent": 15.0,
                "description": "Surface erosion defect",
            }
        ],
        "overall_severity": "medium",
        "report_summary": "Initial baseline inspection report for road pothole.",
    }

    pdf_bytes = generate_pdf_report(
        report_id=1,
        location_id=10,
        latitude=37.7749,
        longitude=-122.4194,
        timestamp=datetime.now(timezone.utc),
        status="new",
        detection_data=detection_data,
        current_photo_path=photo_file,
    )

    assert pdf_bytes is not None
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")


def test_generate_pdf_comparison_two_photos(temp_dir, sample_image_bytes):
    """Test generating a comparison PDF report with baseline and follow-up photos."""
    photo1 = os.path.join(temp_dir, "baseline.jpg")
    photo2 = os.path.join(temp_dir, "followup.jpg")
    with open(photo1, "wb") as f:
        f.write(sample_image_bytes)
    with open(photo2, "wb") as f:
        f.write(sample_image_bytes)

    comparison_data = {
        "status": "worsened",
        "area_change_percent": 22.5,
        "severity_change": "increased",
        "reasoning": "Expansion of pothole rim observed.",
        "report_summary": "Comparative inspection shows defect progression.",
    }

    pdf_bytes = generate_pdf_report(
        report_id=2,
        location_id=10,
        latitude=37.7749,
        longitude=-122.4194,
        timestamp=datetime.now(timezone.utc),
        status="worsened",
        detection_data=comparison_data,
        current_photo_path=photo2,
        previous_photo_path=photo1,
        previous_report_id=1,
        previous_timestamp=datetime(2026, 9, 1, 10, 0, 0),
    )

    assert pdf_bytes is not None
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")
