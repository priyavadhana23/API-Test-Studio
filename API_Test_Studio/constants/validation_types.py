"""
constants/validation_types.py
==============================
Enumerations for all validation-related categories in API Test Studio.

These constants are used by:
    - Test case generators  (future phase)
    - Response validators   (future phase)
    - Report builders       (future phase)

Usage:
    from constants.validation_types import ValidationType, AssertionOperator

    v = ValidationType.STATUS_CODE
    op = AssertionOperator.EQUALS
"""

from enum import Enum


class ValidationType(str, Enum):
    """
    Categories of validation that can be applied to an API response.

    Inherits from ``str`` for easy serialization to JSON/YAML.
    """

    STATUS_CODE = "status_code"
    """Validate the HTTP response status code."""

    RESPONSE_BODY = "response_body"
    """Validate one or more fields inside the response body."""

    RESPONSE_SCHEMA = "response_schema"
    """Validate the response body against a JSON Schema."""

    RESPONSE_HEADER = "response_header"
    """Validate the presence or value of a response header."""

    RESPONSE_TIME = "response_time"
    """Validate that response time is within an acceptable threshold."""

    CONTENT_TYPE = "content_type"
    """Validate the Content-Type response header."""

    JSON_PATH = "json_path"
    """Validate a value extracted via JSONPath expression."""

    REGEX = "regex"
    """Validate a value against a regular expression."""

    NOT_EMPTY = "not_empty"
    """Validate that a field or response body is not empty."""

    CUSTOM = "custom"
    """Placeholder for custom validation logic (future extension)."""


class AssertionOperator(str, Enum):
    """
    Comparison operators used when building assertion rules.

    Example usage::

        # "status_code EQUALS 200"
        AssertionOperator.EQUALS

        # "response_time LESS_THAN 500"
        AssertionOperator.LESS_THAN
    """

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    MATCHES_REGEX = "matches_regex"
    IN = "in"
    NOT_IN = "not_in"


class TestStatus(str, Enum):
    """
    Lifecycle / result status for a test case or test run.
    """

    PENDING = "pending"
    """Test is queued but has not yet started."""

    RUNNING = "running"
    """Test is currently executing."""

    PASSED = "passed"
    """All assertions passed."""

    FAILED = "failed"
    """One or more assertions failed."""

    SKIPPED = "skipped"
    """Test was intentionally skipped."""

    ERROR = "error"
    """An unexpected error occurred during execution (not a test failure)."""

    BLOCKED = "blocked"
    """Test could not run due to a dependency failure."""


class Severity(str, Enum):
    """
    Importance / priority classification for test cases.
    """

    CRITICAL = "critical"
    """Must pass. Failure blocks further testing."""

    HIGH = "high"
    """Important; failure indicates significant regression."""

    MEDIUM = "medium"
    """Standard test; failure is notable but not blocking."""

    LOW = "low"
    """Nice-to-have; failure is informational only."""
