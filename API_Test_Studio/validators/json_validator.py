"""
validators/json_validator.py
==============================
Validates JSON structure and field-level assertions in the response body.

Handles assertion types:
    - ValidationType.NOT_EMPTY     — body must not be empty / null
    - ValidationType.RESPONSE_BODY — field-level check using dot-notation target
    - ValidationType.JSON_PATH     — same as RESPONSE_BODY (dot-notation path)

Level 1 generic checks (always run for JSON responses):
    - Body is not None / empty
    - Body is valid JSON (dict or list) — not a raw string

Level: Generic Validation (Level 1) + assertion-driven field checks
"""

import json
from typing import Any, Dict

from constants.validation_types import ValidationType
from interfaces.validator_interface import IValidator
from models.execution_result import AssertionResult
from models.test_case import Assertion
from validators.validation_utils import (
    evaluate_operator,
    extract_json_field,
    make_error,
    make_fail,
    make_pass,
)
from utilities.logger import get_logger

logger = get_logger(__name__)


class JSONValidator(IValidator):
    """
    Validates JSON response body structure and individual field values.

    For ``NOT_EMPTY`` assertions:
        Fails if the body is ``None``, ``""``, ``[]``, or ``{}``.

    For ``RESPONSE_BODY`` / ``JSON_PATH`` assertions:
        ``target`` is a dot-notation path (e.g. ``"user.id"``).
        The extracted value is compared to ``expected_value`` using the operator.

    Generic Level-1 checks (used by ValidationManager independently):
        - ``generic_not_empty_check()``: body must not be None/empty
        - ``generic_json_check()``: body must be parseable JSON
    """

    @property
    def validator_name(self) -> str:
        return "JSON Validator"

    def supports(self, validation_type: str) -> bool:
        return validation_type in (
            ValidationType.NOT_EMPTY.value,
            ValidationType.RESPONSE_BODY.value,
            ValidationType.JSON_PATH.value,
        )

    def validate(
        self,
        assertion: Assertion,
        response_data: Dict[str, Any],
    ) -> AssertionResult:
        """
        Evaluate a JSON-related assertion.

        Args:
            assertion:     The ``Assertion`` to evaluate.
            response_data: Standardised response dict.

        Returns:
            ``AssertionResult`` reflecting pass or fail.
        """
        try:
            body = response_data.get("body")

            # ── NOT_EMPTY ──────────────────────────────────────────────
            if assertion.validation_type == ValidationType.NOT_EMPTY.value:
                return self._check_not_empty(assertion, body)

            # ── RESPONSE_BODY / JSON_PATH — field extraction ───────────
            if body is None:
                return make_fail(
                    assertion,
                    actual=None,
                    reason="Response body is empty — cannot extract field.",
                )

            if not isinstance(body, (dict, list)):
                # Try to parse if body is a JSON string
                if isinstance(body, str):
                    try:
                        body = json.loads(body)
                    except json.JSONDecodeError:
                        return make_fail(
                            assertion,
                            actual=body,
                            reason="Response body is not valid JSON — cannot extract field.",
                        )
                else:
                    return make_fail(
                        assertion,
                        actual=body,
                        reason=f"Response body type '{type(body).__name__}' "
                               "is not a JSON object/array.",
                    )

            # target == "response_body" means check the whole body
            if assertion.target in ("response_body", "body", ""):
                passed, reason = evaluate_operator(
                    actual=body,
                    operator=assertion.operator,
                    expected=assertion.expected_value,
                )
                return make_pass(assertion, body, reason) if passed \
                    else make_fail(assertion, body, reason)

            # Dot-notation field extraction
            value, found = extract_json_field(body, assertion.target)
            if not found:
                return make_fail(
                    assertion,
                    actual=None,
                    reason=f"Field '{assertion.target}' not found in response body.",
                )

            passed, reason = evaluate_operator(
                actual=value,
                operator=assertion.operator,
                expected=assertion.expected_value,
            )
            logger.debug(
                "%s: field='%s'  actual=%r  %s",
                self.validator_name, assertion.target, value,
                "PASS" if passed else "FAIL",
            )
            return make_pass(assertion, value, reason) if passed \
                else make_fail(assertion, value, reason)

        except Exception as exc:
            logger.error("%s: unexpected error: %s", self.validator_name, exc)
            return make_error(assertion, exc)

    # ------------------------------------------------------------------
    # Generic level-1 checks
    # ------------------------------------------------------------------

    def generic_not_empty_check(
        self, response_data: Dict[str, Any]
    ) -> AssertionResult:
        """Check that the response body is not None/empty."""
        synthetic = Assertion(
            assertion_id="generic_not_empty",
            validation_type=ValidationType.NOT_EMPTY.value,
            operator="is_not_null",
            target="response_body",
            expected_value=True,
            description="Generic: response body must not be empty",
        )
        return self._check_not_empty(synthetic, response_data.get("body"))

    def generic_json_check(
        self, response_data: Dict[str, Any]
    ) -> AssertionResult:
        """Check that the response body is parseable JSON (dict or list)."""
        body = response_data.get("body")
        synthetic = Assertion(
            assertion_id="generic_valid_json",
            validation_type=ValidationType.RESPONSE_BODY.value,
            operator="is_not_null",
            target="response_body",
            expected_value=True,
            description="Generic: response body must be valid JSON",
        )

        if body is None:
            return make_fail(synthetic, None, "Response body is None.")

        if isinstance(body, (dict, list)):
            return make_pass(synthetic, type(body).__name__,
                             f"Response body is valid JSON ({type(body).__name__}).")

        if isinstance(body, str):
            try:
                json.loads(body)
                return make_pass(synthetic, "string(JSON)",
                                 "Response body is a valid JSON string.")
            except json.JSONDecodeError as exc:
                return make_fail(synthetic, body[:100],
                                 f"Response body is not valid JSON: {exc}")

        return make_fail(synthetic, type(body).__name__,
                         f"Response body type '{type(body).__name__}' is not JSON.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_not_empty(assertion: Assertion, body: Any) -> AssertionResult:
        """Evaluate a NOT_EMPTY assertion against *body*."""
        if body is None:
            return make_fail(assertion, None, "Response body is None.")
        if body == "" or body == [] or body == {}:
            return make_fail(
                assertion, body,
                f"Response body is empty ({type(body).__name__}).",
            )
        return make_pass(assertion, type(body).__name__,
                         "Response body is not empty.")
