"""
analytics/health_analyzer.py
==============================
Computes an overall API health score (0–100) from a single execution run.

Score composition (total 100 points):
    Pass Rate       40 pts  — proportional to pass percentage
    Response Time   30 pts  — based on average response time vs SLA
    Stability       20 pts  — inversely proportional to error rate
    Availability    10 pts  — flat 10 if the run completed, 0 if all errors

Thresholds (from analytics/models.py):
    95–100  → Excellent
    80–94   → Good
    60–79   → Needs Attention
    0–59    → Critical

No SQL. No HTTP. Pure computation.
"""

from typing import Any, List, Optional

from analytics.models import HealthReport, HEALTH_EXCELLENT, HEALTH_GOOD, HEALTH_NEEDS_ATTN
from analytics.statistics import safe_divide
from utilities.logger import get_logger

logger = get_logger(__name__)

# Weights
_PASS_RATE_WEIGHT  = 40.0
_RT_WEIGHT         = 30.0
_STABILITY_WEIGHT  = 20.0
_AVAIL_WEIGHT      = 10.0

# Response-time thresholds for full score (ms)
_RT_EXCELLENT_MS   = 500.0    # ≤ 500 ms → full RT score
_RT_ACCEPTABLE_MS  = 5_000.0  # ≤ 5 000 ms → partial score
# Above 5 000 ms → 0 RT score


class HealthAnalyzer:
    """
    Computes a composite health score for one execution run.

    Args:
        run:         The ``DbExecutionRun`` record.
        tc_results:  All ``DbTestCaseResult`` rows for the run.
    """

    def __init__(self, run: Any, tc_results: List[Any]) -> None:
        self._run     = run
        self._tc      = tc_results
        logger.debug(
            "HealthAnalyzer: run=%s  results=%d",
            getattr(run, "run_id", "?")[:8], len(tc_results),
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def analyse(self) -> HealthReport:
        """
        Compute the HealthReport for the run.

        Returns:
            Fully populated ``HealthReport``.
        """
        run = self._run
        total    = getattr(run, "total_executed", 0) or 0
        passed   = getattr(run, "passed", 0) or 0
        errors   = getattr(run, "errors", 0) or 0
        pass_pct = getattr(run, "pass_percentage", 0.0) or 0.0
        avg_rt   = getattr(run, "avg_response_time_ms", None)

        if total == 0:
            logger.debug("HealthAnalyzer: zero executions — score = 0.")
            return HealthReport(
                score=0.0,
                recommendations=["No test cases were executed — cannot compute health score."],
            )

        # ── Component 1: Pass Rate (0–40) ──────────────────────────────
        pass_rate_score = round(safe_divide(pass_pct, 100.0) * _PASS_RATE_WEIGHT, 2)

        # ── Component 2: Response Time (0–30) ──────────────────────────
        if avg_rt is None:
            rt_score = _RT_WEIGHT * 0.5   # no data → assume partial
        elif avg_rt <= _RT_EXCELLENT_MS:
            rt_score = _RT_WEIGHT
        elif avg_rt <= _RT_ACCEPTABLE_MS:
            # Linear scale: excellent → acceptable gives full → 0
            fraction = 1.0 - safe_divide(
                avg_rt - _RT_EXCELLENT_MS,
                _RT_ACCEPTABLE_MS - _RT_EXCELLENT_MS,
            )
            rt_score = round(fraction * _RT_WEIGHT, 2)
        else:
            rt_score = 0.0

        # ── Component 3: Stability / Error Rate (0–20) ─────────────────
        # Error rate = errors / total; stability = 1 - error_rate
        error_rate     = safe_divide(errors, total)
        stability_score = round((1.0 - error_rate) * _STABILITY_WEIGHT, 2)

        # ── Component 4: Availability (0–10) ───────────────────────────
        # Full score if at least one test completed without a fatal error,
        # else 0.
        has_responses = total - errors
        availability_score = _AVAIL_WEIGHT if has_responses > 0 else 0.0

        # ── Composite score ────────────────────────────────────────────
        score = round(
            pass_rate_score + rt_score + stability_score + availability_score, 2
        )
        score = max(0.0, min(100.0, score))  # clamp to [0, 100]

        # ── Recommendations ────────────────────────────────────────────
        recommendations: List[str] = []

        if pass_pct < 80:
            recommendations.append(
                f"Pass rate is {pass_pct:.1f}% — investigate failing test cases "
                f"and review API contract changes."
            )
        if avg_rt is not None and avg_rt > _RT_ACCEPTABLE_MS:
            recommendations.append(
                f"Average response time {avg_rt:.0f} ms exceeds 5 000 ms SLA — "
                f"check server performance and timeouts."
            )
        if error_rate > 0.1:
            recommendations.append(
                f"Error rate is {error_rate*100:.1f}% — high execution failure "
                f"rate may indicate connectivity or configuration issues."
            )
        if error_rate > 0.5:
            recommendations.append(
                "More than 50% of executions failed — verify the API base URL "
                "and authentication configuration."
            )
        if not recommendations:
            recommendations.append("No critical issues detected. Continue monitoring.")

        report = HealthReport(
            score               = score,
            pass_rate_score     = pass_rate_score,
            response_time_score = round(rt_score, 2),
            stability_score     = stability_score,
            availability_score  = availability_score,
            recommendations     = recommendations,
        )

        logger.debug(
            "HealthAnalyzer: score=%.1f  rating=%s  "
            "(pass=%.1f  rt=%.1f  stability=%.1f  avail=%.1f)",
            score, report.rating,
            pass_rate_score, rt_score, stability_score, availability_score,
        )
        return report
