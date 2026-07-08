"""
web_dashboard/backend/schemas/results.py
==========================================
Pydantic v2 response models for the test-results query API (Phase 9.4).

Endpoints covered:
    GET /api/runs/{run_id}/results               — filtered/paginated results
    GET /api/runs/{run_id}/results/{result_id}   — single result detail
    GET /api/runs/{run_id}/results/summary       — per-endpoint/category counts
"""

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Validation detail (one row from validation_details table)
# ---------------------------------------------------------------------------

class ValidationDetailSchema(BaseModel):
    """One validator assertion result attached to a test-case result."""

    validation_detail_id: str
    validator_name: str
    status: str = Field(..., examples=["passed", "failed"])
    message: Optional[str] = None
    severity: Optional[str] = None
    execution_time_ms: Optional[float] = None
    recorded_at: str


# ---------------------------------------------------------------------------
# Test-case result (one row from test_case_results table)
# ---------------------------------------------------------------------------

class TestCaseResultSchema(BaseModel):
    """
    Represents one executed + validated test case.

    ``request_headers``, ``request_payload``, ``response_headers``, and
    ``response_body`` are stored as JSON strings in SQLite.  This schema
    exposes them as parsed ``Any`` values so API consumers get real JSON
    objects rather than escaped strings.
    """

    result_id: str
    run_id: str
    test_id: str
    operation_id: Optional[str] = None
    endpoint: str
    http_method: str
    category: Optional[str] = None
    request_url: Optional[str] = None

    request_headers: Optional[Any] = Field(
        default=None,
        description="Request headers as a JSON object (parsed from stored string).",
    )
    request_payload: Optional[Any] = Field(
        default=None,
        description="Request body as a JSON value (parsed from stored string).",
    )

    response_status_code: Optional[int] = None
    response_headers: Optional[Any] = Field(
        default=None,
        description="Response headers as a JSON object.",
    )
    response_body: Optional[Any] = Field(
        default=None,
        description="Response body as a JSON value, or raw string if not valid JSON.",
    )

    response_time_ms: Optional[float] = None
    validation_status: Optional[str] = Field(
        default=None,
        examples=["passed", "failed", "skipped", "error"],
    )
    failure_reason: Optional[str] = None
    validation_time_ms: Optional[float] = None
    executed_at: Optional[str] = None

    # Populated only in the detail endpoint (GET …/results/{result_id})
    validation_details: Optional[List[ValidationDetailSchema]] = Field(
        default=None,
        description="Per-validator assertion details. Only present in the detail view.",
    )

    @field_validator(
        "request_headers",
        "request_payload",
        "response_headers",
        "response_body",
        mode="before",
    )
    @classmethod
    def _parse_json_string(cls, v: Any) -> Any:
        """
        If the value is a JSON string, decode it so the API returns a
        proper object rather than a double-escaped string.
        """
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return v   # keep raw string (e.g. HTML body)
        return v


# ---------------------------------------------------------------------------
# Paginated list response
# ---------------------------------------------------------------------------

class TestCaseResultListResponse(BaseModel):
    """Response for GET /api/runs/{run_id}/results."""

    run_id: str
    total: int = Field(..., description="Total matching results (before pagination).")
    page: int
    page_size: int
    has_next: bool
    results: List[TestCaseResultSchema]


# ---------------------------------------------------------------------------
# Summary response  (per-endpoint and per-category breakdown)
# ---------------------------------------------------------------------------

class EndpointSummaryRow(BaseModel):
    """Pass/fail counts for a single endpoint path."""

    endpoint: str
    http_method: str
    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    pass_rate: float = Field(..., description="Percentage 0–100.")
    avg_response_time_ms: Optional[float] = None


class CategorySummaryRow(BaseModel):
    """Pass/fail counts for a test-case category (positive/negative/boundary/security)."""

    category: str
    total: int
    passed: int
    failed: int
    pass_rate: float


class ResultsSummaryResponse(BaseModel):
    """
    Response for GET /api/runs/{run_id}/results/summary.

    Provides an aggregated breakdown without sending every individual row.
    """

    run_id: str
    total_results: int
    passed: int
    failed: int
    skipped: int
    errors: int
    pass_rate: float

    by_endpoint: List[EndpointSummaryRow]
    by_category: List[CategorySummaryRow]
    by_status: Dict[str, int] = Field(
        ...,
        description="Raw count keyed by validation_status value.",
    )
    by_http_method: Dict[str, int] = Field(
        ...,
        description="Raw count keyed by HTTP method.",
    )
