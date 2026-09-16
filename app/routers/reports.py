import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models.location import Location
from app.models.report import Report
from app.schemas.common import ErrorResponse
from app.schemas.report import (
    ReportCreateResponse,
    ReportDetailResponse,
    ReportListResponse,
)
from app.services.gemini import GeminiAPIError, GeminiService, get_gemini_service
from app.services.matcher import find_nearest_location
from app.services.pdf import generate_pdf_report
from app.services.storage import StorageService, get_storage_service

router = APIRouter(prefix="/reports", tags=["Reports"])
settings = get_settings()


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse ISO8601 timestamp string into timezone-naive UTC datetime."""
    try:
        # Replace Z with +00:00 for fromisoformat compatibility
        cleaned = dt_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        # Convert to naive UTC
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_TIMESTAMP",
                "message": f"Malformed ISO 8601 timestamp '{dt_str}'. Expected format: YYYY-MM-DDTHH:MM:SSZ",
                "details": str(e),
            },
        )


@router.post(
    "",
    response_model=ReportCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new road pothole report",
    description=(
        "Upload a road surface photo with coordinates and timestamp. "
        "If a previous report exists within the matching radius (default 15m), "
        "runs Gemini comparison against the baseline to track progression ('worsened', 'improved', 'persistent', 'resolved'). "
        "Otherwise, creates a new location, runs initial detection, and generates an official PDF report."
    ),
    responses={
        201: {"description": "Report successfully analyzed and recorded", "model": ReportCreateResponse},
        400: {"description": "Bad Request: Invalid image format, invalid coordinates, or malformed timestamp", "model": ErrorResponse},
        502: {"description": "Bad Gateway: Gemini AI service failed or returned unparseable output", "model": ErrorResponse},
    },
)
async def create_report(
    photo: UploadFile = File(..., description="Photo file (JPEG, PNG, or WebP)"),
    latitude: float = Form(..., description="Latitude coordinate between -90 and 90", examples=[37.7749]),
    longitude: float = Form(..., description="Longitude coordinate between -180 and 180", examples=[-122.4194]),
    timestamp: str = Form(..., description="ISO 8601 capture timestamp", examples=["2026-09-16T10:30:00Z"]),
    db: Session = Depends(get_db),
    gemini: GeminiService = Depends(get_gemini_service),
    storage: StorageService = Depends(get_storage_service),
):
    # 1. Validate coordinates
    if not (-90.0 <= latitude <= 90.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_COORDINATES",
                "message": f"Latitude {latitude} is outside valid range [-90.0, 90.0]",
            },
        )
    if not (-180.0 <= longitude <= 180.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_COORDINATES",
                "message": f"Longitude {longitude} is outside valid range [-180.0, 180.0]",
            },
        )

    # 2. Validate timestamp
    parsed_dt = parse_iso_datetime(timestamp)

    # 3. Validate image upload
    content_type = photo.content_type or "image/jpeg"
    ext = os.path.splitext(photo.filename or "")[1].lower()
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}

    if content_type not in settings.allowed_image_types and ext not in valid_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_IMAGE_TYPE",
                "message": f"Unsupported media type '{content_type}'. Allowed types: JPEG, PNG, WebP.",
            },
        )

    photo_bytes = await photo.read()
    if not photo_bytes or len(photo_bytes) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "EMPTY_OR_CORRUPT_IMAGE",
                "message": "Uploaded photo file is empty or too small to be a valid image.",
            },
        )

    # 4. Save photo file via storage service
    file_ext = ext if ext in valid_exts else ".jpg"
    unique_photo_filename = f"{uuid.uuid4().hex}{file_ext}"
    saved_photo_path = storage.save_file(photo_bytes, unique_photo_filename, subfolder="photos")
    abs_new_photo_path = storage.get_absolute_path(saved_photo_path)

    # 5. Proximity location matching
    matched = find_nearest_location(
        db,
        latitude=latitude,
        longitude=longitude,
        threshold_meters=settings.matching_radius_meters,
    )

    location: Location
    report_status: str
    compared_to_id: Optional[int] = None
    detection_data: dict
    previous_report: Optional[Report] = None

    if matched is not None:
        # Existing location found within threshold radius
        location, dist = matched
        # Retrieve the most recent report at this location
        previous_report = (
            db.query(Report)
            .filter(Report.location_id == location.id)
            .order_by(desc(Report.timestamp))
            .first()
        )

    can_compare = (
        matched is not None
        and previous_report is not None
        and storage.file_exists(previous_report.photo_path)
    )

    if can_compare and previous_report is not None:
        # Sequential follow-up report at existing location -> Run comparison
        compared_to_id = previous_report.id
        abs_old_photo_path = storage.get_absolute_path(previous_report.photo_path)

        try:
            old_photo_bytes = storage.read_file(previous_report.photo_path)
            old_mime = "image/png" if previous_report.photo_path.endswith(".png") else "image/jpeg"

            comparison_result = gemini.compare_potholes(
                old_image_bytes=old_photo_bytes,
                old_mime=old_mime,
                new_image_bytes=photo_bytes,
                new_mime=content_type,
                old_timestamp=previous_report.timestamp.isoformat(),
                new_timestamp=parsed_dt.isoformat(),
            )
            report_status = comparison_result.get("status", "persistent")
            detection_data = comparison_result
        except GeminiAPIError:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "GEMINI_COMPARISON_FAILED",
                    "message": f"Failed to perform visual comparison with Gemini AI: {str(e)}",
                },
            )
    else:
        # Brand new location (or baseline photo missing on disk) -> Run single-image detection
        if matched is None:
            location = Location(latitude=latitude, longitude=longitude)
            db.add(location)
            db.flush()  # Populates location.id
        elif previous_report is not None:
            compared_to_id = previous_report.id

        try:
            detection_result = gemini.detect_potholes(image_bytes=photo_bytes, mime_type=content_type)
            report_status = "new"
            detection_data = detection_result
        except GeminiAPIError:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "GEMINI_DETECTION_FAILED",
                    "message": f"Failed to perform pothole detection with Gemini AI: {str(e)}",
                },
            )

    # 6. Create Report DB record
    new_report = Report(
        location_id=location.id,
        photo_path=saved_photo_path,
        timestamp=parsed_dt,
        detection_data=detection_data,
        status=report_status,
        compared_to_id=compared_to_id,
        pdf_path=None,
    )
    db.add(new_report)
    db.flush()  # Populates new_report.id

    # 7. Generate PDF Report
    prev_photo_abs = (
        storage.get_absolute_path(previous_report.photo_path)
        if previous_report and previous_report.photo_path
        else None
    )
    prev_dt = previous_report.timestamp if previous_report else None

    pdf_bytes = generate_pdf_report(
        report_id=new_report.id,
        location_id=location.id,
        latitude=location.latitude,
        longitude=location.longitude,
        timestamp=parsed_dt,
        status=report_status,
        detection_data=detection_data,
        current_photo_path=abs_new_photo_path,
        previous_photo_path=prev_photo_abs,
        previous_report_id=compared_to_id,
        previous_timestamp=prev_dt,
    )

    pdf_filename = f"report_{new_report.id}.pdf"
    saved_pdf_path = storage.save_file(pdf_bytes, pdf_filename, subfolder="reports")
    new_report.pdf_path = saved_pdf_path

    db.commit()
    db.refresh(new_report)

    return ReportCreateResponse(
        report_id=new_report.id,
        location_id=location.id,
        status=new_report.status,
        compared_to_report_id=new_report.compared_to_id,
        detection=new_report.detection_data,
        pdf_url=f"/api/v1/reports/{new_report.id}/pdf",
        created_at=new_report.created_at,
    )


@router.get(
    "/{report_id}",
    response_model=ReportDetailResponse,
    summary="Get full report details",
    description="Retrieve comprehensive details for an individual pothole inspection report.",
    responses={
        200: {"description": "Report details found", "model": ReportDetailResponse},
        404: {"description": "Report not found", "model": ErrorResponse},
    },
)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPORT_NOT_FOUND", "message": f"Report with ID {report_id} does not exist."},
        )

    return ReportDetailResponse(
        id=report.id,
        location_id=report.location_id,
        latitude=report.location.latitude,
        longitude=report.location.longitude,
        photo_path=report.photo_path,
        photo_url=f"/api/v1/reports/{report.id}/photo",
        timestamp=report.timestamp,
        detection_data=report.detection_data,
        status=report.status,
        compared_to_id=report.compared_to_id,
        pdf_path=report.pdf_path,
        pdf_url=f"/api/v1/reports/{report.id}/pdf",
        created_at=report.created_at,
    )


@router.get(
    "/{report_id}/pdf",
    summary="Download or stream report PDF",
    description="Streams or downloads the official generated PDF inspection report.",
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF file stream"},
        404: {"description": "Report or PDF file not found", "model": ErrorResponse},
    },
)
def download_report_pdf(
    report_id: int,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report or not report.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PDF_NOT_FOUND", "message": f"PDF report for ID {report_id} was not found."},
        )

    abs_path = storage.get_absolute_path(report.pdf_path)
    if not os.path.exists(abs_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "FILE_MISSING", "message": f"PDF file at path '{abs_path}' is missing on disk."},
        )

    return FileResponse(
        path=abs_path,
        media_type="application/pdf",
        filename=f"pothole_report_{report_id}.pdf",
    )


@router.get(
    "/{report_id}/photo",
    summary="View inspection photo",
    description="Retrieve the raw photo image associated with this report.",
    responses={
        200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}}, "description": "Photo image file stream"},
        404: {"description": "Photo not found", "model": ErrorResponse},
    },
)
def get_report_photo(
    report_id: int,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report or not report.photo_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PHOTO_NOT_FOUND", "message": f"Photo for report ID {report_id} was not found."},
        )

    abs_path = storage.get_absolute_path(report.photo_path)
    if not os.path.exists(abs_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PHOTO_MISSING", "message": f"Photo file at path '{abs_path}' is missing on disk."},
        )

    ext = os.path.splitext(abs_path)[1].lower()
    media_type = "image/png" if ext == ".png" else "image/webp" if ext == ".webp" else "image/jpeg"
    return FileResponse(path=abs_path, media_type=media_type)


@router.get(
    "",
    response_model=ReportListResponse,
    summary="List and filter reports",
    description="Retrieve a paginated list of reports with optional filtering by defect status and date range.",
    responses={
        200: {"description": "Paginated list of reports", "model": ReportListResponse},
    },
)
def list_reports(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by report status: 'new', 'worsened', 'improved', 'persistent', 'resolved'",
    ),
    from_date: Optional[datetime] = Query(None, description="Filter reports captured on or after this UTC timestamp"),
    to_date: Optional[datetime] = Query(None, description="Filter reports captured on or before this UTC timestamp"),
    limit: int = Query(20, ge=1, le=100, description="Page size (max 100)"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: Session = Depends(get_db),
):
    query = db.query(Report)

    if status_filter:
        query = query.filter(Report.status == status_filter.lower())
    if from_date:
        query = query.filter(Report.timestamp >= from_date)
    if to_date:
        query = query.filter(Report.timestamp <= to_date)

    total = query.count()
    reports = query.order_by(desc(Report.timestamp)).offset(offset).limit(limit).all()

    items = [
        ReportDetailResponse(
            id=r.id,
            location_id=r.location_id,
            latitude=r.location.latitude,
            longitude=r.location.longitude,
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
        for r in reports
    ]

    return ReportListResponse(total=total, limit=limit, offset=offset, items=items)
