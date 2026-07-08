"""
analytics/response_time_analyzer.py
=====================================
Computes statistical response-time metrics from test-case results.

Input:  List[DbTestCaseResult] — uses response_time_ms field.
Output: ResponseTimeAnalysis with mean/median/min/max/p95/p99/SLA.

No SQL. No HTTP. Pure computation.
"""

from typing import Any, List, Optional

from analytics.models import ResponseTimeAnalysis
from analytics.statistics import (
    mean, median, std_dev, p95, p99, percentile, safe_divide,
)
from utilities.logger import get_logger

logger = get_logger(__name__)

# Default SLA threshold if none specified (5 seconds)
DEFAULT_SLA_MS: float = 5_000.0


class ResponseTimeAnalyzer:
    """
    Statistical response-time analysis for one execution run.

    Args:
        tc_results:       ``DbTestCaseResult`` rows for the run.
        sla_threshold_ms: Maximum acceptable response time in ms.
                          Defaults to ``DEFAULT_SLA_MS`` (5 000 ms).
    """

    def __init__(
        self,
        tc_results: List[Any],
        sla_threshold_ms: float = DEFAULT_SLA_MS,
    ) -> None:
        self._results       = tc_results
        self._sla_threshold = sla_threshold_ms
        logger.debug(
            "ResponseTimeAnalyzer: %d result(s), SLA=%.0f ms.",
            len(tc_results), sla_threshold_ms,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def analyse(self) -> ResponseTimeAnalysis:
        """
        Compute full response-time statistics.

        Returns:
            ``ResponseTimeAnalysis`` with all fields populated.
        """
        times = [
            r.response_time_ms
            for r in self._results
            if r.response_time_ms is not None
        ]

        if not times:
            logger.debug("ResponseTimeAnalyzer: no timing data available.")
            return ResponseTimeAnalysis(
                sample_count=0,
                sla_threshold_ms=self._sla_threshold,
                sla_compliance_pct=0.0,
            )

        within_sla = sum(1 for t in times if t <= self._sla_threshold)
        sla_pct    = round(safe_divide(within_sla, len(times)) * 100, 2)

        result = ResponseTimeAnalysis(
            sample_count        = len(times),
            mean_ms             = round(mean(times), 2),
            median_ms           = round(median(times), 2),
            min_ms              = round(min(times), 2),
            max_ms              = round(max(times), 2),
            std_dev_ms          = round(std_dev(times), 2) if len(times) > 1 else 0.0,
            p95_ms              = round(p95(times), 2),
            p99_ms              = round(p99(times), 2),
            sla_threshold_ms    = self._sla_threshold,
            sla_compliance_pct  = sla_pct,
        )

        logger.debug(
            "ResponseTimeAnalyzer: mean=%.1fms  p95=%.1fms  p99=%.1fms  "
            "SLA=%.1f%%",
            result.mean_ms or 0, result.p95_ms or 0, result.p99_ms or 0,
            result.sla_compliance_pct,
        )
        return result
