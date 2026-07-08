"""
web_dashboard/backend/routers/results.py
==========================================
Phase 9.4 — Test-results query endpoints.

    GET /api/runs/{run_id}/results/summary    — aggregated breakdown
    GET /api/runs/{run_id}/results            — filtered + paginated result list
    GET /api/runs/{run_id}/results/{result_id} — full detail for one result

Design notes
------------
* The ``/summary`` sub-path is registered **before** ``/{result_id}`` so
  FastAPI routes ``/results/summary`` to the summary handler instead of
  treating ``"summary"`` as a ``result_id`` path parameter.
* All three endpoints share the same ``_get_db()`` helper (no FastAPI
  Depends — identical pattern to runs.py for consistency).
* JSON fields stored as strings in SQLite (headers, body, payload) are
  parsed by the Pydantic ``field_validator`` in ``TestCaseResultSchema``
  so API consumers always receive proper JSON objects.
* Pagination is computed in Python after fetching from SQLite (repository
  returns at most ``page_size * page + 1`` rows) to avoid a separate
  COUNT query.
"""

from collections import defaultdict
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from web_dashboard.backend.config.settings import Settings, get_settings
from web_dashboard.backend.schemas.results import (
    CategorySummaryRow,
    EndpointSummaryRow,
    ResultsSummaryResponse,
    TestCaseResultListResponse,
    TestCaseResultSchema,
    ValidationDetailSchema,
)

import sys as _sys
_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _root not in _sys.path:
    _sys.path.insert(0, _root)

from utilities.logger import get_logger

logger = get_logger("web_dashboard.backend.results")

router = APIRouter(tags=["Results"])


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _get_db(settings: Settings):
    """Open and return an initialised DatabaseManager (caller must close)."""
    from database.database_manager import DatabaseManager
    db = DatabaseManager(
        db_path=settings.db_path,
        history_dir=settings.history_dir,
    )
    db.init_db()
    return db


def _assert_run_exists(db, run_id: str) -> None:
    """Raise 404 if *run_id* is not in the database."""
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )


def _result_to_schema(r) -> TestCaseResultSchema:
    """Convert a ``DbTestCaseResult`` dataclass to the API schema."""
    return TestCaseResultSchema(
        result_id=r.result_id,
        run_id=r.run_id,
        test_id=r.test_id,
        operation_id=r.operation_id,
        endpoint=r.endpoint,
        http_method=r.http_method,
        category=r.category,
        request_url=r.request_url,
        request_headers=r.request_headers,
        request_payload=r.request_payload,
        response_status_code=r.response_status_code,
        response_headers=r.response_headers,
        response_body=r.response_body,
        response_time_ms=r.response_time_ms,
        validation_status=r.validation_status,
        failure_reason=r.failure_reason,
        validation_time_ms=r.validation_time_ms,
        executed_at=r.executed_at,
    )


def _detail_to_schema(d) -> ValidationDetailSchema:
    """Convert a ``DbValidationDetail`` to the API schema."""
    return ValidationDetailSchema(
        validation_detail_id=d.validation_detail_id,
        validator_name=d.validator_name,
        status=d.status,
        message=d.message,
        severity=d.severity,
        execution_time_ms=d.execution_time_ms,
        recorded_at=d.recorded_at,
    )


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/results/summary
# IMPORTANT: must be declared BEFORE /{result_id} to avoid path clash
# ---------------------------------------------------------------------------

@router.get(
    "/api/runs/{run_id}/results/summary",
    response_model=ResultsSummaryResponse,
    summary="Aggregated test-results breakdown for a run",
    description=(
        "Returns pass/fail counts broken down by endpoint, HTTP method, "
        "test-case category, and validation status.\n\n"
        "Use this instead of fetching all individual results when you only "
        "need high-level statistics."
    ),
)
def get_results_summary(
    run_id: str,
    settings: Settings = Depends(get_settings),
) -> ResultsSummaryResponse:
    db = _get_db(settings)
    try:
        _assert_run_exists(db, run_id)
        results = db.get_test_results(run_id)
    finally:
        db.close()

    # ── Aggregate ──────────────────────────────────────────────────────
    total = len(results)
    status_counts: dict = defaultdict(int)
    method_counts: dict = defaultdict(int)

    # endpoint key → [total, passed, failed, skipped, errors, rt_list]
    ep_map: dict = defaultdict(lambda: [0, 0, 0, 0, 0, []])
    cat_map: dict = defaultdict(lambda: [0, 0, 0])   # total, passed, failed

    for r in results:
        vs = r.validation_status or "unknown"
        status_counts[vs] += 1
        method_counts[r.http_method.upper()] += 1

        ep_key = (r.endpoint, r.http_method.upper())
        ep_map[ep_key][0] += 1   # total
        if vs == "passed":
            ep_map[ep_key][1] += 1
        elif vs == "failed":
            ep_map[ep_key][2] += 1
        elif vs == "skipped":
            ep_map[ep_key][3] += 1
        else:
            ep_map[ep_key][4] += 1
        if r.response_time_ms is not None:
            ep_map[ep_key][5].append(r.response_time_ms)

        cat = r.category or "uncategorised"
        cat_map[cat][0] += 1
        if vs == "passed":
            cat_map[cat][1] += 1
        elif vs == "failed":
            cat_map[cat][2] += 1

    by_endpoint = []
    for (ep, method), (tot, pas, fail, skip, err, rt_list) in sorted(ep_map.items()):
        avg_rt = round(sum(rt_list) / len(rt_list), 2) if rt_list else None
        by_endpoint.append(EndpointSummaryRow(
            endpoint=ep,
            http_method=method,
            total=tot,
            passed=pas,
            failed=fail,
            skipped=skip,
            errors=err,
            pass_rate=round(pas / tot * 100, 1) if tot else 0.0,
            avg_response_time_ms=avg_rt,
        ))

    by_category = []
    for cat, (tot, pas, fail) in sorted(cat_map.items()):
        by_category.append(CategorySummaryRow(
            category=cat,
            total=tot,
            passed=pas,
            failed=fail,
            pass_rate=round(pas / tot * 100, 1) if tot else 0.0,
        ))

    passed = status_counts.get("passed", 0)
    failed = status_counts.get("failed", 0)
    skipped = status_counts.get("skipped", 0)
    errors = status_counts.get("error", 0) + status_counts.get("errors", 0)

    return ResultsSummaryResponse(
        run_id=run_id,
        total_results=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=errors,
        pass_rate=round(passed / total * 100, 1) if total else 0.0,
        by_endpoint=by_endpoint,
        by_category=by_category,
        by_status=dict(status_counts),
        by_http_method=dict(method_counts),
    )


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/results
# ---------------------------------------------------------------------------

@router.get(
    "/api/runs/{run_id}/results",
    response_model=TestCaseResultListResponse,
    summary="List and filter test-case results for a run",
    description=(
        "Returns a **paginated, filterable** list of individual test-case "
        "results for the given run.\n\n"
        "**Available filters:**\n"
        "- ``status``       — ``passed`` | ``failed`` | ``skipped`` | ``error``\n"
        "- ``endpoint``     — partial path match, e.g. ``/pet``\n"
        "- ``operation_id`` — exact operation ID from the spec\n"
        "- ``http_method``  — ``GET`` | ``POST`` | ``PUT`` | ``DELETE`` | …\n"
        "- ``category``     — ``positive`` | ``negative`` | ``boundary`` | ``security``\n\n"
        "Combine any filters freely.  Filters are **AND**-ed together."
    ),
)
def list_results(
    run_id: str,
    # Filters
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Validation status: passed | failed | skipped | error",
    ),
    endpoint: Optional[str] = Query(
        default=None,
        description="Partial endpoint path filter (case-insensitive contains match).",
    ),
    operation_id: Optional[str] = Query(
        default=None,
        description="Exact operation_id from the API spec.",
    ),
    http_method: Optional[str] = Query(
        default=None,
        description="HTTP method filter: GET, POST, PUT, DELETE, PATCH, …",
    ),
    category: Optional[str] = Query(
        default=None,
        description="Test category: positive | negative | boundary | security",
    ),
    # Pagination
    page: int = Query(default=1, ge=1, description="Page number (1-based)."),
    page_size: int = Query(default=50, ge=1, le=500, description="Results per page."),
    # Sorting
    sort_by: str = Query(
        default="executed_at",
        description="Field to sort by: executed_at | response_time_ms | validation_status | endpoint",
    ),
    sort_order: str = Query(
        default="asc",
        description="Sort direction: asc | desc",
    ),
    settings: Settings = Depends(get_settings),
) -> TestCaseResultListResponse:
    db = _get_db(settings)
    try:
        _assert_run_exists(db, run_id)

        # Fetch via repository search — always scoped to this run
        all_results = db.search_test_results(
            run_id=run_id,
            operation_id=operation_id,
            endpoint=endpoint,
            status=status_filter,
            limit=10_000,    # fetch all matching, paginate in Python
        )
    finally:
        db.close()

    # ── Apply additional in-Python filters not covered by the repository ─
    if http_method:
        all_results = [
            r for r in all_results
            if r.http_method.upper() == http_method.upper()
        ]
    if category:
        all_results = [
            r for r in all_results
            if (r.category or "").lower() == category.lower()
        ]

    # ── Sort ──────────────────────────────────────────────────────────
    _SORTABLE = {
        "executed_at":       lambda r: r.executed_at or "",
        "response_time_ms":  lambda r: r.response_time_ms or 0.0,
        "validation_status": lambda r: r.validation_status or "",
        "endpoint":          lambda r: r.endpoint or "",
    }
    key_fn = _SORTABLE.get(sort_by, _SORTABLE["executed_at"])
    reverse = sort_order.lower() == "desc"
    all_results.sort(key=key_fn, reverse=reverse)

    # ── Paginate ──────────────────────────────────────────────────────
    total = len(all_results)
    start = (page - 1) * page_size
    end = start + page_size
    page_results = all_results[start:end]
    has_next = end < total

    return TestCaseResultListResponse(
        run_id=run_id,
        total=total,
        page=page,
        page_size=page_size,
        has_next=has_next,
        results=[_result_to_schema(r) for r in page_results],
    )


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/results/{result_id}
# ---------------------------------------------------------------------------

@router.get(
    "/api/runs/{run_id}/results/{result_id}",
    response_model=TestCaseResultSchema,
    summary="Get full detail for a single test-case result",
    description=(
        "Returns a single test-case result **including all per-validator "
        "assertion details** from the ``validation_details`` table.\n\n"
        "The ``validation_details`` list shows which validators ran "
        "(status code, headers, response time, JSON schema, etc.) and "
        "whether each passed or failed."
    ),
)
def get_result(
    run_id: str,
    result_id: str,
    settings: Settings = Depends(get_settings),
) -> TestCaseResultSchema:
    db = _get_db(settings)
    try:
        _assert_run_exists(db, run_id)

        # Fetch the specific result — search by result_id scoped to run_id
        matches = db.search_test_results(run_id=run_id, limit=10_000)
        target = next((r for r in matches if r.result_id == result_id), None)

        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Result '{result_id}' not found in run '{run_id}'.",
            )

        # Fetch validation details for this result
        from database.repository import ValidationRepository
        from database.sqlite_manager import SQLiteManager

        sqlite = SQLiteManager(settings.db_path)
        sqlite.connect()
        try:
            val_repo = ValidationRepository(sqlite)
            details = val_repo.get_by_result(result_id)
        finally:
            sqlite.close()

    finally:
        db.close()

    result_schema = _result_to_schema(target)
    result_schema.validation_details = [_detail_to_schema(d) for d in details]
    return result_schema
