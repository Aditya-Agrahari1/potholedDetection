from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.location import Location
from app.schemas.common import ErrorResponse
from app.schemas.location import LocationResponse, LocationTimelineResponse
from app.schemas.report import ReportDetailResponse

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get(
    "/{location_id}/reports",
    response_model=LocationTimelineResponse,
    summary="Get chronological report timeline for a location",
    description="Returns all reports for a specific monitored pothole location, ordered from oldest to newest to provide a complete defect lifecycle history.",
    responses={
        200: {"description": "Location report timeline", "model": LocationTimelineResponse},
        404: {"description": "Location not found", "model": ErrorResponse},
    },
)
def get_location_reports(
    location_id: int,
    db: Session = Depends(get_db),
):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "LOCATION_NOT_FOUND",
                "message": f"Location with ID {location_id} does not exist.",
            },
        )

    # Ordered oldest -> newest as required
    reports_sorted = sorted(location.reports, key=lambda r: r.timestamp)

    report_items = [
        ReportDetailResponse(
            id=r.id,
            location_id=r.location_id,
            latitude=location.latitude,
            longitude=location.longitude,
            photo_path=r.photo_path,
            photo_url=f"/api/v1/reports/{r.id}/photo",
            timestamp=r.timestamp,
            detection_data=r.detection_data,
            status=r.status,
            compared_to_id=r.compared_to_id,
            pdf_path=r.pdf_path,
            pdf_url=f"/api/v1/reports/{r.id}/pdf",
            created_at=r.created_at,
        )
        for r in reports_sorted
    ]

    return LocationTimelineResponse(
        location_id=location.id,
        latitude=location.latitude,
        longitude=location.longitude,
        created_at=location.created_at,
        reports=report_items,
    )


@router.get(
    "",
    response_model=List[LocationResponse],
    summary="List all tracked pothole locations",
    description="Retrieve all unique geographic coordinates where potholes have been reported.",
    responses={
        200: {"description": "List of locations", "model": List[LocationResponse]},
    },
)
def list_locations(
    db: Session = Depends(get_db),
):
    locations = db.query(Location).order_by(Location.id.desc()).all()
    return [
        LocationResponse(
            id=loc.id,
            latitude=loc.latitude,
            longitude=loc.longitude,
            created_at=loc.created_at,
            report_count=len(loc.reports),
        )
        for loc in locations
    ]
