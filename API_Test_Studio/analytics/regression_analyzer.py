"""
analytics/regression_analyzer.py
==================================
Compares two execution runs to detect regressions.

Input:  Two lists of DbTestCaseResult (baseline run A, current run B).
Output: RegressionSummary

Definition of regression:
    - New failures  — operation_ids that failed in B but passed/didn't exist in A.
    - Fixed         — operation_ids that passed in B but failed in A.
    - Unchanged     — operation_ids that failed in both A and B.

No SQL. No HTTP. Pure computation.
"""

from typing import Any, List, Optional

from analytics.models import RegressionSummary
from analytics.statistics import safe_divide
from utilities.logger import get_logger

logger = get_logger(__name__)


class RegressionAnalyzer:
    """
    Compares two execution runs at the operation-ID level.

    Args:
        baseline_results: ``DbTestCaseResult`` rows from the reference run.
        current_results:  ``DbTestCaseResult`` rows from the newer run.
        baseline_run:     The ``DbExecutionRun`` record for the baseline.
        current_run:      The ``DbExecutionRun`` record for the current run.
    """

    def __init__(
        self,
        baseline_results: List[Any],
        current_results: List[Any],
        baseline_run: Any,
        current_run: Any,
    ) -> None:
        self._baseline_tc  = baseline_results
        self._current_tc   = current_results
        self._baseline_run = baseline_run
        self._current_run  = current_run
        logger.debug(
            "RegressionAnalyzer: baseline=%d results, current=%d results.",
            len(baseline_results), len(current_results),
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def analyse(self) -> RegressionSummary:
        """
        Compare baseline and current runs and produce a RegressionSummary.

        Returns:
            ``RegressionSummary`` with new/fixed/unchanged failure lists.
        """
        if not self._baseline_tc or not self._current_tc:
            logger.debug("RegressionAnalyzer: insufficient data for comparison.")
            return RegressionSummary(
                run_id_baseline=getattr(self._baseline_run, "run_id", ""),
                run_id_current=getattr(self._current_run, "run_id", ""),
                api_name=getattr(self._baseline_run, "api_name", ""),
                verdict="Insufficient data for regression analysis.",
            )

        # ── Build operation_id → status maps ──────────────────────────
        def _status_map(results: List[Any]) -> dict:
            """Return {operation_id: "passed"|"failed"|"error"|"skipped"}."""
            m: dict = {}
            for r in results:
                op = r.operation_id or r.endpoint or r.test_id
                status = (r.validation_status or "unknown").lower()
                # Keep the worst status seen for the same operation
                existing = m.get(op, "passed")
                if status in ("error", "failed"):
                    m[op] = status
                elif existing not in ("error", "failed"):
                    m[op] = status
            return m

        baseline_map = _status_map(self._baseline_tc)
        current_map  = _status_map(self._current_tc)

        all_ops = set(baseline_map) | set(current_map)

        new_failures:       List[str] = []
        fixed_failures:     List[str] = []
        unchanged_failures: List[str] = []

        for op in sorted(all_ops):
            b_status = baseline_map.get(op, "passed")
            c_status = current_map.get(op, "passed")
            b_failed = b_status in ("failed", "error")
            c_failed = c_status in ("failed", "error")

            if c_failed and not b_failed:
                new_failures.append(op)
            elif not c_failed and b_failed:
                fixed_failures.append(op)
            elif c_failed and b_failed:
                unchanged_failures.append(op)

        # ── Response-time delta ────────────────────────────────────────
        avg_rt_a = getattr(self._baseline_run, "avg_response_time_ms", None)
        avg_rt_b = getattr(self._current_run,  "avg_response_time_ms", None)
        avg_rt_delta = (
            round(avg_rt_b - avg_rt_a, 2)
            if avg_rt_a is not None and avg_rt_b is not None
            else None
        )

        # ── Pass-rate delta ────────────────────────────────────────────
        pct_a = getattr(self._baseline_run, "pass_percentage", 0.0) or 0.0
        pct_b = getattr(self._current_run,  "pass_percentage", 0.0) or 0.0
        pct_delta = round(pct_b - pct_a, 2)

        has_regression = len(new_failures) > 0

        # ── Verdict ────────────────────────────────────────────────────
        if has_regression:
            verdict = (
                f"Regression detected: {len(new_failures)} new failure(s), "
                f"{len(fixed_failures)} fixed, pass rate {pct_a:.1f}% → {pct_b:.1f}%."
            )
        elif fixed_failures:
            verdict = (
                f"No regression. {len(fixed_failures)} failure(s) fixed. "
                f"Pass rate {pct_a:.1f}% → {pct_b:.1f}%."
            )
        else:
            verdict = (
                f"No regression detected. Pass rate {pct_a:.1f}% → {pct_b:.1f}%."
            )

        summary = RegressionSummary(
            run_id_baseline    = getattr(self._baseline_run, "run_id", ""),
            run_id_current     = getattr(self._current_run,  "run_id", ""),
            api_name           = getattr(self._baseline_run, "api_name", ""),
            new_failures       = new_failures,
            fixed_failures     = fixed_failures,
            unchanged_failures = unchanged_failures,
            pass_rate_delta    = pct_delta,
            avg_rt_delta_ms    = avg_rt_delta,
            has_regression     = has_regression,
            verdict            = verdict,
        )

        logger.debug(
            "RegressionAnalyzer: new=%d  fixed=%d  unchanged=%d  "
            "has_regression=%s",
            len(new_failures), len(fixed_failures),
            len(unchanged_failures), has_regression,
        )
        return summary
