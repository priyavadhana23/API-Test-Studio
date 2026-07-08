"""
database/models.py
===================
Plain Python dataclasses that mirror each database table row exactly.

These are persistence-layer transfer objects — not the same as the
domain models in ``models/``.  They carry only the data that gets
written to or read from the database.

Naming convention: ``Db<TableName>`` to avoid confusion with domain models.

No business logic lives here.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DbEnvironment:
    """
    Mirrors one row in the ``environments`` table.

    Attributes:
        environment_name: Primary key — matches ``EnvironmentConfig.name``.
        base_url:         API base URL.
        auth_type:        Auth strategy string.
        created_at:       ISO-8601 UTC creation timestamp.
        updated_at:       ISO-8601 UTC last-update timestamp.
    """
    environment_name: str
    base_url: Optional[str]
    auth_type: str
    created_at: str
    updated_at: str


@dataclass
class DbExecutionRun:
    """
    Mirrors one row in the ``execution_runs`` table.

    One run corresponds to one full parse → generate → execute → validate
    cycle for a single API specification.
    """
    run_id: str
    execution_timestamp: str       # ISO-8601 UTC
    api_name: str
    api_version: Optional[str]
    environment_name: Optional[str]
    specification_file: Optional[str]
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
    framework_version: Optional[str]


@dataclass
class DbTestCaseResult:
    """
    Mirrors one row in the ``test_case_results`` table.

    One row per executed+validated test case.
    """
    result_id: str
    run_id: str
    test_id: str
    operation_id: Optional[str]
    endpoint: str
    http_method: str
    category: Optional[str]
    request_url: Optional[str]
    request_headers: Optional[str]   # JSON string
    request_payload: Optional[str]   # JSON string
    response_status_code: Optional[int]
    response_headers: Optional[str]  # JSON string
    response_body: Optional[str]     # JSON string or raw text
    response_time_ms: Optional[float]
    validation_status: Optional[str]
    failure_reason: Optional[str]
    validation_time_ms: Optional[float]
    executed_at: Optional[str]       # ISO-8601 UTC


@dataclass
class DbValidationDetail:
    """
    Mirrors one row in the ``validation_details`` table.

    One row per (validator, test_case_result) pair.
    """
    validation_detail_id: str
    result_id: str
    run_id: str
    validator_name: str
    status: str                     # "passed" | "failed"
    message: Optional[str]
    severity: Optional[str]
    execution_time_ms: Optional[float]
    recorded_at: str                # ISO-8601 UTC


@dataclass
class RunComparison:
    """
    Value object produced by DatabaseManager.compare_runs().

    Carries the delta between two execution runs — not stored in the DB.
    """
    run_id_a: str
    run_id_b: str
    api_name: str

    passed_a: int
    passed_b: int
    passed_delta: int

    failed_a: int
    failed_b: int
    failed_delta: int

    errors_a: int
    errors_b: int
    errors_delta: int

    pass_pct_a: float
    pass_pct_b: float
    pass_pct_delta: float

    avg_rt_a: Optional[float]
    avg_rt_b: Optional[float]
    avg_rt_delta: Optional[float]

    def summary(self) -> str:
        """Return a one-line human-readable comparison summary."""
        direction = "improved" if self.passed_delta >= 0 else "regressed"
        return (
            f"Run {self.run_id_b[:8]} vs {self.run_id_a[:8]}: "
            f"{direction} by {abs(self.passed_delta)} passed tests "
            f"(pass rate {self.pass_pct_a:.1f}% → {self.pass_pct_b:.1f}%)"
        )
