"""
web_dashboard/backend/routers/runs.py
=======================================
Execution and run-history endpoints.

    POST /api/run              — run the full Phases 2–8 pipeline
    GET  /api/runs             — paginated execution history
    GET  /api/runs/{run_id}    — full detail for one run
"""

import time
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from web_dashboard.backend.config.settings import Settings, get_settings
from web_dashboard.backend.schemas.runs import (
    RunDetailResponse,
    RunListResponse,
    RunRequest,
    RunResponse,
    RunSummary,
    ValidatorStat,
    ValidationSummarySchema,
)

router = APIRouter(tags=["Execution"])

import sys as _sys
_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _root not in _sys.path:
    _sys.path.insert(0, _root)

from utilities.logger import get_logger
logger = get_logger("web_dashboard.backend.runs")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_to_summary(run) -> RunSummary:
    """Convert a DbExecutionRun dataclass to a RunSummary schema."""
    return RunSummary(
        run_id=run.run_id,
        api_name=run.api_name,
        api_version=run.api_version,
        environment=run.environment_name,
        execution_timestamp=run.execution_timestamp,
        total_endpoints=run.total_endpoints or 0,
        total_test_cases=run.total_test_cases or 0,
        total_executed=run.total_executed or 0,
        passed=run.passed or 0,
        failed=run.failed or 0,
        skipped=run.skipped or 0,
        errors=run.errors or 0,
        pass_percentage=run.pass_percentage or 0.0,
        avg_response_time_ms=run.avg_response_time_ms,
        total_execution_time_s=run.total_execution_time_s,
        health_score=None,       # filled in detail view via analytics
        health_rating=None,
        specification_file=run.specification_file,
        framework_version=run.framework_version,
    )


def _get_db(settings: Settings):
    from database.database_manager import DatabaseManager
    db = DatabaseManager(
        db_path=settings.db_path,
        history_dir=settings.history_dir,
    )
    db.init_db()
    return db


# ---------------------------------------------------------------------------
# POST /api/run
# ---------------------------------------------------------------------------

@router.post(
    "/api/run",
    response_model=RunResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute the full test pipeline",
    description=(
        "Runs Phases 2–8 (Parse → Generate → Execute → Validate → "
        "Persist → Analytics → Report) for the specified spec file.\n\n"
        "**This is a synchronous blocking call.**  For large specs it may "
        "take 30–120 seconds.  An async job queue will be added in Phase 9.3."
    ),
)
def execute_pipeline(
    req: RunRequest,
    settings: Settings = Depends(get_settings),
) -> RunResponse:
    specs_dir = settings.project_root / "uploaded_specs"
    spec_path = specs_dir / Path(req.specification_filename).name

    if not spec_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Specification file '{req.specification_filename}' not found in uploaded_specs/.",
        )

    logger.info(
        "Pipeline triggered: spec='%s' env='%s'",
        req.specification_filename, req.environment,
    )

    t_start = time.monotonic()

    try:
        # ── Load config and override environment if requested ─────────
        from configs.config_loader import Config
        cfg = Config()

        try:
            env_cfg = cfg.get_environment(req.environment)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Environment '{req.environment}' not found. "
                    f"Available: {cfg.list_environments()}"
                ),
            )

        if req.base_url_override:
            env_cfg.base_url = req.base_url_override.rstrip("/")

        # ── Phase 2: Parse ────────────────────────────────────────────
        from api_parser import ParserManager
        spec = ParserManager().parse(str(spec_path))

        # If env has no base_url, fall back to spec's base_url
        if not env_cfg.base_url and spec.base_url:
            env_cfg.base_url = spec.base_url

        if not env_cfg.base_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No base_url available. Set one in environments.yaml "
                    "or provide base_url_override in the request."
                ),
            )

        # ── Phase 3: Generate ─────────────────────────────────────────
        from testcase_generator import GeneratorManager
        test_cases = GeneratorManager().generate(spec, env_cfg)

        # ── Phase 4: Execute ──────────────────────────────────────────
        from executor import ExecutionManager
        with ExecutionManager(
            environment_config=env_cfg,
            timeout=req.timeout_seconds,
            verify_ssl=req.verify_ssl,
        ) as exec_mgr:
            exec_results = exec_mgr.run(test_cases, spec_title=spec.title)

        # ── Phase 5: Validate ─────────────────────────────────────────
        from validators import ValidationManager
        val_results = ValidationManager().validate_all(
            test_cases=test_cases,
            execution_results=exec_results,
            spec_title=spec.title,
        )

        # ── Phase 6: Persist ──────────────────────────────────────────
        total_time = time.monotonic() - t_start
        db = _get_db(settings)
        try:
            run_id = db.save_run(
                spec=spec,
                test_cases=test_cases,
                exec_results=exec_results,
                val_results=val_results,
                config=cfg,
                total_execution_time_s=total_time,
            )
            run_row = db.get_run(run_id)
        finally:
            db.close()

        # ── Phase 7: Analytics (read-only re-open) ────────────────────
        health_score = None
        health_rating = None
        try:
            from analytics import AnalyticsManager
            db2 = _get_db(settings)
            try:
                summary = AnalyticsManager(db2).run_analysis(run_id)
                if summary.health:
                    health_score = summary.health.score
                    health_rating = summary.health.rating
            finally:
                db2.close()
        except Exception as exc:
            logger.warning("Analytics failed for run '%s': %s", run_id[:16], exc)

        # ── Phase 8: Reports ──────────────────────────────────────────
        report_paths: List[str] = []
        if req.generate_reports:
            try:
                from reporting import ReportManager
                from analytics import AnalyticsManager as AM
                db3 = _get_db(settings)
                try:
                    am = AM(db3)
                    reporter = ReportManager(
                        db_manager=db3,
                        analytics_manager=am,
                        output_dir=Path(settings.reports_dir),
                    )
                    paths = reporter.generate_report(run_id)
                    report_paths = [p.name for p in paths if p.exists()]
                finally:
                    db3.close()
            except Exception as exc:
                logger.warning("Reporting failed for run '%s': %s", run_id[:16], exc)

        run_summary = _run_to_summary(run_row)
        run_summary.health_score = health_score
        run_summary.health_rating = health_rating

        logger.info(
            "Pipeline complete: run_id='%s'  passed=%d  failed=%d  time=%.1fs",
            run_id[:16],
            run_row.passed,
            run_row.failed,
            total_time,
        )

        return RunResponse(
            run_id=run_id,
            status="completed",
            api_name=spec.title,
            summary=run_summary,
            report_paths=report_paths,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Pipeline error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution failed: {exc}",
        )


# ---------------------------------------------------------------------------
# GET /api/runs
# ---------------------------------------------------------------------------

@router.get(
    "/api/runs",
    response_model=RunListResponse,
    summary="List execution history",
    description="Returns paginated execution runs, newest first.",
)
def list_runs(
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Results per page"),
    api_name: Optional[str] = Query(default=None, description="Filter by API name"),
    environment: Optional[str] = Query(default=None, description="Filter by environment"),
    settings: Settings = Depends(get_settings),
) -> RunListResponse:
    db = _get_db(settings)
    try:
        if api_name or environment:
            all_runs = db.search_runs(
                api_name=api_name,
                environment=environment,
                limit=page_size * page + 1,   # fetch one extra to detect has_next
            )
        else:
            all_runs = db.list_runs(limit=page_size * page + 1)
    finally:
        db.close()

    total_fetched = len(all_runs)
    has_next = total_fetched > page_size * page
    page_runs = all_runs[(page - 1) * page_size : page * page_size]

    return RunListResponse(
        total=total_fetched if not has_next else total_fetched - 1,
        page=page,
        page_size=page_size,
        has_next=has_next,
        runs=[_run_to_summary(r) for r in page_runs],
    )


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}
# ---------------------------------------------------------------------------

@router.get(
    "/api/runs/{run_id}",
    response_model=RunDetailResponse,
    summary="Get full details for one execution run",
)
def get_run(
    run_id: str,
    settings: Settings = Depends(get_settings),
) -> RunDetailResponse:
    db = _get_db(settings)
    try:
        run_row = db.get_run(run_id)
        if run_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_id}' not found.",
            )
        val_details = db.get_validation_details(run_id)
    finally:
        db.close()

    # Build validation summary from detail rows
    from collections import defaultdict
    passed_by: dict = defaultdict(int)
    failed_by: dict = defaultdict(int)
    for d in val_details:
        if d.status == "passed":
            passed_by[d.validator_name] += 1
        else:
            failed_by[d.validator_name] += 1

    all_names = sorted(set(list(passed_by) + list(failed_by)))
    v_rows = []
    for name in all_names:
        p = passed_by.get(name, 0)
        f = failed_by.get(name, 0)
        total = p + f
        v_rows.append(ValidatorStat(
            validator_name=name,
            passed=p, failed=f, total=total,
            pass_rate=round(p / total * 100, 1) if total else 0.0,
        ))

    tp = sum(passed_by.values())
    tf = sum(failed_by.values())
    val_summary = ValidationSummarySchema(
        validators=v_rows,
        total_assertions=tp + tf,
        total_passed=tp,
        total_failed=tf,
    )

    # Collect report links
    reports_dir = Path(settings.reports_dir)
    report_links: List[str] = []
    if reports_dir.exists():
        for f in sorted(reports_dir.iterdir()):
            if f.is_file() and f.suffix in {".html", ".pdf", ".csv", ".json"}:
                report_links.append(f"/api/reports/{run_id}/download/{f.name}")

    run_summary = _run_to_summary(run_row)
    return RunDetailResponse(
        run=run_summary,
        validation_summary=val_summary,
        report_links=report_links,
    )
