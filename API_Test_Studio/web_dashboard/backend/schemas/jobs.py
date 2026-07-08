"""
web_dashboard/backend/schemas/jobs.py
=======================================
Pydantic v2 request / response models for the async job queue (Phase 9.3).

Endpoints covered:
    POST /api/jobs           — submit a new pipeline job
    GET  /api/jobs           — list all jobs (with optional status filter)
    GET  /api/jobs/{job_id}  — poll status / progress for one job
    POST /api/jobs/{job_id}/cancel  — (future) cancel a queued job
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class JobRequest(BaseModel):
    """Request body for POST /api/jobs — submit a new async pipeline job."""

    specification_filename: str = Field(
        ...,
        description="Filename inside ``uploaded_specs/`` to run against.",
        examples=["petstore_openapi3.yaml"],
    )
    environment: str = Field(
        default="development",
        description="Environment key from ``environments.yaml``.",
        examples=["development", "staging"],
    )
    base_url_override: Optional[str] = Field(
        default=None,
        description="Override the environment base_url for this job only.",
        examples=["https://httpbin.org"],
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
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

    model_config = {
        "json_schema_extra": {
            "example": {
                "specification_filename": "httpbin_verification.yaml",
                "environment": "development",
                "base_url_override": "https://httpbin.org",
                "timeout_seconds": 30,
                "verify_ssl": True,
                "generate_reports": True,
            }
        }
    }


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class JobStatusResponse(BaseModel):
    """
    Returned by GET /api/jobs/{job_id} and POST /api/jobs.

    Poll this until ``status`` is ``completed`` or ``failed``.
    """

    job_id: str = Field(..., description="Unique job identifier (UUID).")
    status: str = Field(
        ...,
        description="Current lifecycle status.",
        examples=["pending", "running", "completed", "failed"],
    )
    step: str = Field(
        ...,
        description="Human-readable label for the current pipeline phase.",
        examples=["Parsing API specification", "Executing HTTP requests", "Done"],
    )
    percent: int = Field(
        ...,
        ge=0,
        le=100,
        description="Estimated completion percentage (0–100).",
    )

    # Set once the job has completed successfully
    run_id: Optional[str] = Field(
        default=None,
        description="Database run ID — available when status is ``completed``.",
    )
    report_paths: List[str] = Field(
        default_factory=list,
        description="Generated report filenames — available when completed.",
    )

    # Set if the job failed
    error: Optional[str] = Field(
        default=None,
        description="Error message — available when status is ``failed``.",
    )

    # Timestamps
    created_at: str = Field(..., description="ISO-8601 UTC creation timestamp.")
    started_at: Optional[str] = Field(
        default=None,
        description="ISO-8601 UTC timestamp when execution started.",
    )
    completed_at: Optional[str] = Field(
        default=None,
        description="ISO-8601 UTC timestamp when execution finished.",
    )
    elapsed_s: Optional[float] = Field(
        default=None,
        description="Wall-clock seconds from start to completion.",
    )

    # Echo back what was requested
    spec_filename: str = Field(
        ...,
        description="The spec filename this job was submitted for.",
    )
    environment: str = Field(
        ...,
        description="The environment key this job was submitted with.",
    )


class JobSubmitResponse(BaseModel):
    """Returned immediately by POST /api/jobs (HTTP 202 Accepted)."""

    job_id: str = Field(..., description="Use this ID to poll GET /api/jobs/{job_id}.")
    status: str = Field(default="pending", description="Always ``pending`` on submit.")
    poll_url: str = Field(
        ...,
        description="Convenience URL to poll for status updates.",
    )
    message: str = Field(
        default=(
            "Job queued. Poll poll_url until status is 'completed' or 'failed'."
        ),
        description="Human-readable acknowledgement.",
    )


class JobListResponse(BaseModel):
    """Response for GET /api/jobs."""

    total: int = Field(..., description="Total number of jobs tracked in memory.")
    jobs: List[JobStatusResponse]
