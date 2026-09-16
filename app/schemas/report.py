from datetime import datetime
from typing import List, Optional, Any, Union
from pydantic import BaseModel, Field, ConfigDict


class PotholeDetectionItem(BaseModel):
    """Details for an individual detected pothole."""
    bbox: List[float] = Field(
        ...,
        description="Bounding box coordinates normalized between 0.0 and 1.0 [ymin, xmin, ymax, xmax] or [x, y, w, h]",
        examples=[[0.1, 0.2, 0.4, 0.5]],
    )
    severity: str = Field(
        ...,
        description="Severity assessment for this specific pothole: 'low', 'medium', or 'high'",
        examples=["medium"],
    )
    estimated_area_percent: float = Field(
        ...,
        description="Estimated percentage of visible road surface occupied by this pothole",
        examples=[12.5],
    )
    description: str = Field(
        ...,
        description="Brief physical description of the pothole defect",
        examples=["Deep crater defect with fractured asphalt edges"],
    )


class PotholeDetectionResult(BaseModel):
    """Structured response from Gemini pothole detection on a single image."""
    potholes_detected: bool = Field(..., description="Whether any potholes were identified in the image")
    count: int = Field(..., description="Total count of potholes detected", examples=[2])
    detections: List[PotholeDetectionItem] = Field(
        default_factory=list,
        description="List of detected pothole instances with individual metrics",
    )
    overall_severity: str = Field(
        ...,
        description="Aggregate severity across all detected potholes: 'low', 'medium', or 'high'",
        examples=["medium"],
    )
    report_summary: Optional[str] = Field(
        None,
        description="Narrative paragraph summarizing road condition for inclusion in reports",
        examples=["Two medium-severity potholes detected on the road surface requiring preventative maintenance."],
    )


class PotholeComparisonResult(BaseModel):
    """Structured response from Gemini comparing two sequential road photos at the same location."""
    status: str = Field(
        ...,
        description="Pothole progression status: 'worsened', 'improved', 'persistent', or 'resolved'",
        examples=["worsened"],
    )
    area_change_percent: float = Field(
        ...,
        description="Estimated percentage change in pothole surface area (+/-)",
        examples=[23.5],
    )
    severity_change: str = Field(
        ...,
        description="Direction of change in severity: 'increased', 'decreased', or 'same'",
        examples=["increased"],
    )
    reasoning: str = Field(
        ...,
        description="Explanation of visual differences observed between the earlier and later photos",
        examples=["The pothole boundary has expanded outwards and deepened since the previous capture."],
    )
    report_summary: str = Field(
        ...,
        description="Professional summary paragraph suitable for inclusion in an official PDF inspection report",
        examples=["Follow-up inspection shows the pothole has worsened with a 23.5% area increase. Immediate repair recommended."],
    )


class ReportCreateResponse(BaseModel):
    """Response model returned when a new report is created via POST /api/v1/reports."""
    report_id: int = Field(..., description="Unique ID of the newly generated report", examples=[42])
    location_id: int = Field(..., description="ID of the matched or newly created location", examples=[7])
    status: str = Field(
        ...,
        description="Status of the defect: 'new', 'worsened', 'improved', 'persistent', or 'resolved'",
        examples=["new"],
    )
    compared_to_report_id: Optional[int] = Field(
        None,
        description="ID of previous report compared against, or null if first report at location",
        examples=[None],
    )
    detection: Union[PotholeDetectionResult, PotholeComparisonResult, dict, Any] = Field(
        ...,
        description="Raw structured AI analysis output from Gemini (detection or comparison schema)",
    )
    pdf_url: str = Field(..., description="URL endpoint to download the generated PDF report", examples=["/api/v1/reports/42/pdf"])
    created_at: datetime = Field(..., description="Timestamp when report was processed and saved", examples=["2026-09-16T10:30:00Z"])

    model_config = ConfigDict(from_attributes=True)


class ReportDetailResponse(BaseModel):
    """Full detail model for an individual report."""
    id: int = Field(..., description="Unique ID of the report", examples=[42])
    location_id: int = Field(..., description="Associated location ID", examples=[7])
    latitude: float = Field(..., description="Latitude coordinate", examples=[37.7749])
    longitude: float = Field(..., description="Longitude coordinate", examples=[-122.4194])
    photo_path: str = Field(..., description="Storage path of submitted photo")
    photo_url: Optional[str] = Field(None, description="Public download/view URL for the photo")
    timestamp: datetime = Field(..., description="User-submitted photo capture timestamp")
    detection_data: Any = Field(..., description="Raw structured detection or comparison JSON from Gemini")
    status: str = Field(..., description="Report status classification")
    compared_to_id: Optional[int] = Field(None, description="ID of baseline report compared against")
    pdf_path: Optional[str] = Field(None, description="Storage path of generated PDF")
    pdf_url: Optional[str] = Field(None, description="Endpoint to download generated PDF")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class ReportListResponse(BaseModel):
    """Paginated list of reports."""
    total: int = Field(..., description="Total number of matching reports", examples=[1])
    limit: int = Field(..., description="Maximum results requested", examples=[20])
    offset: int = Field(..., description="Offset used for pagination", examples=[0])
    items: List[ReportDetailResponse] = Field(..., description="List of report records")
