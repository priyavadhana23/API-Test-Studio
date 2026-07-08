"""
web_dashboard/backend/routers/analytics.py
===========================================
Analytics endpoints.

    GET /api/analytics/{run_id}   — full AnalyticsSummary for one run
    GET /api/analytics             — latest run analytics (convenience)
"""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status

from web_dashboard.backend.config.settings import Settings, get_settings
from web_dashboard.backend.schemas.analytics import AnalyticsSummarySchema

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

import sys as _sys
_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _root not in _sys.path:
    _sys.path.insert(0, _root)

from utilities.logger import get_logger
logger = get_logger("web_dashboard.backend.analytics")


def _to_schema(summary) -> AnalyticsSummarySchema:
    """Convert an AnalyticsSummary dataclass to the Pydantic schema."""
    from web_dashboard.backend.schemas.analytics import (
        TrendResultSchema, TrendPointSchema,
        EndpointAnalysisSchema, EndpointStatsSchema,
        ResponseTimeSchema, FailureAnalysisSchema, FailureEntrySchema,
        RegressionSchema, HealthSchema,
    )

    def _trend(t):
        if not t:
            return None
        return TrendResultSchema(
            name=t.name,
            points=[TrendPointSchema(label=p.label, value=p.value, run_count=p.run_count)
                    for p in (t.points or [])],
            slope=t.slope,
            direction=t.direction,
            moving_avg=t.moving_avg or [],
        )

    def _endpoint_analysis(ea):
        if not ea:
            return None
        stats = [
            EndpointStatsSchema(
                endpoint=s.endpoint, method=s.method,
                total_executions=s.total_executions,
                passed=s.passed, failed=s.failed, errors=s.errors,
                pass_rate=s.pass_rate,
                avg_response_time_ms=s.avg_response_time_ms,
                min_response_time_ms=s.min_response_time_ms,
                max_response_time_ms=s.max_response_time_ms,
                p95_response_time_ms=s.p95_response_time_ms,
            )
            for s in (ea.all_stats or [])
        ]
        return EndpointAnalysisSchema(
            most_executed=ea.most_executed,
            least_executed=ea.least_executed,
            most_failed=ea.most_failed,
            most_successful=ea.most_successful,
            slowest=ea.slowest,
            fastest=ea.fastest,
            avg_execution_count=ea.avg_execution_count,
            all_stats=stats,
        )

    def _rt(rt):
        if not rt:
            return None
        return ResponseTimeSchema(
            sample_count=rt.sample_count,
            mean_ms=rt.mean_ms, median_ms=rt.median_ms,
            min_ms=rt.min_ms, max_ms=rt.max_ms,
            std_dev_ms=rt.std_dev_ms,
            p95_ms=rt.p95_ms, p99_ms=rt.p99_ms,
            sla_threshold_ms=rt.sla_threshold_ms,
            sla_compliance_pct=rt.sla_compliance_pct,
        )

    def _failure(fa):
        if not fa:
            return None
        def _entries(lst):
            return [FailureEntrySchema(
                category=e.category, count=e.count,
                percentage=e.percentage, sample_message=e.sample_message,
            ) for e in (lst or [])]
        return FailureAnalysisSchema(
            total_failures=fa.total_failures,
            validation_failures=fa.validation_failures,
            execution_errors=fa.execution_errors,
            timeout_failures=fa.timeout_failures,
            auth_failures=fa.auth_failures,
            schema_failures=fa.schema_failures,
            business_rule_failures=fa.business_rule_failures,
            top_failures=_entries(fa.top_failures),
            distribution=_entries(fa.distribution),
        )

    def _regression(reg):
        if not reg:
            return None
        return RegressionSchema(
            run_id_baseline=reg.run_id_baseline,
            run_id_current=reg.run_id_current,
            api_name=reg.api_name,
            new_failures=reg.new_failures or [],
            fixed_failures=reg.fixed_failures or [],
            unchanged_failures=reg.unchanged_failures or [],
            pass_rate_delta=reg.pass_rate_delta,
            avg_rt_delta_ms=reg.avg_rt_delta_ms,
            has_regression=reg.has_regression,
            verdict=reg.verdict,
        )

    def _health(h):
        if not h:
            return None
        return HealthSchema(
            score=h.score, rating=h.rating,
            pass_rate_score=h.pass_rate_score,
            response_time_score=h.response_time_score,
            stability_score=h.stability_score,
            availability_score=h.availability_score,
            recommendations=h.recommendations or [],
        )

    return AnalyticsSummarySchema(
        run_id=summary.run_id,
        api_name=summary.api_name,
        total_runs=summary.total_runs,
        generated_at=summary.generated_at,
        trend=_trend(summary.trend),
        endpoint_analysis=_endpoint_analysis(summary.endpoint_analysis),
        response_time=_rt(summary.response_time),
        failure_analysis=_failure(summary.failure_analysis),
        regression=_regression(summary.regression),
        health=_health(summary.health),
    )


def _open_db(settings: Settings):
    from database.database_manager import DatabaseManager
    db = DatabaseManager(db_path=settings.db_path, history_dir=settings.history_dir)
    db.init_db()
    return db


# ---------------------------------------------------------------------------
# GET /api/analytics  (latest run)
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=AnalyticsSummarySchema,
    summary="Analytics for the most recent run",
)
def analytics_latest(settings: Settings = Depends(get_settings)) -> AnalyticsSummarySchema:
    db = _open_db(settings)
    try:
        run = db.latest_run()
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No execution runs found in the database.",
            )
        from analytics import AnalyticsManager
        summary = AnalyticsManager(db).run_analysis(run.run_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Analytics (latest) error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()
    return _to_schema(summary)


# ---------------------------------------------------------------------------
# GET /api/analytics/{run_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{run_id}",
    response_model=AnalyticsSummarySchema,
    summary="Analytics for a specific run",
)
def analytics_for_run(
    run_id: str,
    settings: Settings = Depends(get_settings),
) -> AnalyticsSummarySchema:
    db = _open_db(settings)
    try:
        if db.get_run(run_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_id}' not found.",
            )
        from analytics import AnalyticsManager
        summary = AnalyticsManager(db).run_analysis(run_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Analytics error for run '%s': %s", run_id[:16], exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()
    return _to_schema(summary)
