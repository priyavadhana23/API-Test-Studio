"""
validators/header_validator.py
================================
Validates response headers.

Handles assertion types:
    - ValidationType.RESPONSE_HEADER  — explicit header assertion
    - ValidationType.CONTENT_TYPE     — Content-Type specific check

Level 1 generic checks (always run regardless of assertions):
    - Content-Type present for non-empty responses
    - Content-Type contains expected MIME type when declared

Level: Generic Validation (Level 1) + assertion-driven
"""

from typing import Any, Dict, Optional

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


class HeaderValidator(IValidator):
    """
    Evaluates header assertions and performs generic Content-Type checks.

    For ``ValidationType.RESPONSE_HEADER`` assertions:
        ``target`` is the header name (case-insensitive).
        The header value is extracted and compared using the assertion operator.

    For ``ValidationType.CONTENT_TYPE`` assertions:
        ``target`` is ignored; the Content-Type header is always inspected.
        ``expected_value`` is the MIME type string to check for (uses CONTAINS).
    """

    @property
    def validator_name(self) -> str:
        return "Header Validator"

    def supports(self, validation_type: str) -> bool:
        return validation_type in (
            ValidationType.RESPONSE_HEADER.value,
            ValidationType.CONTENT_TYPE.value,
        )

    def validate(
        self,
        assertion: Assertion,
        response_data: Dict[str, Any],
    ) -> AssertionResult:
        """
        Evaluate a header assertion.

        Args:
            assertion:     The ``Assertion`` to evaluate.
            response_data: Standardised response dict.

        Returns:
            ``AssertionResult`` reflecting pass or fail.
        """
        try:
            headers: Dict[str, str] = response_data.get("headers", {})

            if assertion.validation_type == ValidationType.CONTENT_TYPE.value:
                return self._check_content_type(assertion, headers)

            # RESPONSE_HEADER: target is the header name
            header_name = assertion.target.lower()
            actual_value = headers.get(header_name)

            if actual_value is None:
                return make_fail(
                    assertion,
                    actual=None,
                    reason=f"Response header '{assertion.target}' is absent.",
                )

            passed, reason = evaluate_operator(
                actual=actual_value,
                operator=assertion.operator,
                expected=assertion.expected_value,
            )
            logger.debug(
                "%s: header='%s'  actual='%s'  %s",
                self.validator_name, assertion.target, actual_value,
                "PASS" if passed else "FAIL",
            )
            return make_pass(assertion, actual_value, reason) if passed \
                else make_fail(assertion, actual_value, reason)

        except Exception as exc:
            logger.error("%s: unexpected error: %s", self.validator_name, exc)
            return make_error(assertion, exc)

    # ------------------------------------------------------------------
    # Generic level-1 Content-Type check
    # ------------------------------------------------------------------

    def generic_content_type_check(
        self,
        response_data: Dict[str, Any],
        expected_mime: Optional[str] = "application/json",
    ) -> AssertionResult:
        """
        Perform a standalone Content-Type check without a pre-built Assertion.

        Args:
            response_data: Standardised response dict.
            expected_mime: Expected MIME type substring (default ``application/json``).

        Returns:
            ``AssertionResult`` for the generic Content-Type check.
        """
        synthetic = Assertion(
            assertion_id="generic_content_type",
            validation_type=ValidationType.CONTENT_TYPE.value,
            operator="contains",
            target="Content-Type",
            expected_value=expected_mime or "application/json",
            description=f"Generic: Content-Type should contain '{expected_mime}'",
        )
        headers = response_data.get("headers", {})
        return self._check_content_type(synthetic, headers)

    def _check_content_type(
        self,
        assertion: Assertion,
        headers: Dict[str, str],
    ) -> AssertionResult:
        """
        Internal Content-Type evaluation.

        Args:
            assertion: The assertion (may be synthetic for generic checks).
            headers:   Lower-cased response header dict.

        Returns:
            ``AssertionResult``.
        """
        content_type = headers.get("content-type", "")
        if not content_type:
            return make_fail(
                assertion,
                actual=None,
                reason="Content-Type header is absent from the response.",
            )

        passed, reason = evaluate_operator(
            actual=content_type,
            operator=assertion.operator,
            expected=assertion.expected_value,
        )
        logger.debug(
            "%s: Content-Type='%s'  %s",
            self.validator_name, content_type, "PASS" if passed else "FAIL",
        )
        return make_pass(assertion, content_type, reason) if passed \
            else make_fail(assertion, content_type, reason)
