"""
web_dashboard/backend/schemas/health.py
========================================
Pydantic response models for the /api/health and / endpoints.
"""

from pydantic import BaseModel, Field


class ComponentStatus(BaseModel):
    """Status of a single framework component."""
    available: bool
    detail: str = ""


class HealthResponse(BaseModel):
    """
    Response body for GET /api/health.

    All fields are read-only — computed at request time, never persisted.
    """
    status: str = Field(
        ...,
        description="Overall service status: 'healthy' or 'degraded'.",
        examples=["healthy"],
    )
    framework_name: str = Field(..., examples=["API Test Studio"])
    framework_version: str = Field(..., examples=["1.0.0"])
    database: ComponentStatus
    analytics: ComponentStatus
    reporting: ComponentStatus

    model_config = {"json_schema_extra": {
        "example": {
            "status": "healthy",
            "framework_name": "API Test Studio",
            "framework_version": "1.0.0",
            "database":  {"available": True,  "detail": "Connected — api_test_studio.db"},
            "analytics": {"available": True,  "detail": "AnalyticsManager ready"},
            "reporting": {"available": True,  "detail": "ReportManager ready"},
        }
    }}


class RootResponse(BaseModel):
    """Response body for GET /."""
    name: str = Field(..., examples=["API Test Studio"])
    version: str = Field(..., examples=["1.0.0"])
    description: str
    status: str = Field(..., examples=["running"])
    docs_url: str = Field(..., examples=["/docs"])
    redoc_url: str = Field(..., examples=["/redoc"])
    health_url: str = Field(..., examples=["/api/health"])
