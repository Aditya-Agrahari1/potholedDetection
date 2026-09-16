import json
import logging
import re
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GeminiAPIError(Exception):
    """Exception raised when Gemini API calls fail or return invalid data after retries."""

    def __init__(self, message: str, status_code: int = 502, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


def clean_and_parse_json(text: str) -> Dict[str, Any]:
    """Robust JSON parser that strips markdown code fences and surrounding prose.

    Handles:
    - ```json ... ``` or ``` ... ``` blocks
    - Leading/trailing text before first '{' and after last '}'
    """
    if not text or not text.strip():
        raise ValueError("Empty response received from AI model")

    cleaned = text.strip()

    # 1. Check for markdown code blocks
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(fence_pattern, cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()

    # 2. Extract substring between first '{' and last '}'
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = cleaned[start_idx : end_idx + 1]

    # 3. Parse JSON
    return json.loads(cleaned)


DETECTION_PROMPT = """Analyze this image of a road surface for potholes and structural road surface defects.
You must return a STRICT JSON object only. Do not output markdown code blocks (no ```json fences), no conversational text, and no commentary.

The JSON output MUST match this exact schema:
{
  "potholes_detected": true,
  "count": 1,
  "detections": [
    {
      "bbox": [0.1, 0.2, 0.4, 0.5],
      "severity": "low",
      "estimated_area_percent": 12.5,
      "description": "short description of the pothole"
    }
  ],
  "overall_severity": "low",
  "report_summary": "A 2-3 sentence technical summary describing the condition of the road surface and defect severity for an official road inspection report."
}

Allowed values for severity and overall_severity: "low", "medium", "high".
If no potholes are detected:
- set "potholes_detected" to false
- set "count" to 0
- set "detections" to []
- set "overall_severity" to "low"
- provide an appropriate "report_summary" noting no road defects detected.
"""


COMPARISON_PROMPT = """Compare these two sequential photographs of the same road pothole location.
- The EARLIER photograph was captured at: {old_timestamp}
- The LATER photograph was captured at: {new_timestamp}

Determine whether the pothole has worsened, improved, persisted (no meaningful change), or resolved.
You must return a STRICT JSON object only. Do not output markdown code blocks (no ```json fences), no conversational text, and no commentary.

The JSON output MUST match this exact schema:
{
  "status": "worsened",
  "area_change_percent": 23.5,
  "severity_change": "increased",
  "reasoning": "1-2 sentence technical explanation comparing earlier and later surface deterioration.",
  "report_summary": "A 3-4 sentence paragraph suitable for inclusion in an official civil infrastructure PDF report describing defect progression and recommended maintenance actions."
}

Allowed values:
- "status": "worsened", "improved", "persistent", or "resolved"
- "severity_change": "increased", "decreased", or "same"
- "area_change_percent": numeric float (positive for expansion, negative for reduction, 0 for same)
"""


class GeminiService:
    """Service handling interactions with the Google Gemini API using google-genai SDK."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.gemini_model
        self.is_mock = (
            not self.api_key
            or self.api_key.lower() in ("mock", "test", "dummy", "none")
        )

        if not self.is_mock:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def _call_gemini_with_retry(self, contents: List[Any], schema_description: str) -> Dict[str, Any]:
        """Execute Gemini generate_content call with one retry on parse failure."""
        if self.is_mock:
            raise RuntimeError("Mock mode active; should not invoke live client directly")

        raw_response_text = ""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
            )
            raw_response_text = response.text or ""
            return clean_and_parse_json(raw_response_text)
        except (json.JSONDecodeError, ValueError) as parse_err:
            logger.warning(
                "Gemini response failed initial JSON parsing: %s. Retrying once...",
                parse_err,
            )
            # Attempt 1 retry with corrective prompt
            try:
                retry_contents = contents + [
                    f"CRITICAL: Your previous response could not be parsed as valid JSON: '{raw_response_text}'. "
                    f"Please convert it into STRICT valid JSON with no markdown formatting or prose. "
                    f"Schema required: {schema_description}"
                ]
                retry_response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=retry_contents,
                )
                return clean_and_parse_json(retry_response.text or "")
            except Exception as retry_err:
                logger.error("Gemini failed after retry: %s", retry_err)
                raise GeminiAPIError(
                    message=f"Gemini returned invalid or unparseable JSON after retry: {str(retry_err)}",
                    status_code=502,
                    details={"raw_response": raw_response_text},
                )
        except Exception as api_err:
            logger.error("Upstream Gemini API error: %s", api_err)
            raise GeminiAPIError(
                message=f"Gemini API request failed: {str(api_err)}",
                status_code=502,
            )

    def detect_potholes(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> Dict[str, Any]:
        """Perform single-image pothole detection."""
        if self.is_mock:
            return {
                "potholes_detected": True,
                "count": 1,
                "detections": [
                    {
                        "bbox": [0.25, 0.30, 0.65, 0.70],
                        "severity": "medium",
                        "estimated_area_percent": 15.0,
                        "description": "Noticeable asphalt erosion and crater defect with edge cracking",
                    }
                ],
                "overall_severity": "medium",
                "report_summary": "Automated visual inspection identified a medium-severity pothole occupying approximately 15% of the visible lane area. Preventative resurfacing is recommended before structural asphalt degradation expands.",
            }

        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            DETECTION_PROMPT,
        ]
        result = self._call_gemini_with_retry(
            contents,
            schema_description='{"potholes_detected": bool, "count": int, "detections": list, "overall_severity": str, "report_summary": str}',
        )

        # Ensure required keys exist with defaults if missing
        result.setdefault("potholes_detected", True if result.get("count", 0) > 0 else False)
        result.setdefault("count", len(result.get("detections", [])))
        result.setdefault("detections", [])
        result.setdefault("overall_severity", "medium")
        result.setdefault(
            "report_summary",
            f"Detected {result.get('count', 1)} pothole(s) with {result.get('overall_severity', 'medium')} severity.",
        )
        return result

    def compare_potholes(
        self,
        old_image_bytes: bytes,
        old_mime: str,
        new_image_bytes: bytes,
        new_mime: str,
        old_timestamp: str,
        new_timestamp: str,
    ) -> Dict[str, Any]:
        """Perform two-image comparison and change tracking between sequential photos."""
        if self.is_mock:
            return {
                "status": "worsened",
                "area_change_percent": 24.5,
                "severity_change": "increased",
                "reasoning": "Follow-up imagery reveals edge spalling and depth increase compared to the initial baseline capture.",
                "report_summary": "Comparative inspection indicates the pothole has worsened significantly over the monitoring period, expanding by approximately 24.5% in surface area. Edge disintegration indicates elevated risk to vehicular traffic; patching crew dispatch is advised.",
            }

        prompt = COMPARISON_PROMPT.format(
            old_timestamp=old_timestamp,
            new_timestamp=new_timestamp,
        )

        contents = [
            f"PHOTO 1 (BASELINE / EARLIER - Captured: {old_timestamp}):",
            types.Part.from_bytes(data=old_image_bytes, mime_type=old_mime),
            f"PHOTO 2 (LATEST / RECENT - Captured: {new_timestamp}):",
            types.Part.from_bytes(data=new_image_bytes, mime_type=new_mime),
            prompt,
        ]

        result = self._call_gemini_with_retry(
            contents,
            schema_description='{"status": str, "area_change_percent": float, "severity_change": str, "reasoning": str, "report_summary": str}',
        )

        # Normalize status to allowed set
        valid_statuses = {"worsened", "improved", "persistent", "resolved"}
        status = str(result.get("status", "persistent")).lower()
        if status not in valid_statuses:
            status = "persistent"
        result["status"] = status

        result.setdefault("area_change_percent", 0.0)
        result.setdefault("severity_change", "same")
        result.setdefault("reasoning", "Comparison evaluated between sequential timestamps.")
        result.setdefault(
            "report_summary",
            f"Pothole status evaluated as {status} based on multi-temporal visual comparison.",
        )
        return result


# Singleton instance
_gemini_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    """Dependency injector / factory for GeminiService."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
