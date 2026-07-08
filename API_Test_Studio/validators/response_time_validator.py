"""
validators/response_time_validator.py
========================================
Validates that the API responded within an acceptable time threshold.

Handles assertion types:
    - ValidationType.RESPONSE_TIME

Default threshold: 5 000 ms (5 seconds) — overridable per assertion.

Level: Generic Validation (Level 1)
"""

from typing import Any, Dict

from constants.validation_types import ValidationType
from interfaces.validator_interface import IValidator
from models.execution_result import AssertionResult
from models.test_case import Assertion
from validators.validation_utils import (
    evaluate_operator,
    make_error,
    make_fail,
    make_pass,
)
from utilities.logger import get_logger

logger = get_logger(__name__)

# Default maximum acceptable response time in milliseconds
DEFAULT_MAX_RESPONSE_TIME_MS: float = 5_000.0


class ResponseTimeValidator(IValidator):
    """
    Ensures the API response time is within the expected threshold.

    For explicit assertions:
        ``expected_value`` is the maximum acceptable response time in ms.
        ``operator`` defaults to ``"less_than_or_equal"`` when omitted.

    Generic Level-1 check:
        Uses ``DEFAULT_MAX_RESPONSE_TIME_MS`` unless overridden.
    """

    @property
    def validator_name(self) -> str:
        return "Response Time Validator"

    def supports(self, validation_type: str) -> bool:
        return validation_type == ValidationType.RESPONSE_TIME.value

    def validate(
        self,
        assertion: Assertion,
        response_data: Dict[str, Any],
    ) -> AssertionResult:
        """
        Evaluate a response-time assertion.

        Args:
            assertion:     The ``Assertion`` to evaluate.
            response_data: Standardised response dict.

        Returns:
            ``AssertionResult`` reflecting pass or fail.
        """
        try:
            actual_ms = response_data.get("response_time_ms")

            if actual_ms is None:
                return make_fail(
                    assertion,
                    actual=None,
                    reason="Response time not recorded (execution error).",
                )

            # Use the assertion's operator; default to less_than_or_equal
            operator = assertion.operator or "less_than_or_equal"
            passed, reason = evaluate_operator(
                actual=actual_ms,
                operator=operator,
                expected=assertion.expected_value,
            )
            logger.debug(
                "%s: actual=%.1fms  threshold=%s  %s",
                self.validator_name, actual_ms,
                assertion.expected_value, "PASS" if passed else "FAIL",
            )
            return make_pass(assertion, actual_ms, reason) if passed \
                else make_fail(assertion, actual_ms, reason)

        except Exception as exc:
            logger.error("%s: unexpected error: %s", self.validator_name, exc)
            return make_error(assertion, exc)

    def generic_check(
        self,
        response_data: Dict[str, Any],
        max_ms: float = DEFAULT_MAX_RESPONSE_TIME_MS,
    ) -> AssertionResult:
        """
        Perform a standalone response-time check without a pre-built Assertion.

        Args:
            response_data: Standardised response dict.
            max_ms:        Maximum acceptable response time in milliseconds.

        Returns:
            ``AssertionResult`` for the generic response-time check.
        """
        synthetic = Assertion(
            assertion_id="generic_response_time",
            validation_type=ValidationType.RESPONSE_TIME.value,
            operator="less_than_or_equal",
            target="response_time_ms",
            expected_value=max_ms,
            description=f"Generic: response time should be ≤ {max_ms} ms",
        )
        return self.validate(synthetic, response_data)
