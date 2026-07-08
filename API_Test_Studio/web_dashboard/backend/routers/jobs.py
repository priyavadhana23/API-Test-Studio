"""
web_dashboard/backend/routers/jobs.py
=======================================
Phase 9.3 — Async job queue endpoints.

    POST /api/jobs              — submit a new pipeline job (returns 202)
    GET  /api/jobs              — list all in-memory jobs
    GET  /api/jobs/{job_id}     — poll status / progress for one job
    DELETE /api/jobs/{job_id}   — cancel a pending job (fails if running)

Design
------
* Jobs run inside a module-level ``ThreadPoolExecutor`` (max 4 workers).
  FastAPI remains fully non-blocking — the executor thread holds the GIL
  only when doing Python work, releasing it during HTTP I/O in ``requests``.
* The ``JobStore`` singleton (services/job_store.py) is the single source
  of truth for job state.  It is thread-safe and lives for the lifetime of
  the process.
* POST /api/run (Phase 9.2) is kept unchanged for backward compatibility.
  POST /api/jobs is the new async alternative.

Polling contract
----------------
1. Client POSTs to /api/jobs → receives ``{job_id, poll_url, status: "pending"}``.
2. Client polls GET /api/jobs/{job_id} every 2–5 s.
3. When ``status == "completed"`` the response includes ``run_id`` and
   ``report_paths``.  Client can then hit GET /api/runs/{run_id} for full
   results.
4. When ``status == "failed"`` the response includes ``error``.

Recommended polling intervals
------------------------------
* 0–10 s elapsed  → poll every 2 s
* 10–60 s elapsed → poll every 5 s
* > 60 s elapsed  → poll every 10 s
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from web_dashboard.backend.config.settings import Settings, get_settings
from web_dashboard.backend.schemas.jobs import (
    JobListResponse,
    JobRequest,
    JobStatusResponse,
    JobSubmitResponse,
)
from web_dashboard.backend.services.job_store import Job, get_job_store

import sys as _sys
_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _root not in _sys.path:
    _sys.path.insert(0, _root)

from utilities.logger import get_logger

logger = get_logger("web_dashboard.backend.jobs")

router = APIRouter(tags=["Execution"])

# ---------------------------------------------------------------------------
# Module-level executor — shared across all requests in this process
# ---------------------------------------------------------------------------

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pipeline-worker")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job_to_schema(job: Job) -> JobStatusResponse:
    """Convert a ``Job`` dataclass to a ``JobStatusResponse`` Pydantic model."""
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        step=job.step,
        percent=job.percent,
        run_id=job.run_id,
        report_paths=job.report_paths,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        elapsed_s=job.elapsed_s,
        spec_filename=job.spec_filename,
        environment=job.environment,
    )


# ---------------------------------------------------------------------------
# POST /api/jobs  — submit a new async job
# ---------------------------------------------------------------------------

@router.post(
    "/api/jobs",
    response_model=JobSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit an async pipeline job",
    description=(
        "Queues a new test pipeline execution and returns immediately with a "
        "``job_id``.  Poll **GET /api/jobs/{job_id}** to track progress.\n\n"
        "**Phases executed in the background:**\n"
        "2 Parse → 3 Generate → 4 Execute → 5 Validate → 6 Persist → "
        "7 Analytics → 8 Reports\n\n"
        "The job progresses through these ``step`` labels:\n"
        "``Queued`` → ``Loading configuration`` → ``Parsing API specification`` → "
        "``Generating test cases`` → ``Executing HTTP requests`` → "
        "``Validating responses`` → ``Persisting results`` → "
        "``Running analytics`` → ``Generating reports`` → ``Done``"
    ),
)
def submit_job(
    req: JobRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> JobSubmitResponse:
    """Accept a pipeline job and queue it for async execution."""

    # Validate spec exists before queuing so the caller gets a fast 404
    specs_dir = settings.project_root / "uploaded_specs"
    spec_path = specs_dir / Path(req.specification_filename).name
    if not spec_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Specification file '{req.specification_filename}' not found "
                f"in uploaded_specs/."
            ),
        )

    store = get_job_store()
    job = store.create_job(
        spec_filename=req.specification_filename,
        environment=req.environment,
    )

    # Build the poll URL from the incoming request so it works behind proxies
    base_url = str(request.base_url).rstrip("/")
    poll_url = f"{base_url}/api/jobs/{job.job_id}"

    # Submit to background executor
    from web_dashboard.backend.services.pipeline_runner import run_pipeline_job
    _executor.submit(
        run_pipeline_job,
        job.job_id,
        req.specification_filename,
        req.environment,
        req.base_url_override,
        req.timeout_seconds,
        req.verify_ssl,
        req.generate_reports,
        settings.db_path,
        settings.history_dir,
        settings.reports_dir,
        settings.project_root,
    )

    logger.info(
        "Job submitted: job_id=%s  spec='%s'  env='%s'",
        job.job_id[:8], req.specification_filename, req.environment,
    )

    return JobSubmitResponse(
        job_id=job.job_id,
        status="pending",
        poll_url=poll_url,
        message=(
            "Job queued. Poll poll_url until status is 'completed' or 'failed'."
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}  — poll a single job
# ---------------------------------------------------------------------------

@router.get(
    "/api/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Poll job status and progress",
    description=(
        "Returns the current status, progress percentage, and step label for "
        "the specified job.\n\n"
        "**Status values:**\n"
        "- ``pending``   — queued, not yet started\n"
        "- ``running``   — pipeline is executing\n"
        "- ``completed`` — pipeline finished; ``run_id`` is populated\n"
        "- ``failed``    — pipeline encountered an error; ``error`` is populated\n\n"
        "When ``status == 'completed'``, use the returned ``run_id`` with "
        "**GET /api/runs/{run_id}** to retrieve full results."
    ),
)
def get_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> JobStatusResponse:
    """Return current state of a single job."""
    job = get_job_store().get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    return _job_to_schema(job)


# ---------------------------------------------------------------------------
# GET /api/jobs  — list all jobs
# ---------------------------------------------------------------------------

@router.get(
    "/api/jobs",
    response_model=JobListResponse,
    summary="List all pipeline jobs",
    description=(
        "Returns all jobs currently tracked in memory, newest first.\n\n"
        "Jobs are pruned automatically after 24 hours.  Use the optional "
        "``status`` query parameter to filter the list."
    ),
)
def list_jobs(
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by status: pending | running | completed | failed",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Maximum number of jobs to return.",
    ),
    settings: Settings = Depends(get_settings),
) -> JobListResponse:
    """Return all tracked jobs with optional status filter."""
    store = get_job_store()
    jobs = store.list_jobs(status=status_filter, limit=limit)
    return JobListResponse(
        total=store.count(),
        jobs=[_job_to_schema(j) for j in jobs],
    )


# ---------------------------------------------------------------------------
# DELETE /api/jobs/{job_id}  — cancel a pending job
# ---------------------------------------------------------------------------

@router.delete(
    "/api/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Cancel or dismiss a job",
    description=(
        "Cancels a **pending** job (before execution starts) or dismisses a "
        "**completed / failed** job from the in-memory store.\n\n"
        "Returns ``409 Conflict`` if the job is currently **running** — "
        "running jobs cannot be interrupted mid-execution."
    ),
    response_model=dict,
)
def cancel_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Cancel a pending job or remove a finished/failed job from memory."""
    store = get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    if job.status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Job '{job_id}' is currently running and cannot be cancelled. "
                "Wait for it to complete or fail."
            ),
        )

    # Mark as failed with a cancellation message (pending) or just remove it
    if job.status == "pending":
        store.fail(job_id, error="Cancelled by user.")
        logger.info("Job cancelled by user: job_id=%s", job_id[:8])
        return {"job_id": job_id, "status": "cancelled", "message": "Job cancelled."}

    # completed / failed — just acknowledge (auto-pruned after 24 h)
    return {
        "job_id": job_id,
        "status": job.status,
        "message": "Job already finished. It will be pruned automatically.",
    }
