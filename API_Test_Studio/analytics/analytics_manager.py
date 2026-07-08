"""
analytics/analytics_manager.py
================================
Public orchestrator for the Phase 7 Analytics Engine.

``AnalyticsManager`` is the ONLY class the rest of the framework calls.
No external code should directly instantiate TrendAnalyzer, EndpointAnalyzer,
or any other individual analyzer.

Pipeline
--------
    DatabaseManager
         │
         ├─ list_runs()            → all runs for the API
         ├─ get_test_results()     → test-case rows for the run
         ├─ get_validation_details() → validation rows for the run
         │
         ▼
    AnalyticsManager.run_analysis(run_id)
         │
         ├─ TrendAnalyzer       → TrendResult (pass rate over time)
         ├─ EndpointAnalyzer    → EndpointAnalysis
         ├─ ResponseTimeAnalyzer → ResponseTimeAnalysis
         ├─ FailureAnalyzer     → FailureAnalysis
         ├─ RegressionAnalyzer  → RegressionSummary (vs previous run)
         └─ HealthAnalyzer      → HealthReport
         │
         ▼
    AnalyticsSummary   ← returned to caller + printed to logger

The manager communicates only with DatabaseManager — never with SQLite,
repositories, or any other lower-level component.
"""

import time
from datetime import datetime, timezone
from typing import Any, List, Optional

from analytics.endpoint_analyzer  import EndpointAnalyzer
from analytics.failure_analyzer   import FailureAnalyzer
from analytics.health_analyzer    import HealthAnalyzer
from analytics.models             import AnalyticsSummary
from analytics.regression_analyzer import RegressionAnalyzer
from analytics.response_time_analyzer import ResponseTimeAnalyzer
from analytics.trend_analyzer    import TrendAnalyzer
from utilities.logger             import get_logger

logger = get_logger(__name__)


class AnalyticsManager:
    """
    Orchestrates all analytics computations for one execution run.

    Args:
        db_manager: An initialised ``DatabaseManager`` instance.
                    The analytics layer reads data exclusively through
                    this object.

    Usage::

        with DatabaseManager(...) as db:
            manager = AnalyticsManager(db)
            summary = manager.run_analysis(run_id)
    """

    def __init__(self, db_manager: Any) -> None:
        self._db = db_manager
        logger.info("AnalyticsManager: initialised.")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run_analysis(self, run_id: str) -> AnalyticsSummary:
        """
        Run the full analytics pipeline for *run_id*.

        Args:
            run_id: The execution run to analyse.

        Returns:
            Fully populated ``AnalyticsSummary``.

        Raises:
            ValueError: If *run_id* is not found in the database.
        """
        t_start = time.monotonic()
        logger.info("AnalyticsManager: starting analysis for run '%s'.", run_id[:16])

        # ── 1. Fetch data from DatabaseManager ────────────────────────
        run = self._db.get_run(run_id)
        if run is None:
            raise ValueError(f"Run '{run_id}' not found in the database.")

        tc_results  = self._db.get_test_results(run_id)
        val_details = self._db.get_validation_details(run_id)
        all_runs    = self._db.search_runs(api_name=run.api_name, limit=500)

        logger.debug(
            "AnalyticsManager: fetched run=%s  tc=%d  vd=%d  history=%d",
            run_id[:8], len(tc_results), len(val_details), len(all_runs),
        )

        # ── 2. Trend analysis (all runs for this API) ──────────────────
        trend_analyzer = TrendAnalyzer(all_runs)
        trend = trend_analyzer.pass_rate_trend()

        # ── 3. Endpoint analysis ───────────────────────────────────────
        endpoint_analysis = EndpointAnalyzer(tc_results).analyse()

        # ── 4. Response-time analysis ──────────────────────────────────
        rt_analysis = ResponseTimeAnalyzer(tc_results).analyse()

        # ── 5. Failure analysis ────────────────────────────────────────
        failure_analysis = FailureAnalyzer(tc_results, val_details).analyse()

        # ── 6. Regression (compare against previous run) ──────────────
        regression = self._compute_regression(run, all_runs)

        # ── 7. Health score ────────────────────────────────────────────
        health = HealthAnalyzer(run, tc_results).analyse()

        elapsed = time.monotonic() - t_start
        now_iso = datetime.now(tz=timezone.utc).isoformat()

        summary = AnalyticsSummary(
            run_id           = run_id,
            api_name         = run.api_name,
            total_runs       = len(all_runs),
            trend            = trend,
            endpoint_analysis= endpoint_analysis,
            response_time    = rt_analysis,
            failure_analysis = failure_analysis,
            regression       = regression,
            health           = health,
            generated_at     = now_iso,
        )

        logger.info(
            "AnalyticsManager: analysis complete in %.2fs  "
            "health=%.1f (%s).",
            elapsed, health.score, health.rating,
        )

        self._print_summary(summary, elapsed)
        return summary

    def run_analysis_latest(self) -> Optional[AnalyticsSummary]:
        """
        Analyse the most recently stored run.

        Returns:
            ``AnalyticsSummary`` or ``None`` if no runs exist.
        """
        latest = self._db.latest_run()
        if not latest:
            logger.warning("AnalyticsManager: no runs in database.")
            return None
        return self.run_analysis(latest.run_id)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _compute_regression(
        self,
        current_run: Any,
        all_runs: List[Any],
    ) -> Any:
        """
        Find the previous run and compute a regression comparison.

        Args:
            current_run: The run being analysed.
            all_runs:    All runs for this API (unsorted).

        Returns:
            ``RegressionSummary`` or a default empty summary.
        """
        from analytics.models import RegressionSummary

        # Sort by timestamp, find index of current run
        sorted_runs = sorted(
            all_runs, key=lambda r: r.execution_timestamp or ""
        )
        current_ids = [r.run_id for r in sorted_runs]
        try:
            idx = current_ids.index(current_run.run_id)
        except ValueError:
            idx = -1

        if idx <= 0:
            # No previous run — no regression possible
            logger.debug(
                "RegressionAnalyzer: no previous run found for '%s'.",
                current_run.run_id[:8],
            )
            return RegressionSummary(
                run_id_baseline=current_run.run_id,
                run_id_current=current_run.run_id,
                api_name=current_run.api_name,
                verdict="No previous run available for regression comparison.",
            )

        prev_run = sorted_runs[idx - 1]
        prev_tc  = self._db.get_test_results(prev_run.run_id)
        curr_tc  = self._db.get_test_results(current_run.run_id)

        return RegressionAnalyzer(
            baseline_results = prev_tc,
            current_results  = curr_tc,
            baseline_run     = prev_run,
            current_run      = current_run,
        ).analyse()

    # ------------------------------------------------------------------ #
    # Summary printer
    # ------------------------------------------------------------------ #

    def _print_summary(self, summary: AnalyticsSummary, elapsed: float) -> None:
        """Emit a structured analytics summary through the logger."""
        wide = "=" * 52
        sep  = "─" * 52
        h    = summary.health
        ep   = summary.endpoint_analysis
        rt   = summary.response_time
        fa   = summary.failure_analysis
        reg  = summary.regression
        tr   = summary.trend

        logger.info(wide)
        logger.info("  ANALYTICS SUMMARY")
        logger.info(wide)
        logger.info("  API Name       : %s", summary.api_name)
        logger.info("  Run ID         : %s…", summary.run_id[:20])
        logger.info("  Total Runs     : %d", summary.total_runs)
        logger.info("  Generated At   : %s", summary.generated_at[:19])
        logger.info(sep)

        # Health
        if h:
            rating_emoji = {
                "Excellent": "✅", "Good": "🟢",
                "Needs Attention": "🟡", "Critical": "🔴",
            }.get(h.rating, "")
            logger.info(
                "  Health Score   : %.1f / 100  %s %s",
                h.score, h.rating, rating_emoji,
            )
            logger.info(
                "    Pass Rate Pts : %.1f / 40   "
                "RT Pts: %.1f / 30   "
                "Stability: %.1f / 20   "
                "Avail: %.1f / 10",
                h.pass_rate_score, h.response_time_score,
                h.stability_score, h.availability_score,
            )
            for rec in h.recommendations:
                logger.info("    ⚠  %s", rec)
        logger.info(sep)

        # Pass-rate trend
        if tr and tr.points:
            logger.info(
                "  Pass Rate Trend: %s (slope=%.4f)",
                tr.direction.upper(), tr.slope,
            )
            if len(tr.points) >= 2:
                first, last = tr.points[0], tr.points[-1]
                logger.info(
                    "    %s: %.1f%%  →  %s: %.1f%%",
                    first.label, first.value, last.label, last.value,
                )
        logger.info(sep)

        # Endpoint analysis
        if ep:
            logger.info("  Endpoint Analysis")
            logger.info("    Most Executed  : %s", ep.most_executed or "—")
            logger.info("    Most Failed    : %s", ep.most_failed   or "—")
            logger.info("    Slowest        : %s", ep.slowest       or "—")
            logger.info("    Fastest        : %s", ep.fastest       or "—")
            logger.info("    Most Successful: %s", ep.most_successful or "—")
            logger.info("    Avg Test Count : %.1f", ep.avg_execution_count)
        logger.info(sep)

        # Response-time stats
        if rt and rt.sample_count > 0:
            logger.info("  Response Time Analysis  (n=%d)", rt.sample_count)
            logger.info(
                "    mean=%.1fms  median=%.1fms  min=%.1fms  max=%.1fms",
                rt.mean_ms or 0, rt.median_ms or 0,
                rt.min_ms  or 0, rt.max_ms    or 0,
            )
            logger.info(
                "    p95=%.1fms  p99=%.1fms  SLA (≤%.0fms): %.1f%%",
                rt.p95_ms or 0, rt.p99_ms or 0,
                rt.sla_threshold_ms, rt.sla_compliance_pct,
            )
        logger.info(sep)

        # Failure analysis
        if fa:
            logger.info(
                "  Failure Analysis  (total=%d)", fa.total_failures
            )
            logger.info(
                "    Validation: %d  Execution errors: %d  "
                "Auth: %d  Schema: %d  Timeout: %d",
                fa.validation_failures, fa.execution_errors,
                fa.auth_failures, fa.schema_failures, fa.timeout_failures,
            )
            if fa.top_failures:
                logger.info("    Top failures:")
                for entry in fa.top_failures[:5]:
                    logger.info(
                        "      [%dx %.1f%%] %s",
                        entry.count, entry.percentage,
                        (entry.category or "")[:80],
                    )
        logger.info(sep)

        # Regression
        if reg:
            logger.info("  Regression Analysis")
            logger.info("    Verdict        : %s", reg.verdict)
            if reg.has_regression:
                logger.info(
                    "    New failures   : %d  Fixed: %d  Unchanged: %d",
                    len(reg.new_failures), len(reg.fixed_failures),
                    len(reg.unchanged_failures),
                )
                for op in reg.new_failures[:5]:
                    logger.info("      🔴 NEW FAIL: %s", op)
            else:
                logger.info(
                    "    Fixed failures : %d  Unchanged: %d",
                    len(reg.fixed_failures), len(reg.unchanged_failures),
                )
            logger.info(
                "    Pass rate delta: %+.2f%%  RT delta: %s",
                reg.pass_rate_delta,
                f"{reg.avg_rt_delta_ms:+.1f}ms"
                if reg.avg_rt_delta_ms is not None else "N/A",
            )

        logger.info(wide)
        logger.info("  Analytics generated in %.2f s.", elapsed)
        logger.info("  END OF ANALYTICS SUMMARY — %s", summary.api_name)
        logger.info(wide)
