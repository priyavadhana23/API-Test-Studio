"""
exceptions/validation_exceptions.py
=====================================
Custom exceptions for the response validation layer.

Raised by:
    - validators/  (Phase 4)

Hierarchy:
    ValidationError
    ├── AssertionFailedError
    ├── SchemaValidationError
    └── MissingFieldError
"""
from typing import Any


class ValidationError(Exception):
    """
    Base class for all response validation errors.

    Catch this to handle any validation problem without caring about the
    specific subtype.
    """


class AssertionFailedError(ValidationError):
    """
    Raised when an assertion rule evaluates to ``False`` against the
    actual response.

    Args:
        assertion_id:    The ID of the failing assertion.
        operator:        The comparison operator that was applied.
        expected:        The expected value.
        actual:          The actual value extracted from the response.
        description:     Human-readable description of what was checked.

    Example::

        raise AssertionFailedError(
            assertion_id="a_001",
            operator="equals",
            expected=200,
            actual=404,
            description="status_code should be 200"
        )
    """

    def __init__(
        self,
        assertion_id: str,
        operator: str,
        expected: Any,
        actual: Any,
        description: str = "",
    ) -> None:
        self.assertion_id = assertion_id
        self.operator = operator
        self.expected = expected
        self.actual = actual
        self.description = description
        super().__init__(
            f"Assertion '{assertion_id}' failed [{description}]: "
            f"expected {expected!r} {operator} actual {actual!r}"
        )


class SchemaValidationError(ValidationError):
    """
    Raised when a response body does not conform to the expected JSON
    Schema declared in the API specification.

    Args:
        endpoint:       The endpoint path and method (for context).
        schema_path:    The JSON pointer path within the schema where
                        the violation occurred.
        message:        The validation error message from the schema validator.
    """

    def __init__(self, endpoint: str, schema_path: str, message: str) -> None:
        self.endpoint = endpoint
        self.schema_path = schema_path
        super().__init__(
            f"Schema validation failed for '{endpoint}' at '{schema_path}': {message}"
        )


class MissingFieldError(ValidationError):
    """
    Raised when a required field is absent from the response body or
    headers.

    Args:
        field_name:  The name or JSONPath of the missing field.
        location:    Where the field was expected (e.g. ``"body"``, ``"headers"``).
    """

    def __init__(self, field_name: str, location: str = "body") -> None:
        self.field_name = field_name
        self.location = location
        super().__init__(
            f"Required field '{field_name}' is missing from the response {location}."
        )
