"""
web_dashboard/backend/schemas/runs.py
======================================
Pydantic response models for the /api/run and /api/runs endpoints.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Execution request
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    """Request body for POST /api/run."""
    specification_filename: str = Field(
        ...,
        description="Filename inside uploaded_specs/ to run against.",
        examples=["petstore_openapi3.yaml"],
    )
    environment: str = Field(
        default="development",
        description="Environment key from environments.yaml.",
        examples=["development", "staging"],
    )
    base_url_override: Optional[str] = Field(
        default=None,
        description="Override the environment base_url for this run only.",
        examples=["https://httpbin.org"],
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1, le=300,
        description="Per-request HTTP timeout in seconds.",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify TLS certificates.",
    )
    generate_reports: bool = Field(
        default=True,
        description="Whether to run Phase 8 report generation after execution.",
    )

    model_config = {"json_schema_extra": {"example": {
        "specification_filename": "httpbin_verification.yaml",
        "environment": "development",
        "base_url_override": "https://httpbin.org",
        "timeout_seconds": 30,
        "verify_ssl": True,
        "generate_reports": True,
    }}}


# ---------------------------------------------------------------------------
# Execution response
# ---------------------------------------------------------------------------

class RunSummary(BaseModel):
    """Compact summary returned after execution and in list views."""
    run_id: str
    api_name: str
    api_version: Optional[str]
    environment: Optional[str]
    execution_timestamp: Optional[str]
    total_endpoints: int
    total_test_cases: int
    total_executed: int
    passed: int
    failed: int
    skipped: int
    errors: int
    pass_percentage: float
    avg_response_time_ms: Optional[float]
    total_execution_time_s: Optional[float]
    health_score: Optional[float]
    health_rating: Optional[str]
    specification_file: Optional[str]
    framework_version: Optional[str]


class RunResponse(BaseModel):
    """Returned immediately after POST /api/run completes."""
    run_id: str
    status: str = Field(..., examples=["completed", "failed"])
    api_name: str
    summary: RunSummary
    report_paths: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class RunListResponse(BaseModel):
    """Response for GET /api/runs."""
    total: int
    page: int
    page_size: int
    has_next: bool
    runs: List[RunSummary]


# ---------------------------------------------------------------------------
# Run detail
# ---------------------------------------------------------------------------

class ValidatorStat(BaseModel):
    validator_name: str
    passed: int
    failed: int
    total: int
    pass_rate: float


class ValidationSummarySchema(BaseModel):
    validators: List[ValidatorStat]
    total_assertions: int
    total_passed: int
    total_failed: int


class RunDetailResponse(BaseModel):
    """Full detail for GET /api/runs/{run_id}."""
    run: RunSummary
    validation_summary: Optional[ValidationSummarySchema]
    report_links: List[str] = Field(default_factory=list)
