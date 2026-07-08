"""
validators/status_code_validator.py
=====================================
Validates the HTTP status code of an executed response.

Handles assertion types:
    - ValidationType.STATUS_CODE   — primary target
    - ValidationType.RESPONSE_BODY when target == "status_code"  — fallback

Also performs a standalone generic check when the execution produced
an error result (no HTTP response received), producing an automatic FAIL.

Level: Generic Validation (Level 1 — always runs)
"""

from typing import Any, Dict, List

from constants.validation_types import ValidationType, TestStatus
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


class StatusCodeValidator(IValidator):
    """
    Evaluates assertions whose ``validation_type`` is ``"status_code"``.

    Also fires automatically for any execution result whose Phase 4 status
    is ``"error"`` (connection refused, timeout) — producing an automatic
    FAIL with a clear message rather than silently skipping validation.

    Strategy:
        1. If the result has no HTTP status (execution error) → FAIL.
        2. Use ``evaluate_operator()`` to compare actual vs expected code.
    """

    @property
    def validator_name(self) -> str:
        return "Status Code Validator"

    def supports(self, validation_type: str) -> bool:
        return validation_type in (
            ValidationType.STATUS_CODE.value,
            "status_code",  # defensive: plain string in older assertions
        )

    def validate(
        self,
        assertion: Assertion,
        response_data: Dict[str, Any],
    ) -> AssertionResult:
        """
        Evaluate a status-code assertion.

        Args:
            assertion:     The ``Assertion`` to evaluate.
            response_data: Standardised response dict from ``build_response_data()``.

        Returns:
            ``AssertionResult`` reflecting pass or fail.
        """
        try:
            actual_code = response_data.get("status_code")

            # Execution error — no HTTP response was received at all
            if actual_code is None:
                error_msg = response_data.get("error_message", "No response received")
                logger.debug(
                    "%s: no status code — execution error: %s",
                    self.validator_name, error_msg,
                )
                return make_fail(
                    assertion,
                    actual=None,
                    reason=f"No HTTP response received (execution error: {error_msg})",
                )

            passed, reason = evaluate_operator(
                actual=actual_code,
                operator=assertion.operator,
                expected=assertion.expected_value,
            )

            logger.debug(
                "%s: expected=%s  actual=%d  %s",
                self.validator_name,
                assertion.expected_value,
                actual_code,
                "PASS" if passed else "FAIL",
            )

            return make_pass(assertion, actual_code, reason) if passed \
                else make_fail(assertion, actual_code, reason)

        except Exception as exc:
            logger.error("%s: unexpected error: %s", self.validator_name, exc)
            return make_error(assertion, exc)

    # ------------------------------------------------------------------
    # Generic level-1 check (called directly by ValidationManager,
    # not through the assertion dispatch path)
    # ------------------------------------------------------------------

    def generic_check(
        self,
        response_data: Dict[str, Any],
        expected_code: int,
    ) -> AssertionResult:
        """
        Perform a standalone status-code check without a pre-built Assertion.

        Used by ``ValidationManager`` for Level-1 generic validation when
        a test case carries no explicit status-code assertion but the
        expected code is known from the generator.

        Args:
            response_data: Standardised response dict.
            expected_code: The expected HTTP status code.

        Returns:
            ``AssertionResult`` for the generic status-code check.
        """
        synthetic = Assertion(
            assertion_id="generic_status",
            validation_type=ValidationType.STATUS_CODE.value,
            operator="equals",
            target="status_code",
            expected_value=expected_code,
            description=f"Generic: status code should be {expected_code}",
        )
        return self.validate(synthetic, response_data)
