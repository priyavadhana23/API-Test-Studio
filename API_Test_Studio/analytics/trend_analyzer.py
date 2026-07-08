"""
analytics/trend_analyzer.py
=============================
Computes time-series trends across multiple execution runs.

Input:  List[DbExecutionRun] from DatabaseManager.list_runs()
Output: TrendResult objects for pass rate, failure count, response time,
        and execution frequency (daily / weekly / monthly).

No SQL. No HTTP. Pure computation over run records.
"""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from analytics.models import TrendPoint, TrendResult
from analytics.statistics import (
    moving_average,
    safe_divide,
    trend_direction,
    trend_slope,
)
from utilities.logger import get_logger

logger = get_logger(__name__)


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 UTC timestamp string, returning None on failure."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


class TrendAnalyzer:
    """
    Computes pass-rate, failure, response-time, and execution-frequency
    trends from a chronologically ordered list of execution runs.

    Args:
        runs: All ``DbExecutionRun`` rows for the API being analysed,
              sorted oldest-first.
    """

    def __init__(self, runs: List[Any]) -> None:
        # Sort oldest-first so trend lines run left-to-right in time
        self._runs = sorted(
            runs,
            key=lambda r: r.execution_timestamp or "",
        )
        logger.debug("TrendAnalyzer: %d run(s) loaded.", len(self._runs))

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def pass_rate_trend(self) -> TrendResult:
        """
        Build a pass-rate trend (% passed per run over time).

        Returns:
            ``TrendResult`` with one point per run, slope, and direction.
        """
        points = [
            TrendPoint(
                label=self._run_label(r),
                value=round(r.pass_percentage, 2),
                run_count=1,
            )
            for r in self._runs
        ]
        values = [p.value for p in points]
        slope  = trend_slope(values)
        ma     = moving_average(values)
        direction = trend_direction(values)

        logger.debug(
            "TrendAnalyzer.pass_rate_trend: slope=%.4f direction=%s",
            slope, direction,
        )
        return TrendResult(
            name="Pass Rate Trend (%)",
            points=points,
            slope=slope,
            direction=direction,
            moving_avg=ma,
        )

    def failure_trend(self) -> TrendResult:
        """Build a failure-count trend (failed + error per run)."""
        points = [
            TrendPoint(
                label=self._run_label(r),
                value=float(r.failed + r.errors),
                run_count=1,
            )
            for r in self._runs
        ]
        values = [p.value for p in points]
        slope  = trend_slope(values)
        # For failures a negative slope is "improving"
        raw_direction = trend_direction(values)
        direction = (
            "improving" if raw_direction == "declining"
            else "declining" if raw_direction == "improving"
            else "stable"
        )
        return TrendResult(
            name="Failure Count Trend",
            points=points,
            slope=slope,
            direction=direction,
            moving_avg=moving_average(values),
        )

    def response_time_trend(self) -> TrendResult:
        """Build an average response-time trend (ms per run)."""
        points = [
            TrendPoint(
                label=self._run_label(r),
                value=round(r.avg_response_time_ms or 0.0, 2),
                run_count=1,
            )
            for r in self._runs
            if r.avg_response_time_ms is not None
        ]
        if not points:
            return TrendResult(name="Response Time Trend (ms)")

        values = [p.value for p in points]
        slope  = trend_slope(values)
        raw_direction = trend_direction(values)
        # Rising response time is "declining" health
        direction = (
            "declining" if raw_direction == "improving"
            else "improving" if raw_direction == "declining"
            else "stable"
        )
        return TrendResult(
            name="Response Time Trend (ms)",
            points=points,
            slope=slope,
            direction=direction,
            moving_avg=moving_average(values),
        )

    def daily_executions(self) -> TrendResult:
        """Aggregate execution counts by calendar day (YYYY-MM-DD)."""
        return self._aggregate_by(
            fmt="%Y-%m-%d",
            name="Daily Executions",
        )

    def weekly_executions(self) -> TrendResult:
        """Aggregate execution counts by ISO week (YYYY-Www)."""
        return self._aggregate_by(
            fmt="%Y-W%W",
            name="Weekly Executions",
        )

    def monthly_executions(self) -> TrendResult:
        """Aggregate execution counts by month (YYYY-MM)."""
        return self._aggregate_by(
            fmt="%Y-%m",
            name="Monthly Executions",
        )

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _aggregate_by(self, fmt: str, name: str) -> TrendResult:
        """
        Aggregate pass percentage and run count by a strftime *fmt* bucket.

        Args:
            fmt:  strftime format string defining the bucket width.
            name: Human-readable trend name.

        Returns:
            ``TrendResult`` with one point per bucket.
        """
        buckets: Dict[str, List[float]] = defaultdict(list)
        counts:  Dict[str, int]         = defaultdict(int)

        for r in self._runs:
            dt = _parse_ts(r.execution_timestamp)
            if not dt:
                continue
            key = dt.strftime(fmt)
            buckets[key].append(r.pass_percentage)
            counts[key]  += 1

        if not buckets:
            return TrendResult(name=name)

        points = [
            TrendPoint(
                label=label,
                value=round(safe_divide(sum(pcts), len(pcts)), 2),
                run_count=counts[label],
            )
            for label, pcts in sorted(buckets.items())
        ]
        values    = [p.value for p in points]
        slope     = trend_slope(values)
        direction = trend_direction(values)
        return TrendResult(
            name=name,
            points=points,
            slope=slope,
            direction=direction,
            moving_avg=moving_average(values),
        )

    @staticmethod
    def _run_label(run: Any) -> str:
        """Short label for a run: ``YYYY-MM-DD HH:MM`` or run_id[:8]."""
        dt = _parse_ts(run.execution_timestamp)
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M")
        return run.run_id[:8]
