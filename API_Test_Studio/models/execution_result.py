"""
models/execution_result.py
==========================
Dataclasses representing the outcome of executing a single test case.

These models are populated by the executor module (Phase 4+).
No execution logic lives here — pure data structures only.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from constants.validation_types import TestStatus


@dataclass
class AssertionResult:
    """
    The evaluated outcome of one ``Assertion`` from a test case.

    Attributes:
        assertion_id:    References the parent ``Assertion.assertion_id``.
        passed:          ``True`` if the assertion succeeded.
        actual_value:    The value extracted from the response.
        expected_value:  The value that was expected.
        message:         Human-readable explanation of the outcome.
    """

    assertion_id: str
    passed: bool
    actual_value: Any
    expected_value: Any
    message: Optional[str] = None

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"AssertionResult(id={self.assertion_id!r}, status={status}, "
            f"expected={self.expected_value!r}, actual={self.actual_value!r})"
        )


@dataclass
class ExecutionResult:
    """
    The complete outcome of executing one ``TestCase``.

    Attributes:
        result_id:          Unique identifier for this result record.
        test_id:            References the parent ``TestCase.test_id``.
        run_id:             Groups results from the same test-run batch.
        status:             Final test status (passed, failed, error, …).
        http_status_code:   The actual HTTP status code received.
        response_headers:   Response headers as a dictionary.
        response_body:      Raw response body (string or parsed object).
        response_time_ms:   End-to-end response time in milliseconds.
        assertion_results:  Ordered list of ``AssertionResult`` instances.
        error_message:      Error details if the test could not complete.
        request_url:        Fully resolved URL that was called.
        request_headers:    Headers actually sent in the request.
        request_body:       Body actually sent in the request.
        executed_at:        UTC timestamp of when execution started.
        duration_ms:        Total execution duration in milliseconds
                            (may differ from response_time_ms if retries occurred).
    """

    result_id: str
    test_id: str
    run_id: str
    status: str  # Use TestStatus constants

    http_status_code: Optional[int] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    response_body: Optional[Any] = None
    response_time_ms: Optional[float] = None

    assertion_results: List[AssertionResult] = field(default_factory=list)
    error_message: Optional[str] = None

    request_url: Optional[str] = None
    request_headers: Dict[str, str] = field(default_factory=dict)
    request_body: Optional[Any] = None

    executed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None

    def __post_init__(self) -> None:
        if self.executed_at is None:
            from datetime import timezone
            self.executed_at = datetime.now(tz=timezone.utc)

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def passed(self) -> bool:
        """Return ``True`` if the test case passed."""
        return self.status == TestStatus.PASSED.value

    @property
    def failed(self) -> bool:
        """Return ``True`` if the test case failed."""
        return self.status == TestStatus.FAILED.value

    @property
    def total_assertions(self) -> int:
        """Total number of assertions that were evaluated."""
        return len(self.assertion_results)

    @property
    def passed_assertions(self) -> int:
        """Number of assertions that passed."""
        return sum(1 for r in self.assertion_results if r.passed)

    @property
    def failed_assertions(self) -> int:
        """Number of assertions that failed."""
        return sum(1 for r in self.assertion_results if not r.passed)

    def __repr__(self) -> str:
        return (
            f"ExecutionResult(id={self.result_id!r}, test_id={self.test_id!r}, "
            f"status={self.status!r}, http={self.http_status_code}, "
            f"assertions={self.passed_assertions}/{self.total_assertions})"
        )
