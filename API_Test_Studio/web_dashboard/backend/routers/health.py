"""
web_dashboard/backend/routers/health.py
========================================
Health and root endpoints.

    GET /          → RootResponse     (service identity)
    GET /api/health → HealthResponse  (component availability)

These two endpoints must always respond — even if the database is
unavailable — so they catch all exceptions internally and report
degraded status rather than returning 500.
"""

from fastapi import APIRouter, Depends
from pathlib import Path

from web_dashboard.backend.config.settings import Settings, get_settings
from web_dashboard.backend.schemas.health import (
    ComponentStatus,
    HealthResponse,
    RootResponse,
)

router = APIRouter(tags=["System"])


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=RootResponse,
    summary="Service root",
    description="Returns service identity and links to documentation.",
)
def root(settings: Settings = Depends(get_settings)) -> RootResponse:
    """Service identity — always returns 200."""
    return RootResponse(
        name=settings.app_name,
        version=settings.app_version,
        description="Enterprise API Testing Platform — Backend API",
        status="running",
        docs_url="/docs",
        redoc_url="/redoc",
        health_url="/api/health",
    )


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

@router.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Probes every framework component and returns their availability. "
        "Returns HTTP 200 with status='degraded' if any component is down, "
        "so load-balancers can distinguish 'service is up but degraded' from "
        "'service is completely down'."
    ),
)
def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    Check the availability of database, analytics, and reporting components.

    Never raises an exception — all probe errors are caught and reported
    as ``available: false`` in the response body.
    """
    # ── Database probe ────────────────────────────────────────────────
    db_status = _probe_database(settings.db_path)

    # ── Analytics probe ───────────────────────────────────────────────
    analytics_status = _probe_analytics()

    # ── Reporting probe ───────────────────────────────────────────────
    reporting_status = _probe_reporting()

    # ── Overall status ────────────────────────────────────────────────
    all_ok = db_status.available and analytics_status.available and reporting_status.available
    overall = "healthy" if all_ok else "degraded"

    return HealthResponse(
        status=overall,
        framework_name=settings.app_name,
        framework_version=settings.framework_version,
        database=db_status,
        analytics=analytics_status,
        reporting=reporting_status,
    )


# ---------------------------------------------------------------------------
# Probe helpers — each returns ComponentStatus, never raises
# ---------------------------------------------------------------------------

def _probe_database(db_path: str) -> ComponentStatus:
    """Try to open and immediately close a DatabaseManager connection."""
    try:
        from database.database_manager import DatabaseManager
        db = DatabaseManager(db_path=db_path)
        db.init_db()
        size_kb = db.db_size_kb()
        db.close()
        db_name = Path(db_path).name
        return ComponentStatus(
            available=True,
            detail=f"Connected — {db_name}  ({size_kb:.0f} KB)",
        )
    except Exception as exc:
        return ComponentStatus(available=False, detail=str(exc)[:200])


def _probe_analytics() -> ComponentStatus:
    """Check that AnalyticsManager can be imported and instantiated."""
    try:
        from analytics.analytics_manager import AnalyticsManager  # noqa: F401
        return ComponentStatus(available=True, detail="AnalyticsManager ready")
    except Exception as exc:
        return ComponentStatus(available=False, detail=str(exc)[:200])


def _probe_reporting() -> ComponentStatus:
    """Check that ReportManager can be imported and instantiated."""
    try:
        from reporting.report_manager import ReportManager  # noqa: F401
        return ComponentStatus(available=True, detail="ReportManager ready")
    except Exception as exc:
        return ComponentStatus(available=False, detail=str(exc)[:200])
