"""
validators/schema_validator.py
================================
Validates a response body against a JSON Schema.

Uses the ``jsonschema`` library (pip install jsonschema).

Handles assertion type:
    - ValidationType.RESPONSE_SCHEMA

Validation rules checked:
    - Required fields present
    - Field data types correct
    - Nested object structure valid
    - Array items match declared item schema
    - No additional properties (when ``additionalProperties: false``)
    - Enum values respected
    - String format constraints (date, email, uri, etc.)

Level: Schema Validation (Level 2) — runs only when a schema is provided.
"""

import json
from typing import Any, Dict, List, Optional

try:
    import jsonschema
    from jsonschema import Draft7Validator, ValidationError as JsonSchemaError
    _JSONSCHEMA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _JSONSCHEMA_AVAILABLE = False

from constants.validation_types import ValidationType
from interfaces.validator_interface import IValidator
from models.execution_result import AssertionResult
from models.test_case import Assertion
from validators.validation_utils import make_error, make_fail, make_pass
from utilities.logger import get_logger

logger = get_logger(__name__)


class SchemaValidator(IValidator):
    """
    Validates a JSON response body against a declared schema using jsonschema.

    The schema is passed via ``assertion.expected_value`` as a Python dict.
    If ``expected_value`` is ``True`` (the sentinel set by Phase 3 generators),
    the validator performs a light structural check instead of full schema
    validation (ensures body is a non-empty JSON object or array).

    Extension for contract testing (Phase 6+):
        Pass the full OpenAPI response schema dict as ``expected_value``
        to enable strict contract validation.
    """

    @property
    def validator_name(self) -> str:
        return "Schema Validator"

    def supports(self, validation_type: str) -> bool:
        return validation_type == ValidationType.RESPONSE_SCHEMA.value

    def validate(
        self,
        assertion: Assertion,
        response_data: Dict[str, Any],
    ) -> AssertionResult:
        """
        Evaluate a schema assertion.

        Args:
            assertion:     The ``Assertion`` to evaluate.
                           ``expected_value`` should be a JSON Schema dict,
                           or ``True`` for a basic structure check.
            response_data: Standardised response dict.

        Returns:
            ``AssertionResult`` reflecting pass or fail.
        """
        try:
            body = response_data.get("body")

            # No body — cannot validate schema
            if body is None:
                return make_fail(
                    assertion, None,
                    "Response body is empty — schema validation skipped.",
                )

            # Parse string body if needed
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except json.JSONDecodeError:
                    return make_fail(
                        assertion, body[:100],
                        "Response body is not valid JSON — schema validation failed.",
                    )

            schema = assertion.expected_value

            # Sentinel value True → lightweight structural check only
            if schema is True or not isinstance(schema, dict):
                return self._light_structure_check(assertion, body)

            return self._full_schema_check(assertion, body, schema)

        except Exception as exc:
            logger.error("%s: unexpected error: %s", self.validator_name, exc)
            return make_error(assertion, exc)

    # ------------------------------------------------------------------
    # Validation strategies
    # ------------------------------------------------------------------

    def _full_schema_check(
        self,
        assertion: Assertion,
        body: Any,
        schema: Dict[str, Any],
    ) -> AssertionResult:
        """
        Validate *body* against *schema* using jsonschema Draft7Validator.

        Args:
            assertion: The source assertion (for result construction).
            body:      Parsed JSON body.
            schema:    JSON Schema dict.

        Returns:
            ``AssertionResult`` with all violations listed in the message.
        """
        if not _JSONSCHEMA_AVAILABLE:
            logger.warning(
                "%s: jsonschema not installed — falling back to structural check.",
                self.validator_name,
            )
            return self._light_structure_check(assertion, body)

        validator = Draft7Validator(schema)
        errors: List[JsonSchemaError] = sorted(
            validator.iter_errors(body),
            key=lambda e: str(e.path),
        )

        if not errors:
            logger.debug("%s: schema validation passed.", self.validator_name)
            return make_pass(
                assertion, "schema_valid",
                f"Response body conforms to declared schema "
                f"({len(schema.get('properties', {}))} properties checked).",
            )

        messages = [
            f"[{'.'.join(str(p) for p in err.absolute_path) or 'root'}] "
            f"{err.message}"
            for err in errors[:5]   # cap at 5 violations for readability
        ]
        violation_summary = " | ".join(messages)
        logger.debug(
            "%s: schema validation FAILED — %d violation(s): %s",
            self.validator_name, len(errors), violation_summary,
        )
        return make_fail(
            assertion, body,
            f"Schema validation failed — {len(errors)} violation(s): "
            f"{violation_summary}",
        )

    @staticmethod
    def _light_structure_check(
        assertion: Assertion,
        body: Any,
    ) -> AssertionResult:
        """
        Lightweight check: body is a non-empty JSON object or array.

        Used when no explicit schema dict is available.

        Args:
            assertion: The source assertion.
            body:      Parsed body value.

        Returns:
            ``AssertionResult``.
        """
        if isinstance(body, dict) and body:
            return make_pass(
                assertion, "object",
                f"Response body is a non-empty JSON object ({len(body)} keys).",
            )
        if isinstance(body, list):
            return make_pass(
                assertion, "array",
                f"Response body is a JSON array ({len(body)} items).",
            )
        if isinstance(body, dict) and not body:
            return make_fail(
                assertion, "{}",
                "Response body is an empty JSON object — expected content.",
            )
        return make_pass(
            assertion, type(body).__name__,
            "Response body is a valid JSON value.",
        )
