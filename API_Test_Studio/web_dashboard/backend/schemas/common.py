"""
web_dashboard/backend/schemas/common.py
========================================
Shared Pydantic models reused across multiple routers.
"""

from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Structured error body returned on 4xx / 5xx responses."""
    error: str = Field(..., description="Short machine-readable error code.")
    message: str = Field(..., description="Human-readable explanation.")
    detail: Optional[Any] = Field(None, description="Optional extra context.")

    model_config = {"json_schema_extra": {
        "example": {
            "error": "not_found",
            "message": "Run 'run_abc123' does not exist.",
            "detail": None,
        }
    }}


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated list wrapper.

    Usage:
        PaginatedResponse[RunSummary](items=[...], total=42, page=1, page_size=20)
    """
    items: List[T]
    total: int
    page: int = 1
    page_size: int = 20
    has_next: bool = False
