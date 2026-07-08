"""
validators/validation_utils.py
================================
Shared, stateless utilities for the validation layer.

Responsibilities:
    - Build the standardised ``response_data`` dict every validator receives
    - Evaluate assertion operators (equals, contains, less_than, …)
    - Construct ``AssertionResult`` pass/fail objects consistently
    - Extract nested JSON values by dot-notation or JSONPath-lite
    - Provide a ``ValidationResult`` dataclass (the output of one full
      validation run for one ExecutionResult)

No HTTP I/O.  No assertion logic beyond the operator table.
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from constants.validation_types import AssertionOperator, TestStatus, Severity
from models.execution_result import AssertionResult, ExecutionResult
from models.test_case import Assertion, TestCase
from utilities.common_helpers import generate_id
from utilities.logger import get_logger

logger = get_logger(__name__)


# ===========================================================================
# ValidationResult — the single output produced by ValidationManager
# ===========================================================================

@dataclass
class ValidationResult:
    """
    The complete validation outcome for one executed test case.

    Produced by ``ValidationManager.validate()`` after all applicable
    validators have run against a single ``ExecutionResult``.

    Attributes:
        validation_id:       Unique ID for this validation record.
        test_id:             References the parent ``TestCase.test_id``.
        result_id:           References the parent ``ExecutionResult.result_id``.
        operation_id:        Operation ID from the test case tags (for display).
        test_name:           Human-readable test case name.
        overall_status:      ``"passed"`` | ``"failed"`` | ``"error"`` | ``"skipped"``.
        passed_validators:   Names of validators that passed.
        failed_validators:   Names of validators that failed.
        assertion_results:   All individual ``AssertionResult`` records.
        failure_messages:    Human-readable failure descriptions.
        severity:            Severity of the test case.
        validated_at:        UTC timestamp of when validation completed.
        validation_time_ms:  Wall-clock time taken for all validators to run.
        http_status_code:    The actual HTTP status code (for display).
        request_url:         The URL that was called (for display).
    """

    validation_id: str
    test_id: str
    result_id: str
    operation_id: str
    test_name: str
    overall_status: str

    passed_validators: List[str] = field(default_factory=list)
    failed_validators: List[str] = field(default_factory=list)
    assertion_results: List[AssertionResult] = field(default_factory=list)
    failure_messages: List[str] = field(default_factory=list)
    severity: str = Severity.MEDIUM.value
    validated_at: Optional[datetime] = None
    validation_time_ms: float = 0.0
    http_status_code: Optional[int] = None
    request_url: Optional[str] = None

    def __post_init__(self) -> None:
        if self.validated_at is None:
            self.validated_at = datetime.now(tz=timezone.utc)

    @property
    def passed(self) -> bool:
        return self.overall_status == TestStatus.PASSED.value

    @property
    def failed(self) -> bool:
        return self.overall_status == TestStatus.FAILED.value

    @property
    def total_assertions(self) -> int:
        return len(self.assertion_results)

    @property
    def passed_assertion_count(self) -> int:
        return sum(1 for r in self.assertion_results if r.passed)

    @property
    def failed_assertion_count(self) -> int:
        return sum(1 for r in self.assertion_results if not r.passed)

    def __repr__(self) -> str:
        return (
            f"ValidationResult(test={self.test_name!r}, "
            f"status={self.overall_status!r}, "
            f"passed={self.passed_assertion_count}/{self.total_assertions})"
        )


# ===========================================================================
# response_data builder
# ===========================================================================

def build_response_data(execution_result: ExecutionResult) -> Dict[str, Any]:
    """
    Convert an ``ExecutionResult`` into the standardised ``response_data``
    dictionary consumed by every validator.

    Standardised keys:
        - ``status_code``       (int | None)
        - ``headers``           (dict, lower-cased keys)
        - ``body``              (parsed JSON dict/list, or raw string, or None)
        - ``response_time_ms``  (float | None)
        - ``content_type``      (str | None)
        - ``response_size``     (int — byte-length of body string representation)
        - ``error_message``     (str | None)
        - ``request_url``       (str | None)

    Args:
        execution_result: The ``ExecutionResult`` from Phase 4.

    Returns:
        Standardised dict for validators to inspect.
    """
    # Lower-case all header keys for case-insensitive lookup
    headers = {k.lower(): v for k, v in (execution_result.response_headers or {}).items()}
    content_type = headers.get("content-type")

    body = execution_result.response_body
    body_size = len(str(body)) if body is not None else 0

    return {
        "status_code":      execution_result.http_status_code,
        "headers":          headers,
        "body":             body,
        "response_time_ms": execution_result.response_time_ms,
        "content_type":     content_type,
        "response_size":    body_size,
        "error_message":    execution_result.error_message,
        "request_url":      execution_result.request_url,
    }


# ===========================================================================
# AssertionResult factories
# ===========================================================================

def make_pass(assertion: Assertion, actual: Any, message: str = "") -> AssertionResult:
    """
    Build a passing ``AssertionResult`` for *assertion*.

    Args:
        assertion: The ``Assertion`` that was evaluated.
        actual:    The actual value extracted from the response.
        message:   Optional supplementary message.

    Returns:
        ``AssertionResult`` with ``passed=True``.
    """
    return AssertionResult(
        assertion_id=assertion.assertion_id,
        passed=True,
        actual_value=actual,
        expected_value=assertion.expected_value,
        message=message or f"PASS: {assertion.description or assertion.validation_type}",
    )


def make_fail(assertion: Assertion, actual: Any, reason: str) -> AssertionResult:
    """
    Build a failing ``AssertionResult`` for *assertion*.

    Args:
        assertion: The ``Assertion`` that was evaluated.
        actual:    The actual value extracted from the response.
        reason:    Human-readable failure description.

    Returns:
        ``AssertionResult`` with ``passed=False``.
    """
    return AssertionResult(
        assertion_id=assertion.assertion_id,
        passed=False,
        actual_value=actual,
        expected_value=assertion.expected_value,
        message=f"FAIL: {reason}",
    )


def make_error(assertion: Assertion, error: Exception) -> AssertionResult:
    """
    Build an error ``AssertionResult`` for an unexpected exception.

    Args:
        assertion: The ``Assertion`` being evaluated when the error occurred.
        error:     The exception that was raised.

    Returns:
        ``AssertionResult`` with ``passed=False`` and an error message.
    """
    return AssertionResult(
        assertion_id=assertion.assertion_id,
        passed=False,
        actual_value=None,
        expected_value=assertion.expected_value,
        message=f"ERROR during validation: {type(error).__name__}: {error}",
    )


# ===========================================================================
# Operator evaluator
# ===========================================================================

def evaluate_operator(
    actual: Any,
    operator: str,
    expected: Any,
) -> Tuple[bool, str]:
    """
    Apply *operator* to compare *actual* against *expected*.

    Supports all ``AssertionOperator`` values.

    Args:
        actual:   The value extracted from the response.
        operator: An ``AssertionOperator`` string value.
        expected: The value to compare against.

    Returns:
        A tuple ``(passed: bool, reason: str)`` where *reason* describes
        the result (useful both for pass messages and failure messages).
    """
    op = operator.lower()

    try:
        # ── Null checks ────────────────────────────────────────────────
        if op == AssertionOperator.IS_NULL.value:
            passed = actual is None
            return passed, f"actual={actual!r} is {'null' if passed else 'not null'}"

        if op == AssertionOperator.IS_NOT_NULL.value:
            passed = actual is not None
            return passed, f"actual={actual!r} is {'not null' if passed else 'null'}"

        # ── Equality ───────────────────────────────────────────────────
        if op == AssertionOperator.EQUALS.value:
            # Coerce types for numeric comparisons (e.g. expected=200 int vs actual=200 int)
            passed = _coerce_equal(actual, expected)
            return passed, f"actual={actual!r} {'==' if passed else '!='} expected={expected!r}"

        if op == AssertionOperator.NOT_EQUALS.value:
            passed = not _coerce_equal(actual, expected)
            return passed, f"actual={actual!r} {'!=' if passed else '=='} expected={expected!r}"

        # ── String containment ─────────────────────────────────────────
        if op == AssertionOperator.CONTAINS.value:
            passed = expected in str(actual) if actual is not None else False
            return passed, f"'{expected}' {'found in' if passed else 'not found in'} '{actual}'"

        if op == AssertionOperator.NOT_CONTAINS.value:
            passed = expected not in str(actual) if actual is not None else True
            return passed, f"'{expected}' {'not found in' if passed else 'found in'} '{actual}'"

        if op == AssertionOperator.STARTS_WITH.value:
            s = str(actual) if actual is not None else ""
            passed = s.startswith(str(expected))
            return passed, f"'{s}' {'starts with' if passed else 'does not start with'} '{expected}'"

        if op == AssertionOperator.ENDS_WITH.value:
            s = str(actual) if actual is not None else ""
            passed = s.endswith(str(expected))
            return passed, f"'{s}' {'ends with' if passed else 'does not end with'} '{expected}'"

        # ── Numeric comparisons ────────────────────────────────────────
        if op == AssertionOperator.GREATER_THAN.value:
            passed = float(actual) > float(expected)
            return passed, f"{actual} {'>' if passed else '<='} {expected}"

        if op == AssertionOperator.LESS_THAN.value:
            passed = float(actual) < float(expected)
            return passed, f"{actual} {'<' if passed else '>='} {expected}"

        if op == AssertionOperator.GREATER_THAN_OR_EQUAL.value:
            passed = float(actual) >= float(expected)
            return passed, f"{actual} {'>=' if passed else '<'} {expected}"

        if op == AssertionOperator.LESS_THAN_OR_EQUAL.value:
            passed = float(actual) <= float(expected)
            return passed, f"{actual} {'<=' if passed else '>'} {expected}"

        # ── Membership ─────────────────────────────────────────────────
        if op == AssertionOperator.IN.value:
            passed = actual in expected if hasattr(expected, "__contains__") else False
            return passed, f"{actual!r} {'in' if passed else 'not in'} {expected!r}"

        if op == AssertionOperator.NOT_IN.value:
            passed = actual not in expected if hasattr(expected, "__contains__") else True
            return passed, f"{actual!r} {'not in' if passed else 'in'} {expected!r}"

        # ── Regex ──────────────────────────────────────────────────────
        if op == AssertionOperator.MATCHES_REGEX.value:
            passed = bool(re.search(str(expected), str(actual)))
            return passed, f"'{actual}' {'matches' if passed else 'does not match'} regex '{expected}'"

        # ── Unknown operator ───────────────────────────────────────────
        return False, f"Unknown operator: '{operator}'"

    except (TypeError, ValueError) as exc:
        return False, f"Type error during comparison: {exc}"


def _coerce_equal(actual: Any, expected: Any) -> bool:
    """
    Compare two values with lightweight type coercion.

    Handles the common case where a spec declares ``expected=200`` (int)
    and the response carries ``status_code=200`` (also int) but some paths
    produce strings.

    Args:
        actual:   Actual value.
        expected: Expected value.

    Returns:
        ``True`` if they are considered equal after coercion.
    """
    if actual == expected:
        return True
    # Try numeric coercion
    try:
        return float(actual) == float(expected)
    except (TypeError, ValueError):
        pass
    # Try string comparison
    return str(actual).strip() == str(expected).strip()


# ===========================================================================
# JSON field extraction (dot-notation)
# ===========================================================================

def extract_json_field(body: Any, path: str) -> Tuple[Any, bool]:
    """
    Extract a value from a nested JSON body using dot-notation path.

    Example::

        extract_json_field({"user": {"id": 42}}, "user.id")  → (42, True)
        extract_json_field({"user": {}}, "user.id")           → (None, False)

    Supports:
        - Dot-notation for nested dicts: ``"a.b.c"``
        - Array index access: ``"items.0.name"``

    Args:
        body: Parsed JSON body (dict, list, or scalar).
        path: Dot-separated field path string.

    Returns:
        A tuple ``(value, found)`` where *found* is ``False`` if any
        key in the path is absent.
    """
    if not path or body is None:
        return None, False

    parts = path.split(".")
    current = body

    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                return None, False
            current = current[part]
        elif isinstance(current, list):
            try:
                idx = int(part)
                current = current[idx]
            except (ValueError, IndexError):
                return None, False
        else:
            return None, False

    return current, True


# ===========================================================================
# ValidationResult factory
# ===========================================================================

def build_validation_result(
    test_case: TestCase,
    execution_result: ExecutionResult,
    assertion_results: List[AssertionResult],
    passed_validators: List[str],
    failed_validators: List[str],
    validation_time_ms: float,
) -> ValidationResult:
    """
    Assemble the final ``ValidationResult`` from all collected data.

    The overall status is:
        - ``"error"``   if Phase 4 reported an execution error (no response)
        - ``"failed"``  if any assertion failed
        - ``"passed"``  if all assertions passed
        - ``"skipped"`` if there were no assertions to evaluate

    Args:
        test_case:          The ``TestCase`` that was validated.
        execution_result:   The ``ExecutionResult`` from Phase 4.
        assertion_results:  All ``AssertionResult`` records.
        passed_validators:  Names of validators that passed.
        failed_validators:  Names of validators that failed.
        validation_time_ms: Wall-clock time for all validators.

    Returns:
        A fully populated ``ValidationResult``.
    """
    # Determine overall status
    if execution_result.status == TestStatus.ERROR.value:
        overall = TestStatus.ERROR.value
    elif not assertion_results:
        overall = TestStatus.SKIPPED.value
    elif all(r.passed for r in assertion_results):
        overall = TestStatus.PASSED.value
    else:
        overall = TestStatus.FAILED.value

    failure_messages = [
        r.message for r in assertion_results
        if not r.passed and r.message
    ]

    # Extract operation_id from tags (it's always the third tag by convention)
    operation_id = ""
    for tag in (test_case.tags or []):
        if tag not in ("positive", "negative", "boundary", "security",
                       "enum", "auth", "header", "method", "query_param",
                       "path_param", "request_body", "null", "empty",
                       "datatype",
                       test_case.method.lower()):
            operation_id = tag
            break

    return ValidationResult(
        validation_id=generate_id("val_"),
        test_id=test_case.test_id,
        result_id=execution_result.result_id,
        operation_id=operation_id,
        test_name=test_case.name,
        overall_status=overall,
        passed_validators=passed_validators,
        failed_validators=failed_validators,
        assertion_results=assertion_results,
        failure_messages=failure_messages,
        severity=test_case.severity,
        validation_time_ms=round(validation_time_ms, 3),
        http_status_code=execution_result.http_status_code,
        request_url=execution_result.request_url,
    )
