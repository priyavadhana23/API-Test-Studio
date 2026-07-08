"""
web_dashboard/backend/dependencies/providers.py
=================================================
FastAPI dependency providers for the three core framework services.

Each provider is a generator function compatible with FastAPI's
``Depends()`` system.  They open a resource, yield it to the route
handler, then close it cleanly — even on exceptions.

Usage in a router:
    from fastapi import Depends
    from web_dashboard.backend.dependencies.providers import get_db

    @router.get("/runs")
    def list_runs(db: DatabaseManager = Depends(get_db)):
        return db.list_runs(20)

Providers:
    get_db()        — opens DatabaseManager, yields, closes
    get_analytics() — yields AnalyticsManager bound to an open db
    get_reporter()  — yields ReportManager bound to db + analytics
"""

from pathlib import Path
from typing import Generator

from fastapi import Depends

from web_dashboard.backend.config.settings import Settings, get_settings


# ---------------------------------------------------------------------------
# DatabaseManager
# ---------------------------------------------------------------------------

def get_db(
    settings: Settings = Depends(get_settings),
) -> Generator:
    """
    Open a DatabaseManager for the duration of one HTTP request.

    Yields:
        An initialised ``DatabaseManager`` instance.

    Ensures:
        The connection is closed after the response is sent, even if an
        exception is raised inside the route handler.
    """
    from database.database_manager import DatabaseManager

    db = DatabaseManager(
        db_path=settings.db_path,
        history_dir=settings.history_dir,
    )
    db.init_db()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# AnalyticsManager
# ---------------------------------------------------------------------------

def get_analytics(
    db=Depends(get_db),
) -> Generator:
    """
    Yield an AnalyticsManager bound to the request-scoped DatabaseManager.

    The AnalyticsManager itself holds no connections — it is safe to
    construct per-request.

    Yields:
        An ``AnalyticsManager`` instance.
    """
    from analytics.analytics_manager import AnalyticsManager

    yield AnalyticsManager(db)


# ---------------------------------------------------------------------------
# ReportManager
# ---------------------------------------------------------------------------

def get_reporter(
    settings: Settings = Depends(get_settings),
    db=Depends(get_db),
    analytics=Depends(get_analytics),
) -> Generator:
    """
    Yield a ReportManager bound to db + analytics for one HTTP request.

    Yields:
        A ``ReportManager`` instance writing to the configured reports dir.
    """
    from reporting.report_manager import ReportManager

    yield ReportManager(
        db_manager=db,
        analytics_manager=analytics,
        output_dir=Path(settings.reports_dir),
    )
