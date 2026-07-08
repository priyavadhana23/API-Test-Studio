"""
analytics/models.py
====================
Pure data models (dataclasses) produced by the Phase 7 Analytics Engine.

These objects carry computed insights — no DB access, no HTTP calls.
Phase 8 (Reports) and future dashboards will consume them directly.

Models:
    TrendPoint          — one data point on a time series
    TrendResult         — a full time-series trend
    EndpointStats       — stats for one endpoint path
    EndpointAnalysis    — aggregate endpoint-level insights
    FailureEntry        — one failure category + its count
    FailureAnalysis     — full failure distribution
    RegressionSummary   — comparison between two runs
    HealthReport        — overall API health score and rating
    AnalyticsSummary    — top-level container returned by AnalyticsManager
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Trend models
# ---------------------------------------------------------------------------

@dataclass
class TrendPoint:
    """One data point on a time series."""
    label: str          # e.g. "2026-07-07" or "Week 27"
    value: float
    run_count: int = 1


@dataclass
class TrendResult:
    """
    A named time series with statistical summary.

    Attributes:
        name:          Human-readable series name (e.g. "Pass Rate Trend").
        points:        Ordered list of ``TrendPoint`` objects.
        slope:         Linear regression slope (positive = improving).
        direction:     ``"improving"`` | ``"declining"`` | ``"stable"``.
        moving_avg:    Moving average values aligned with *points*.
    """
    name: str
    points: List[TrendPoint] = field(default_factory=list)
    slope: float = 0.0
    direction: str = "stable"
    moving_avg: List[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoint models
# ---------------------------------------------------------------------------

@dataclass
class EndpointStats:
    """Statistics for a single endpoint path."""
    endpoint: str
    method: str
    total_executions: int
    passed: int
    failed: int
    errors: int
    pass_rate: float
    avg_response_time_ms: Optional[float]
    min_response_time_ms: Optional[float]
    max_response_time_ms: Optional[float]
    p95_response_time_ms: Optional[float]


@dataclass
class EndpointAnalysis:
    """
    Aggregate endpoint-level insights across all test-case results.

    Attributes:
        most_executed:    Endpoint path with most test runs.
        least_executed:   Endpoint path with fewest test runs.
        most_failed:      Endpoint path with most failures.
        most_successful:  Endpoint path with highest pass rate.
        slowest:          Endpoint path with highest avg response time.
        fastest:          Endpoint path with lowest avg response time.
        avg_execution_count: Average number of test cases per endpoint.
        all_stats:        Full stats table keyed by endpoint path.
    """
    most_executed: Optional[str] = None
    least_executed: Optional[str] = None
    most_failed: Optional[str] = None
    most_successful: Optional[str] = None
    slowest: Optional[str] = None
    fastest: Optional[str] = None
    avg_execution_count: float = 0.0
    all_stats: List[EndpointStats] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Response time model
# ---------------------------------------------------------------------------

@dataclass
class ResponseTimeAnalysis:
    """
    Statistical summary of response times for a run or endpoint.

    Attributes:
        sample_count:       Number of timed requests.
        mean_ms:            Arithmetic mean.
        median_ms:          Median (p50).
        min_ms:             Minimum.
        max_ms:             Maximum.
        std_dev_ms:         Standard deviation.
        p95_ms:             95th percentile.
        p99_ms:             99th percentile.
        sla_threshold_ms:   The SLA threshold used for compliance check.
        sla_compliance_pct: Percentage of requests that met the SLA.
    """
    sample_count: int = 0
    mean_ms: Optional[float] = None
    median_ms: Optional[float] = None
    min_ms: Optional[float] = None
    max_ms: Optional[float] = None
    std_dev_ms: Optional[float] = None
    p95_ms: Optional[float] = None
    p99_ms: Optional[float] = None
    sla_threshold_ms: float = 5000.0
    sla_compliance_pct: float = 0.0


# ---------------------------------------------------------------------------
# Failure models
# ---------------------------------------------------------------------------

@dataclass
class FailureEntry:
    """One category of failure with its count and percentage."""
    category: str
    count: int
    percentage: float
    sample_message: Optional[str] = None


@dataclass
class FailureAnalysis:
    """
    Full failure distribution for a run.

    Attributes:
        total_failures:       All failed + error results.
        validation_failures:  Failures due to assertion mismatch.
        execution_errors:     Failures due to connection/timeout errors.
        timeout_failures:     Subset of execution errors that are timeouts.
        auth_failures:        Auth-related failures (401/403).
        schema_failures:      Schema validation failures.
        business_rule_failures: Business rule failures.
        top_failures:         Top-10 most common failure messages.
        distribution:         All failure categories with counts.
    """
    total_failures: int = 0
    validation_failures: int = 0
    execution_errors: int = 0
    timeout_failures: int = 0
    auth_failures: int = 0
    schema_failures: int = 0
    business_rule_failures: int = 0
    top_failures: List[FailureEntry] = field(default_factory=list)
    distribution: List[FailureEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Regression model
# ---------------------------------------------------------------------------

@dataclass
class RegressionSummary:
    """
    Comparison between two execution runs.

    Attributes:
        run_id_baseline:  The older (reference) run ID.
        run_id_current:   The newer (comparison) run ID.
        api_name:         API being compared.
        new_failures:     Endpoints/operations that newly failed.
        fixed_failures:   Endpoints/operations that now pass (were failing).
        unchanged_failures: Still failing in both runs.
        pass_rate_delta:  Positive = improvement.
        avg_rt_delta_ms:  Positive = slower; negative = faster.
        has_regression:   ``True`` if new_failures is non-empty.
        verdict:          Human-readable summary.
    """
    run_id_baseline: str = ""
    run_id_current: str = ""
    api_name: str = ""
    new_failures: List[str] = field(default_factory=list)
    fixed_failures: List[str] = field(default_factory=list)
    unchanged_failures: List[str] = field(default_factory=list)
    pass_rate_delta: float = 0.0
    avg_rt_delta_ms: Optional[float] = None
    has_regression: bool = False
    verdict: str = "No comparison available"


# ---------------------------------------------------------------------------
# Health model
# ---------------------------------------------------------------------------

# Health rating thresholds
HEALTH_EXCELLENT    = 95
HEALTH_GOOD         = 80
HEALTH_NEEDS_ATTN   = 60


@dataclass
class HealthReport:
    """
    Overall API health score for a single execution run.

    Score range: 0–100.

    Attributes:
        score:            Weighted composite health score.
        rating:           ``"Excellent"`` | ``"Good"`` | ``"Needs Attention"`` | ``"Critical"``.
        pass_rate_score:  Component score from pass rate (0–40 points).
        response_time_score: Component score from response time (0–30 points).
        stability_score:  Component score from error rate (0–20 points).
        availability_score: Component score (0–10 points) — 1 if run completed.
        recommendations:  List of human-readable improvement suggestions.
    """
    score: float = 0.0
    rating: str = "Critical"
    pass_rate_score: float = 0.0
    response_time_score: float = 0.0
    stability_score: float = 0.0
    availability_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.rating = self._compute_rating()

    def _compute_rating(self) -> str:
        if self.score >= HEALTH_EXCELLENT:
            return "Excellent"
        if self.score >= HEALTH_GOOD:
            return "Good"
        if self.score >= HEALTH_NEEDS_ATTN:
            return "Needs Attention"
        return "Critical"


# ---------------------------------------------------------------------------
# Top-level analytics summary
# ---------------------------------------------------------------------------

@dataclass
class AnalyticsSummary:
    """
    Top-level container returned by ``AnalyticsManager.run_analysis()``.

    All Phase 8 reports consume this object — they never recalculate metrics.

    Attributes:
        run_id:             The run that was analysed.
        api_name:           API name.
        total_runs:         Total runs in the database for this API.
        trend:              Pass-rate trend across all runs.
        endpoint_analysis:  Endpoint-level statistics.
        response_time:      Response-time statistical summary.
        failure_analysis:   Failure distribution.
        regression:         Regression comparison (latest vs previous run).
        health:             API health report.
        generated_at:       ISO-8601 UTC timestamp.
    """
    run_id: str = ""
    api_name: str = ""
    total_runs: int = 0
    trend: Optional[TrendResult] = None
    endpoint_analysis: Optional[EndpointAnalysis] = None
    response_time: Optional[ResponseTimeAnalysis] = None
    failure_analysis: Optional[FailureAnalysis] = None
    regression: Optional[RegressionSummary] = None
    health: Optional[HealthReport] = None
    generated_at: str = ""
