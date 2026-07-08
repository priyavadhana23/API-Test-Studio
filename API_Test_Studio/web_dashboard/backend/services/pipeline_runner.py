"""
web_dashboard/backend/services/pipeline_runner.py
===================================================
Background pipeline worker for Phase 9.3.

``run_pipeline_job()`` is designed to be submitted to a
``concurrent.futures.ThreadPoolExecutor``.  It:

1. Marks the job ``running``.
2. Runs Phases 2–8 (Parse → Generate → Execute → Validate → Persist →
   Analytics → Reports), updating progress after each phase.
3. On success marks the job ``completed`` with the persisted ``run_id``.
4. On any exception marks the job ``failed`` with the error message.

The function never raises — all exceptions are swallowed and stored in
the job so HTTP polling can surface them cleanly.

Usage (from a router)::

    from concurrent.futures import ThreadPoolExecutor
    from web_dashboard.backend.services.pipeline_runner import run_pipeline_job
    from web_dashboard.backend.services.job_store import get_job_store

    _executor = ThreadPoolExecutor(max_workers=4)

    @router.post("/api/jobs")
    def submit(req: JobRequest, settings: Settings = Depends(get_settings)):
        job = get_job_store().create_job(req.specification_filename, req.environment)
        _executor.submit(run_pipeline_job, job.job_id, req, settings)
        return {"job_id": job.job_id, "status": "pending"}
"""

from pathlib import Path
from typing import List, Optional

from utilities.logger import get_logger

logger = get_logger("web_dashboard.backend.pipeline_runner")


def run_pipeline_job(
    job_id: str,
    spec_filename: str,
    environment: str,
    base_url_override: Optional[str],
    timeout_seconds: int,
    verify_ssl: bool,
    generate_reports: bool,
    db_path: str,
    history_dir: str,
    reports_dir: str,
    project_root: Path,
) -> None:
    """
    Execute the full Phases 2–8 pipeline in a background thread.

    All parameters are plain scalars / paths — no FastAPI objects —
    so this function is safe to run inside ``ThreadPoolExecutor`` without
    any async event-loop concerns.

    Args:
        job_id:             ID of the ``Job`` to update during execution.
        spec_filename:      Filename inside ``uploaded_specs/``.
        environment:        Environment key from ``environments.yaml``.
        base_url_override:  Optional base URL override.
        timeout_seconds:    Per-request HTTP timeout.
        verify_ssl:         Whether to verify TLS certs.
        generate_reports:   Whether to run Phase 8.
        db_path:            Absolute path to the SQLite database file.
        history_dir:        Absolute path to the history directory.
        reports_dir:        Absolute path to the reports directory.
        project_root:       ``Path`` to the ``API_Test_Studio/`` directory.
    """
    import sys
    import time

    root_str = str(project_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    from web_dashboard.backend.services.job_store import get_job_store
    store = get_job_store()

    store.set_running(job_id)
    t_start = time.monotonic()

    try:
        # ── Resolve spec path ─────────────────────────────────────────
        specs_dir = project_root / "uploaded_specs"
        spec_path = specs_dir / Path(spec_filename).name
        if not spec_path.exists():
            raise FileNotFoundError(
                f"Specification file '{spec_filename}' not found in uploaded_specs/."
            )

        # ── Load config ───────────────────────────────────────────────
        store.set_progress(job_id, "Loading configuration", 5)
        from configs.config_loader import Config
        cfg = Config()

        try:
            env_cfg = cfg.get_environment(environment)
        except KeyError:
            raise ValueError(
                f"Environment '{environment}' not found. "
                f"Available: {cfg.list_environments()}"
            )

        if base_url_override:
            env_cfg.base_url = base_url_override.rstrip("/")

        # ── Phase 2: Parse ────────────────────────────────────────────
        store.set_progress(job_id, "Parsing API specification", 10)
        from api_parser import ParserManager
        spec = ParserManager().parse(str(spec_path))

        if not env_cfg.base_url and spec.base_url:
            env_cfg.base_url = spec.base_url

        if not env_cfg.base_url:
            raise ValueError(
                "No base_url available. Set one in environments.yaml "
                "or provide base_url_override in the request."
            )

        logger.info(
            "[job:%s] Parsed spec '%s' — %d endpoint(s).",
            job_id[:8], spec.title, len(spec.endpoints),
        )

        # ── Phase 3: Generate ─────────────────────────────────────────
        store.set_progress(job_id, "Generating test cases", 20)
        from testcase_generator import GeneratorManager
        test_cases = GeneratorManager().generate(spec, env_cfg)

        logger.info(
            "[job:%s] Generated %d test case(s).", job_id[:8], len(test_cases)
        )

        # ── Phase 4: Execute ──────────────────────────────────────────
        store.set_progress(job_id, "Executing HTTP requests", 35)
        from executor import ExecutionManager
        with ExecutionManager(
            environment_config=env_cfg,
            timeout=timeout_seconds,
            verify_ssl=verify_ssl,
        ) as exec_mgr:
            exec_results = exec_mgr.run(test_cases, spec_title=spec.title)

        logger.info(
            "[job:%s] Execution complete — %d result(s).",
            job_id[:8], len(exec_results),
        )

        # ── Phase 5: Validate ─────────────────────────────────────────
        store.set_progress(job_id, "Validating responses", 60)
        from validators import ValidationManager
        val_results = ValidationManager().validate_all(
            test_cases=test_cases,
            execution_results=exec_results,
            spec_title=spec.title,
        )

        # ── Phase 6: Persist ──────────────────────────────────────────
        store.set_progress(job_id, "Persisting results", 75)
        total_time = time.monotonic() - t_start

        from database.database_manager import DatabaseManager
        db = DatabaseManager(db_path=db_path, history_dir=history_dir)
        db.init_db()
        try:
            run_id = db.save_run(
                spec=spec,
                test_cases=test_cases,
                exec_results=exec_results,
                val_results=val_results,
                config=cfg,
                total_execution_time_s=total_time,
            )
        finally:
            db.close()

        logger.info("[job:%s] Persisted as run '%s'.", job_id[:8], run_id[:16])

        # ── Phase 7: Analytics ────────────────────────────────────────
        store.set_progress(job_id, "Running analytics", 85)
        try:
            from analytics import AnalyticsManager
            db2 = DatabaseManager(db_path=db_path, history_dir=history_dir)
            db2.init_db()
            try:
                AnalyticsManager(db2).run_analysis(run_id)
            finally:
                db2.close()
        except Exception as exc:
            logger.warning(
                "[job:%s] Analytics phase failed (non-fatal): %s", job_id[:8], exc
            )

        # ── Phase 8: Reports ──────────────────────────────────────────
        report_paths: List[str] = []
        if generate_reports:
            store.set_progress(job_id, "Generating reports", 92)
            try:
                from reporting import ReportManager
                from analytics import AnalyticsManager as AM
                db3 = DatabaseManager(db_path=db_path, history_dir=history_dir)
                db3.init_db()
                try:
                    am = AM(db3)
                    reporter = ReportManager(
                        db_manager=db3,
                        analytics_manager=am,
                        output_dir=Path(reports_dir),
                    )
                    paths = reporter.generate_report(run_id)
                    report_paths = [p.name for p in paths if p.exists()]
                finally:
                    db3.close()
            except Exception as exc:
                logger.warning(
                    "[job:%s] Reporting phase failed (non-fatal): %s", job_id[:8], exc
                )

        # ── Done ──────────────────────────────────────────────────────
        store.complete(job_id, run_id=run_id, report_paths=report_paths)
        logger.info(
            "[job:%s] Pipeline complete in %.1fs. run_id=%s",
            job_id[:8], time.monotonic() - t_start, run_id[:16],
        )

    except Exception as exc:
        logger.error(
            "[job:%s] Pipeline failed: %s", job_id[:8], exc, exc_info=True
        )
        store.fail(job_id, error=str(exc))
