"""
reporting/report_models.py
============================
Report-specific data models that aggregate pre-computed analytics into
presentation-ready structures.

These are NOT analytics models — they contain no calculations.
They receive already-computed values from AnalyticsSummary / DbExecutionRun
and reshape them into exactly what each report format needs.

No SQL. No HTTP. No statistics calculations. Pure presentation data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ReportMetadata:
    """
    Header information attached to every report.

    Attributes:
        report_id:       Unique ID for this report file.
        generated_at:    ISO-8601 UTC timestamp of report generation.
        framework_name:  Always "API Test Studio".
        framework_version: e.g. "1.0.0".
        run_id:          The execution run this report covers.
        api_name:        API being reported on.
        environment:     Environment name (e.g. "Development").
        report_formats:  List of format strings generated, e.g. ["html","pdf"].
    """
    report_id: str
    generated_at: str
    framework_name: str
    framework_version: str
    run_id: str
    api_name: str
    environment: str = ""
    report_formats: List[str] = field(default_factory=list)


@dataclass
class ExecutiveSummary:
    """
    High-level numbers shown at the very top of every report.

    All values are pre-computed — this model only stores them for rendering.
    """
    api_name: str
    api_version: str
    execution_date: str
    environment: str
    total_endpoints: int
    total_test_cases: int
    total_executed: int
    passed: int
    failed: int
    skipped: int
    errors: int
    pass_percentage: float
    avg_response_time_ms: Optional[float]
    total_execution_time_s: Optional[float]
    health_score: float
    health_rating: str
    specification_file: str = ""
    framework_version: str = ""


@dataclass
class ValidatorRow:
    """One row in the validator statistics table."""
    validator_name: str
    passed: int
    failed: int
    total: int
    pass_rate: float


@dataclass
class ValidationSummary:
    """
    Validator-level statistics for the report's validation section.

    Aggregated from DbValidationDetail rows — no raw assertions here.
    """
    validators: List[ValidatorRow] = field(default_factory=list)
    total_assertions: int = 0
    total_passed: int = 0
    total_failed: int = 0


@dataclass
class ChartData:
    """
    Pre-rendered Plotly chart as an HTML div string.

    Attributes:
        chart_id:    Unique HTML element id (used in templates).
        title:       Chart title for accessibility.
        html:        The ``<div>`` block returned by ``plotly.offline.plot()``.
        chart_type:  ``"pie"`` | ``"bar"`` | ``"line"`` | ``"gauge"``.
    """
    chart_id: str
    title: str
    html: str
    chart_type: str = "bar"


@dataclass
class TestResultRow:
    """One row in the detailed test-results table."""
    result_id: str
    operation_id: str
    endpoint: str
    method: str
    category: str
    status: str
    response_status_code: Optional[int]
    response_time_ms: Optional[float]
    validation_status: str
    failure_reason: str
    executed_at: str


@dataclass
class DetailedResults:
    """
    The full test-case results table for the HTML report.

    Attributes:
        rows:         List of ``TestResultRow`` objects.
        total:        Total rows.
        passed_count: Rows with validation_status == "passed".
        failed_count: Rows with validation_status == "failed".
        error_count:  Rows with validation_status == "error".
    """
    rows: List[TestResultRow] = field(default_factory=list)
    total: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0


@dataclass
class ComparisonSummary:
    """
    Side-by-side comparison data for the comparison report.

    All delta values are pre-computed by the Analytics RegressionSummary.
    """
    api_name: str
    run_id_baseline: str
    run_id_current: str
    timestamp_baseline: str
    timestamp_current: str

    passed_baseline: int
    passed_current: int
    passed_delta: int

    failed_baseline: int
    failed_current: int
    failed_delta: int

    pass_pct_baseline: float
    pass_pct_current: float
    pass_pct_delta: float

    health_baseline: float
    health_current: float
    health_delta: float

    avg_rt_baseline: Optional[float]
    avg_rt_current: Optional[float]
    avg_rt_delta: Optional[float]

    new_failures: List[str] = field(default_factory=list)
    fixed_failures: List[str] = field(default_factory=list)
    unchanged_failures: List[str] = field(default_factory=list)
    verdict: str = ""
    has_regression: bool = False


@dataclass
class ReportBundle:
    """
    Top-level container carrying all data for one report generation run.

    All generators receive a ``ReportBundle`` and render only their section.
    The bundle is assembled once by ``ReportManager`` and shared.

    Attributes:
        metadata:          Report header information.
        executive_summary: Top-level numbers.
        validation_summary: Validator statistics.
        charts:            Pre-rendered Plotly chart divs keyed by chart_id.
        detailed_results:  Full test-case table.
        comparison:        Optional run comparison data.
        analytics:         Original ``AnalyticsSummary`` for template access.
        run:               Original ``DbExecutionRun`` row.
    """
    metadata: Optional[ReportMetadata] = None
    executive_summary: Optional[ExecutiveSummary] = None
    validation_summary: Optional[ValidationSummary] = None
    charts: Dict[str, ChartData] = field(default_factory=dict)
    detailed_results: Optional[DetailedResults] = None
    comparison: Optional[ComparisonSummary] = None
    analytics: Optional[Any] = None   # AnalyticsSummary
    run: Optional[Any] = None          # DbExecutionRun
