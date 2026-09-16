from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.report import ReportDetailResponse


class LocationBase(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees", examples=[37.7749])
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees", examples=[-122.4194])


class LocationResponse(LocationBase):
    id: int = Field(..., description="Unique ID of location", examples=[7])
    created_at: datetime = Field(..., description="Timestamp when location was first recorded")
    report_count: Optional[int] = Field(0, description="Total reports logged at this location")

    model_config = ConfigDict(from_attributes=True)


class LocationTimelineResponse(LocationBase):
    """Timeline of reports for a specific pothole location ordered oldest to newest."""
    location_id: int = Field(..., description="Location ID", examples=[7])
    created_at: datetime = Field(..., description="Location creation timestamp")
    reports: List[ReportDetailResponse] = Field(
        default_factory=list,
        description="Chronological history of all inspection reports for this location (oldest to newest)",
    )

    model_config = ConfigDict(from_attributes=True)
