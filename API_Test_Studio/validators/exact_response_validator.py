"""
validators/exact_response_validator.py
========================================
Validates exact values within a response body.

Level: Exact Response Validation (Level 3) — runs when expected values
are explicitly declared in the assertion.

Handles assertion types:
    - ValidationType.RESPONSE_BODY  with a specific target field
    - ValidationType.JSON_PATH       with a dot-notation path

Exact validation checks:
    - Exact JSON field value match
    - Exact response status message
    - Exact response structure (all declared keys present)
    - Required fields present with correct values
    - Response shape matches an expected template dict

This validator is the strictest layer. It fires only when
``assertion.expected_value`` is a concrete value (not a schema or True).
"""

import json
from typing import Any, Dict, List, Optional, Tuple

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


class ExactResponseValidator(IValidator):
    """
    Validates that specific fields in the response body carry exact values.

    Use cases:
        1. Verify ``response.id`` equals a known value.
        2. Verify ``response.status`` equals ``"success"``.
        3. Verify a template dict is a structural subset of the body
           (all template keys exist with correct values).

    For ``RESPONSE_BODY`` assertions whose ``target`` is a dot-path:
        Extracts the field and applies the operator.

    For ``RESPONSE_BODY`` assertions whose ``expected_value`` is a dict
    (template matching):
        Verifies that every key in the template exists in the body with
        the same value (body may have additional keys — not strict).
    """

    @property
    def validator_name(self) -> str:
        return "Exact Response Validator"

    def supports(self, validation_type: str) -> bool:
        # Handles the same types as JSONValidator but fires only on exact
        # value assertions routed explicitly by ValidationManager
        return validation_type in (
            ValidationType.RESPONSE_BODY.value,
            ValidationType.JSON_PATH.value,
        )

    def validate(
        self,
        assertion: Assertion,
        response_data: Dict[str, Any],
    ) -> AssertionResult:
        """
        Evaluate an exact-value assertion.

        Args:
            assertion:     The ``Assertion`` to evaluate.
            response_data: Standardised response dict.

        Returns:
            ``AssertionResult`` reflecting pass or fail.
        """
        try:
            body = response_data.get("body")

            if body is None:
                return make_fail(
                    assertion, None,
                    "Response body is empty — exact validation cannot proceed.",
                )

            # Parse string body if needed
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except json.JSONDecodeError:
                    return make_fail(
                        assertion, body[:100],
                        "Response body is not parseable JSON.",
                    )

            expected = assertion.expected_value

            # Template dict matching — check all template keys exist with correct values
            if isinstance(expected, dict) and assertion.target in ("response_body", "body", ""):
                return self._template_match(assertion, body, expected)

            # Dot-path field extraction + operator comparison
            if assertion.target and assertion.target not in ("response_body", "body"):
                return self._field_check(assertion, body)

            # Whole-body exact comparison
            passed, reason = evaluate_operator(
                actual=body,
                operator=assertion.operator,
                expected=expected,
            )
            logger.debug(
                "%s: whole-body check  %s",
                self.validator_name, "PASS" if passed else "FAIL",
            )
            return make_pass(assertion, body, reason) if passed \
                else make_fail(assertion, body, reason)

        except Exception as exc:
            logger.error("%s: unexpected error: %s", self.validator_name, exc)
            return make_error(assertion, exc)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _field_check(
        self,
        assertion: Assertion,
        body: Any,
    ) -> AssertionResult:
        """Extract one field and compare it to the expected value."""
        value, found = extract_json_field(body, assertion.target)
        if not found:
            return make_fail(
                assertion, None,
                f"Field '{assertion.target}' not found in response body.",
            )
        passed, reason = evaluate_operator(
            actual=value,
            operator=assertion.operator,
            expected=assertion.expected_value,
        )
        logger.debug(
            "%s: field='%s'  actual=%r  expected=%r  %s",
            self.validator_name, assertion.target,
            value, assertion.expected_value,
            "PASS" if passed else "FAIL",
        )
        return make_pass(assertion, value, reason) if passed \
            else make_fail(assertion, value, reason)

    @staticmethod
    def _template_match(
        assertion: Assertion,
        body: Any,
        template: Dict[str, Any],
    ) -> AssertionResult:
        """
        Verify that every key in *template* exists in *body* with the same value.

        *body* may contain extra keys — this is a subset check, not strict equality.

        Args:
            assertion: Source assertion (for result construction).
            body:      Parsed response body.
            template:  Expected key-value pairs.

        Returns:
            ``AssertionResult``.
        """
        if not isinstance(body, dict):
            return make_fail(
                assertion, type(body).__name__,
                "Response body is not a JSON object — template matching requires a dict.",
            )

        mismatches: List[str] = []
        for key, expected_val in template.items():
            actual_val = body.get(key, "__MISSING__")
            if actual_val == "__MISSING__":
                mismatches.append(f"'{key}' is missing")
            elif actual_val != expected_val:
                mismatches.append(
                    f"'{key}': expected {expected_val!r}, got {actual_val!r}"
                )

        if mismatches:
            return make_fail(
                assertion, body,
                "Template mismatch — " + "; ".join(mismatches),
            )
        return make_pass(
            assertion, body,
            f"All {len(template)} template fields matched.",
        )
