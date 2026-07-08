"""
web_dashboard/backend/services/job_store.py
============================================
In-memory job store for async pipeline execution (Phase 9.3).

Design
------
* A single process-wide ``JobStore`` singleton holds all job state in a
  plain ``dict`` guarded by a ``threading.Lock``.  No external broker
  (Redis, RQ, Celery) is required — everything lives in the FastAPI
  process via Python's ``concurrent.futures.ThreadPoolExecutor``.
* Each job is represented by a ``Job`` dataclass that carries its full
  lifecycle: pending → running → completed | failed.
* Progress is updated in-place by the background worker so polling
  clients see incremental updates without websockets.

Thread safety
-------------
All mutations go through ``JobStore._lock``.  Readers call
``get_job()`` / ``list_jobs()`` which take a brief snapshot under the
lock.

Retention
---------
``JobStore.prune()`` removes jobs older than ``max_age_seconds``
(default 24 h).  It is called automatically on every ``create_job()``
so the dict never grows unboundedly during normal use.

Usage
-----
    from web_dashboard.backend.services.job_store import get_job_store

    store = get_job_store()
    job   = store.create_job(spec_filename="petstore.yaml", environment="dev")
    # hand job.job_id to the caller, run the pipeline in background
    store.set_running(job.job_id)
    store.set_progress(job.job_id, step="Generating test cases", percent=30)
    store.complete(job.job_id, run_id="run_abc123", report_paths=["r.html"])
    # or
    store.fail(job.job_id, error="Connection refused")
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Job dataclass
# ---------------------------------------------------------------------------

@dataclass
class Job:
    """
    Represents one async pipeline execution job.

    Attributes:
        job_id:          UUID string, globally unique.
        spec_filename:   The spec filename passed by the caller.
        environment:     The environment key.
        status:          One of ``pending | running | completed | failed``.
        step:            Human-readable current phase description.
        percent:         0–100 progress indicator.
        run_id:          Populated on completion; the persisted run identifier.
        report_paths:    List of generated report filenames (on completion).
        error:           Error message if the job failed.
        created_at:      ISO-8601 UTC creation timestamp.
        started_at:      ISO-8601 UTC timestamp when execution began.
        completed_at:    ISO-8601 UTC timestamp when execution finished.
        elapsed_s:       Wall-clock seconds from start to finish.
    """
    job_id: str
    spec_filename: str
    environment: str

    status: str = "pending"          # pending | running | completed | failed
    step: str = "Queued"
    percent: int = 0

    run_id: Optional[str] = None
    report_paths: List[str] = field(default_factory=list)
    error: Optional[str] = None

    created_at: str = field(default_factory=lambda: _now_iso())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_s: Optional[float] = None

    # internal monotonic start time — not serialised
    _started_mono: Optional[float] = field(default=None, repr=False, compare=False)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# JobStore
# ---------------------------------------------------------------------------

class JobStore:
    """
    Thread-safe in-memory store for Job objects.

    Do not instantiate directly — use ``get_job_store()`` to obtain the
    process-wide singleton.
    """

    _DEFAULT_MAX_AGE_S: float = 86_400   # 24 hours

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    # ── Creation ────────────────────────────────────────────────────────

    def create_job(
        self,
        spec_filename: str,
        environment: str = "development",
        *,
        max_age_seconds: float = _DEFAULT_MAX_AGE_S,
    ) -> Job:
        """
        Create a new job in ``pending`` status and return it.

        Args:
            spec_filename:    Spec file name (not full path).
            environment:      Environment key.
            max_age_seconds:  Prune jobs older than this before inserting.

        Returns:
            The newly created ``Job`` instance.
        """
        self.prune(max_age_seconds=max_age_seconds)
        job = Job(
            job_id=str(uuid.uuid4()),
            spec_filename=spec_filename,
            environment=environment,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    # ── State transitions ────────────────────────────────────────────────

    def set_running(self, job_id: str) -> None:
        """Transition job to ``running`` and record start time."""
        import time
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "running"
                job.step = "Starting pipeline"
                job.percent = 0
                job.started_at = _now_iso()
                job._started_mono = time.monotonic()

    def set_progress(self, job_id: str, step: str, percent: int) -> None:
        """
        Update the ``step`` label and ``percent`` for a running job.

        Args:
            job_id:   Target job identifier.
            step:     Human-readable current-phase label, e.g. ``"Parsing spec"``.
            percent:  Integer 0–100 completion estimate.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.step = step
                job.percent = max(0, min(100, percent))

    def complete(
        self,
        job_id: str,
        run_id: str,
        report_paths: Optional[List[str]] = None,
    ) -> None:
        """
        Mark the job ``completed``.

        Args:
            job_id:        Target job identifier.
            run_id:        The database run ID returned by Phase 6.
            report_paths:  List of generated report file names.
        """
        import time
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "completed"
                job.step = "Done"
                job.percent = 100
                job.run_id = run_id
                job.report_paths = report_paths or []
                job.completed_at = _now_iso()
                if job._started_mono is not None:
                    job.elapsed_s = round(time.monotonic() - job._started_mono, 2)

    def fail(self, job_id: str, error: str) -> None:
        """
        Mark the job ``failed``.

        Args:
            job_id:  Target job identifier.
            error:   Exception message or human-readable failure reason.
        """
        import time
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "failed"
                job.step = "Failed"
                job.error = error
                job.completed_at = _now_iso()
                if job._started_mono is not None:
                    job.elapsed_s = round(time.monotonic() - job._started_mono, 2)

    # ── Queries ──────────────────────────────────────────────────────────

    def get_job(self, job_id: str) -> Optional[Job]:
        """Return the job with *job_id*, or ``None`` if not found."""
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Job]:
        """
        Return jobs sorted by ``created_at`` descending.

        Args:
            status: If given, filter to only jobs with that status.
            limit:  Maximum number of jobs to return.

        Returns:
            List of ``Job`` snapshots (the actual mutable objects —
            callers should not mutate them).
        """
        with self._lock:
            jobs = list(self._jobs.values())

        jobs.sort(key=lambda j: j.created_at, reverse=True)
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs[:limit]

    def count(self) -> int:
        """Return the total number of tracked jobs."""
        with self._lock:
            return len(self._jobs)

    # ── Maintenance ───────────────────────────────────────────────────────

    def prune(self, max_age_seconds: float = _DEFAULT_MAX_AGE_S) -> int:
        """
        Remove completed or failed jobs older than *max_age_seconds*.

        Running/pending jobs are never pruned.

        Returns:
            Number of jobs removed.
        """
        from datetime import timedelta
        cutoff = datetime.now(tz=timezone.utc) - timedelta(seconds=max_age_seconds)
        to_remove: List[str] = []
        with self._lock:
            for jid, job in self._jobs.items():
                if job.status in ("completed", "failed"):
                    try:
                        ts = datetime.fromisoformat(job.completed_at)
                        # ensure tz-aware comparison
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        if ts < cutoff:
                            to_remove.append(jid)
                    except (TypeError, ValueError):
                        pass
            for jid in to_remove:
                del self._jobs[jid]
        return len(to_remove)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_job_store() -> JobStore:
    """Return the process-wide ``JobStore`` singleton."""
    return JobStore()
