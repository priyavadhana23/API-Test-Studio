"""
analytics/endpoint_analyzer.py
================================
Computes per-endpoint statistics from test-case results.

Input:  List[DbTestCaseResult] for one or more runs.
Output: EndpointAnalysis containing per-endpoint stats plus
        most/least executed, fastest, slowest, most failed, etc.

No SQL. No HTTP. Pure computation.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from analytics.models import EndpointAnalysis, EndpointStats
from analytics.statistics import mean, p95, safe_divide
from utilities.logger import get_logger

logger = get_logger(__name__)


class EndpointAnalyzer:
    """
    Aggregates test-case result rows by endpoint path and computes stats.

    Args:
        tc_results: All ``DbTestCaseResult`` rows for the run(s) to analyse.
    """

    def __init__(self, tc_results: List[Any]) -> None:
        self._results = tc_results
        logger.debug("EndpointAnalyzer: %d result(s) loaded.", len(tc_results))

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def analyse(self) -> EndpointAnalysis:
        """
        Compute full endpoint-level analysis.

        Returns:
            ``EndpointAnalysis`` with all stats populated.
        """
        if not self._results:
            logger.debug("EndpointAnalyzer: no results — returning empty analysis.")
            return EndpointAnalysis()

        stats_map = self._build_stats_map()
        all_stats = list(stats_map.values())

        # Derived insights
        by_executions = sorted(all_stats, key=lambda s: s.total_executions, reverse=True)
        by_failures   = sorted(all_stats, key=lambda s: s.failed + s.errors, reverse=True)
        by_pass_rate  = sorted(
            [s for s in all_stats if s.total_executions > 0],
            key=lambda s: s.pass_rate, reverse=True,
        )
        timed = [s for s in all_stats if s.avg_response_time_ms is not None]
        by_rt = sorted(timed, key=lambda s: s.avg_response_time_ms or 0)

        avg_count = mean([float(s.total_executions) for s in all_stats]) \
            if all_stats else 0.0

        analysis = EndpointAnalysis(
            most_executed   = by_executions[0].endpoint if by_executions else None,
            least_executed  = by_executions[-1].endpoint if len(by_executions) > 1 else None,
            most_failed     = by_failures[0].endpoint
                              if by_failures and (by_failures[0].failed + by_failures[0].errors) > 0
                              else None,
            most_successful = by_pass_rate[0].endpoint if by_pass_rate else None,
            slowest         = by_rt[-1].endpoint if by_rt else None,
            fastest         = by_rt[0].endpoint  if by_rt else None,
            avg_execution_count = round(avg_count, 2),
            all_stats       = sorted(all_stats, key=lambda s: s.endpoint),
        )

        logger.debug(
            "EndpointAnalyzer: %d unique endpoint(s) analysed.  "
            "Most failed: %s  Slowest: %s",
            len(all_stats), analysis.most_failed, analysis.slowest,
        )
        return analysis

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _build_stats_map(self) -> Dict[str, EndpointStats]:
        """
        Group results by (endpoint, http_method) and compute stats.

        Returns:
            Dict keyed by ``"METHOD /path"``.
        """
        # Accumulators
        totals:   Dict[str, int]         = defaultdict(int)
        passed:   Dict[str, int]         = defaultdict(int)
        failed:   Dict[str, int]         = defaultdict(int)
        errors:   Dict[str, int]         = defaultdict(int)
        rt_lists: Dict[str, List[float]] = defaultdict(list)
        methods:  Dict[str, str]         = {}

        for r in self._results:
            key    = r.endpoint or "unknown"
            method = (r.http_method or "GET").upper()
            methods[key] = method
            totals[key] += 1

            status = (r.validation_status or "").lower()
            if status == "passed":
                passed[key] += 1
            elif status in ("failed",):
                failed[key] += 1
            elif status in ("error",):
                errors[key] += 1

            if r.response_time_ms is not None:
                rt_lists[key].append(r.response_time_ms)

        stats_map: Dict[str, EndpointStats] = {}
        for endpoint, total in totals.items():
            p   = passed.get(endpoint, 0)
            f   = failed.get(endpoint, 0)
            e   = errors.get(endpoint, 0)
            rts = rt_lists.get(endpoint, [])

            stats_map[endpoint] = EndpointStats(
                endpoint=endpoint,
                method=methods.get(endpoint, "?"),
                total_executions=total,
                passed=p,
                failed=f,
                errors=e,
                pass_rate=round(safe_divide(p, total) * 100, 2),
                avg_response_time_ms=round(mean(rts), 2) if rts else None,
                min_response_time_ms=round(min(rts), 2) if rts else None,
                max_response_time_ms=round(max(rts), 2) if rts else None,
                p95_response_time_ms=round(p95(rts), 2) if rts else None,
            )

        return stats_map
