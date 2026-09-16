from typing import Any, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Structured error model for API error responses."""
    code: str = Field(..., description="Error classification code")
    message: str = Field(..., description="Human-readable error explanation")
    details: Optional[Any] = Field(None, description="Additional context or validation details")


class ErrorResponse(BaseModel):
    """Standardized API error response body."""
    error: ErrorDetail
