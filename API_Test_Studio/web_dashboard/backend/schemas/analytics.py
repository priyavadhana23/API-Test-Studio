"""
web_dashboard/backend/schemas/analytics.py
===========================================
Pydantic response model for GET /api/analytics/{run_id}.

Serialises the AnalyticsSummary dataclass from analytics/models.py into
a JSON-safe Pydantic model without duplicating any calculation logic.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class TrendPointSchema(BaseModel):
    label: str
    value: float
    run_count: int = 1


class TrendResultSchema(BaseModel):
    name: str
    points: List[TrendPointSchema]
    slope: float
    direction: str
    moving_avg: List[float]


class EndpointStatsSchema(BaseModel):
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


class EndpointAnalysisSchema(BaseModel):
    most_executed: Optional[str]
    least_executed: Optional[str]
    most_failed: Optional[str]
    most_successful: Optional[str]
    slowest: Optional[str]
    fastest: Optional[str]
    avg_execution_count: float
    all_stats: List[EndpointStatsSchema]


class ResponseTimeSchema(BaseModel):
    sample_count: int
    mean_ms: Optional[float]
    median_ms: Optional[float]
    min_ms: Optional[float]
    max_ms: Optional[float]
    std_dev_ms: Optional[float]
    p95_ms: Optional[float]
    p99_ms: Optional[float]
    sla_threshold_ms: float
    sla_compliance_pct: float


class FailureEntrySchema(BaseModel):
    category: str
    count: int
    percentage: float
    sample_message: Optional[str]


class FailureAnalysisSchema(BaseModel):
    total_failures: int
    validation_failures: int
    execution_errors: int
    timeout_failures: int
    auth_failures: int
    schema_failures: int
    business_rule_failures: int
    top_failures: List[FailureEntrySchema]
    distribution: List[FailureEntrySchema]


class RegressionSchema(BaseModel):
    run_id_baseline: str
    run_id_current: str
    api_name: str
    new_failures: List[str]
    fixed_failures: List[str]
    unchanged_failures: List[str]
    pass_rate_delta: float
    avg_rt_delta_ms: Optional[float]
    has_regression: bool
    verdict: str


class HealthSchema(BaseModel):
    score: float
    rating: str
    pass_rate_score: float
    response_time_score: float
    stability_score: float
    availability_score: float
    recommendations: List[str]


class AnalyticsSummarySchema(BaseModel):
    """Serialised form of analytics.models.AnalyticsSummary."""
    run_id: str
    api_name: str
    total_runs: int
    generated_at: str
    trend: Optional[TrendResultSchema]
    endpoint_analysis: Optional[EndpointAnalysisSchema]
    response_time: Optional[ResponseTimeSchema]
    failure_analysis: Optional[FailureAnalysisSchema]
    regression: Optional[RegressionSchema]
    health: Optional[HealthSchema]
