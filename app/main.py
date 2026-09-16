import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.database import init_db
from app.routers.locations import router as locations_router
from app.routers.reports import router as reports_router
from app.services.gemini import GeminiAPIError

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pothole_api")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: initialize database schema on startup."""
    logger.info("Initializing database tables...")
    init_db()
    logger.info("Database initialized successfully.")
    yield
    logger.info("Application shutting down.")


app = FastAPI(
    title="Pothole Detection & Change-Tracking API",
    description=(
        "Production-ready backend REST API for automated road pothole defect detection, "
        "multitemporal visual change tracking via Google Gemini AI, and official civil infrastructure PDF report generation.\n\n"
        "### Key Features\n"
        "- **Automated Geolocation Proximity Matching**: Uses the Haversine formula (15m radius default) to detect whether an upload is a new defect or a follow-up inspection.\n"
        "- **Gemini AI Integration**: Real-time multimodal analysis for single-image detection and multi-image timeline comparison.\n"
        "- **PDF Report Generator**: Dynamic generation of formatted engineering inspection reports embedding field photos and AI defect metrics.\n"
        "- **Database Portability**: SQLAlchemy ORM compatible with SQLite and PostgreSQL without code changes."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Handle standard HTTPExceptions returning consistent ErrorResponse schema."""
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", "HTTP_ERROR")
        msg = exc.detail.get("message", str(exc.detail))
        details = exc.detail.get("details")
    else:
        code = "HTTP_ERROR"
        msg = str(exc.detail)
        details = None

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": msg,
                "details": details,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request payload validation failures gracefully."""
    errors = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err.get("loc", []))
        errors.append({"field": field, "message": err.get("msg"), "type": err.get("type")})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request payload failed input schema validation.",
                "details": errors,
            }
        },
    )


@app.exception_handler(GeminiAPIError)
async def gemini_api_exception_handler(request: Request, exc: GeminiAPIError):
    """Catch Gemini API failures and return clean 502 response without raw stack traces."""
    logger.error("Gemini API Error caught: %s", exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "GEMINI_UPSTREAM_ERROR",
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions to prevent leaking server internals or stack traces."""
    logger.exception("Unhandled server exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred while processing the request.",
                "details": None,
            }
        },
    )


# Health and discovery endpoints
@app.get("/health", tags=["Health"], summary="System health check")
def health_check():
    """Returns server and database status."""
    return {
        "status": "healthy",
        "gemini_model": settings.gemini_model,
        "matching_radius_meters": settings.matching_radius_meters,
        "database": "connected",
    }


@app.get("/", tags=["Health"], summary="Root service info")
def root():
    """Returns basic API service metadata and link to interactive documentation."""
    return {
        "service": "Pothole Detection & Change-Tracking System API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# Mount API routers under /api/v1
app.include_router(reports_router, prefix="/api/v1")
app.include_router(locations_router, prefix="/api/v1")
