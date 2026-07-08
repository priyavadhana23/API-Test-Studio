"""
analytics package
==================
Phase 7 — Analytics and Insights Engine for API Test Studio.

Public API (the only import the rest of the framework needs):

    from analytics import AnalyticsManager

    with DatabaseManager(...) as db:
        manager = AnalyticsManager(db)
        summary = manager.run_analysis(run_id)
        # or
        summary = manager.run_analysis_latest()

Internal modules (not for direct use outside this package):

    statistics          — Pure math: mean/median/std_dev/percentiles/trend
    models              — Analytics result dataclasses (no ORM, no SQL)
    trend_analyzer      — Pass-rate, failure, and response-time trends
    endpoint_analyzer   — Per-endpoint stats: most/least executed/failed/fast
    response_time_analyzer — Mean/median/p95/p99/SLA compliance
    failure_analyzer    — Failure distribution and top-10 failure messages
    regression_analyzer — New/fixed/unchanged failures between two runs
    health_analyzer     — Composite 0–100 health score
    analytics_manager   — Orchestrator and public facade

To add a new analyzer (e.g. SecurityAnalyzer):
    1. Create analytics/security_analyzer.py implementing an analyse() method.
    2. Import and call it inside AnalyticsManager.run_analysis().
    3. Add its result field to AnalyticsSummary in models.py.
    4. No other code changes required.
"""

from analytics.analytics_manager import AnalyticsManager
from analytics.models import AnalyticsSummary

__all__ = ["AnalyticsManager", "AnalyticsSummary"]
