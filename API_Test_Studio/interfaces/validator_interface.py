"""
interfaces/validator_interface.py
===================================
Abstract base class that every response validator must implement.

Why this matters:
    Phase 4 will ship multiple validator strategies:
        - StatusCodeValidator
        - JsonPathValidator
        - SchemaValidator
        - HeaderValidator
        - ResponseTimeValidator
        - RegexValidator

    The executor runs them all through the same interface without knowing
    which specific validator it is invoking.

Contract:
    Any class that inherits ``IValidator`` MUST implement:
        - supports()    → declare which ValidationType this validator handles
        - validate()    → evaluate an assertion against a response

Usage (Phase 4):
    from interfaces.validator_interface import IValidator
    from models.test_case import Assertion
    from models.execution_result import AssertionResult

    class StatusCodeValidator(IValidator):
        def supports(self, validation_type: str) -> bool:
            return validation_type == ValidationType.STATUS_CODE

        def validate(self, assertion, response_data) -> AssertionResult:
            ...
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from models.test_case import Assertion
from models.execution_result import AssertionResult


class IValidator(ABC):
    """
    Interface (abstract base class) for all response validators.

    Concrete implementations (Phase 4):
        - StatusCodeValidator
        - JsonPathValidator
        - SchemaValidator
        - HeaderValidator
        - ResponseTimeValidator
        - RegexValidator

    A ``ValidatorFactory`` or ``ValidatorChain`` will call ``supports()``
    on each registered validator to dispatch the right one for each
    assertion type.
    """

    @abstractmethod
    def supports(self, validation_type: str) -> bool:
        """
        Return ``True`` if this validator handles the given validation type.

        Called by the validator dispatcher to route each ``Assertion`` to
        the correct implementation.

        Args:
            validation_type: A ``ValidationType`` constant string
                             (e.g. ``"status_code"``, ``"json_path"``).

        Returns:
            ``True`` if this validator should handle the given type.
        """

    @abstractmethod
    def validate(
        self,
        assertion: Assertion,
        response_data: Dict[str, Any],
    ) -> AssertionResult:
        """
        Evaluate *assertion* against *response_data* and return the result.

        Args:
            assertion:     The ``Assertion`` rule to evaluate.
            response_data: A dictionary containing the HTTP response fields
                           that validators can inspect.  Standardised keys:

                           - ``"status_code"``   (int)
                           - ``"headers"``        (dict)
                           - ``"body"``           (parsed JSON or raw string)
                           - ``"response_time_ms"`` (float)

        Returns:
            An ``AssertionResult`` instance describing whether the
            assertion passed and what the actual vs expected values were.

        Raises:
            ValidationError: On an unexpected error during evaluation
                             (not on assertion failure — that is expressed
                             via ``AssertionResult.passed = False``).
        """

    @property
    def validator_name(self) -> str:
        """
        Human-readable name for this validator, used in logs and reports.

        Override in subclasses to provide a meaningful name, e.g.
        ``"JSON Path Validator"``.  Defaults to the class name.
        """
        return self.__class__.__name__
