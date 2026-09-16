import pytest
from app.services.gemini import clean_and_parse_json, GeminiAPIError, GeminiService


def test_clean_and_parse_pure_json():
    """Test standard raw JSON without fences."""
    raw = '{"status": "new", "count": 2}'
    data = clean_and_parse_json(raw)
    assert data == {"status": "new", "count": 2}


def test_clean_and_parse_json_with_fences():
    """Test stripping ```json ... ``` code fences."""
    raw = """```json
    {
      "potholes_detected": true,
      "count": 1,
      "overall_severity": "medium"
    }
    ```"""
    data = clean_and_parse_json(raw)
    assert data["potholes_detected"] is True
    assert data["count"] == 1
    assert data["overall_severity"] == "medium"


def test_clean_and_parse_json_with_surrounding_commentary():
    """Test stripping markdown commentary before and after the JSON block."""
    raw = """Here is the detection analysis you requested:
    ```json
    {
      "status": "worsened",
      "area_change_percent": 15.2
    }
    ```
    I hope this helps your inspection."""
    data = clean_and_parse_json(raw)
    assert data["status"] == "worsened"
    assert data["area_change_percent"] == 15.2


def test_clean_and_parse_invalid_json():
    """Unparseable string should raise ValueError or JSONDecodeError."""
    with pytest.raises(Exception):
        clean_and_parse_json("This is not JSON at all.")


def test_gemini_mock_mode_detection():
    """Verify mock mode returns schema-compliant detection response."""
    service = GeminiService(api_key="mock")
    result = service.detect_potholes(b"fake_image_bytes", mime_type="image/jpeg")
    assert "potholes_detected" in result
    assert "count" in result
    assert "detections" in result
    assert "overall_severity" in result
    assert "report_summary" in result


def test_gemini_mock_mode_comparison():
    """Verify mock mode returns schema-compliant comparison response."""
    service = GeminiService(api_key="mock")
    result = service.compare_potholes(
        old_image_bytes=b"old_bytes",
        old_mime="image/jpeg",
        new_image_bytes=b"new_bytes",
        new_mime="image/jpeg",
        old_timestamp="2026-09-01T10:00:00Z",
        new_timestamp="2026-09-16T10:00:00Z",
    )
    assert result["status"] in ("worsened", "improved", "persistent", "resolved")
    assert "area_change_percent" in result
    assert "severity_change" in result
    assert "report_summary" in result
