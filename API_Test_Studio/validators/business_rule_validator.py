"""
validators/business_rule_validator.py
========================================
Applies configurable business rules to response data.

Level: Business Rule Validation — runs for ALL responses after generic checks.

Design
------
Rules are registered as callables (functions or lambdas) via
``BusinessRuleValidator.register_rule()``.  Each rule receives the
parsed response body and returns ``(passed: bool, message: str)``.

This makes the validator completely open to extension without modifying
any existing code — a clean Open/Closed implementation.

Built-in placeholder rules (active by default)
-----------------------------------------------
    1. response_not_error_object   — body must not be {"error": ...}
    2. id_field_not_negative       — if an "id" field exists it must be ≥ 0
    3. no_internal_stack_trace     — body must not contain stack-trace strings
    4. status_field_not_empty      — if a "status" field exists it must be non-empty

Adding a custom rule (Phase 6+)
--------------------------------
    from validators.business_rule_validator import BusinessRuleValidator

    def my_rule(body, response_data):
        if isinstance(body, dict) and body.get("role") == "admin":
            return False, "Admin role should never appear in public API responses"
        return True, "Role check passed"

    BusinessRuleValidator.register_rule("no_admin_role", my_rule)

All rules are then applied automatically by ValidationManager.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from constants.validation_types import ValidationType
from interfaces.validator_interface import IValidator
from models.execution_result import AssertionResult
from models.test_case import Assertion
from validators.validation_utils import make_fail, make_pass
from utilities.logger import get_logger

logger = get_logger(__name__)

# Type alias for a rule callable
RuleCallable = Callable[[Any, Dict[str, Any]], Tuple[bool, str]]


class BusinessRuleValidator(IValidator):
    """
    Applies a registry of named business rules to every response.

    Rules are registered globally via ``register_rule()`` and run in
    registration order.  Each rule that fails produces a separate
    ``AssertionResult`` with ``passed=False``.

    Usage::

        BusinessRuleValidator.register_rule("no_admin_role", my_rule_fn)
        validator = BusinessRuleValidator()
        results = validator.run_all_rules(response_data)
    """

    # Class-level rule registry — shared across all instances
    _rules: Dict[str, RuleCallable] = {}

    def __init__(self) -> None:
        # Register default placeholder rules on first instantiation
        if not BusinessRuleValidator._rules:
            BusinessRuleValidator._register_defaults()

    @property
    def validator_name(self) -> str:
        return "Business Rule Validator"

    def supports(self, validation_type: str) -> bool:
        # Business rules run on CUSTOM assertions
        return validation_type == ValidationType.CUSTOM.value

    def validate(
        self,
        assertion: Assertion,
        response_data: Dict[str, Any],
    ) -> AssertionResult:
        """
        Evaluate a single ``CUSTOM`` assertion using the rule named by
        ``assertion.target``.

        If no rule with that name is registered, the assertion passes
        with a warning (non-breaking unknown rules).

        Args:
            assertion:     The ``Assertion`` with ``target`` = rule name.
            response_data: Standardised response dict.

        Returns:
            ``AssertionResult``.
        """
        rule_name = assertion.target
        rule_fn = BusinessRuleValidator._rules.get(rule_name)

        if rule_fn is None:
            logger.warning(
                "%s: rule '%s' not registered — skipping assertion.",
                self.validator_name, rule_name,
            )
            return make_pass(
                assertion, "skipped",
                f"Rule '{rule_name}' not registered — treated as pass.",
            )

        try:
            body = response_data.get("body")
            passed, message = rule_fn(body, response_data)
            logger.debug(
                "%s: rule='%s'  %s  — %s",
                self.validator_name, rule_name,
                "PASS" if passed else "FAIL", message,
            )
            return make_pass(assertion, body, message) if passed \
                else make_fail(assertion, body, message)
        except Exception as exc:
            logger.error(
                "%s: rule '%s' raised an exception: %s",
                self.validator_name, rule_name, exc,
            )
            return make_fail(
                assertion, None,
                f"Rule '{rule_name}' raised an error: {type(exc).__name__}: {exc}",
            )

    # ------------------------------------------------------------------ #
    # Run all registered rules (called by ValidationManager for Level 1)
    # ------------------------------------------------------------------ #

    def run_all_rules(
        self,
        response_data: Dict[str, Any],
    ) -> List[AssertionResult]:
        """
        Run every registered business rule against *response_data*.

        Called directly by ``ValidationManager`` as a generic Level-1
        check regardless of whether the test case has explicit assertions.

        Args:
            response_data: Standardised response dict.

        Returns:
            List of ``AssertionResult`` — one per registered rule.
        """
        results: List[AssertionResult] = []
        body = response_data.get("body")

        for rule_name, rule_fn in BusinessRuleValidator._rules.items():
            synthetic = Assertion(
                assertion_id=f"biz_{rule_name}",
                validation_type=ValidationType.CUSTOM.value,
                operator="equals",
                target=rule_name,
                expected_value=True,
                description=f"Business rule: {rule_name}",
            )
            try:
                passed, message = rule_fn(body, response_data)
                if passed:
                    results.append(make_pass(synthetic, body, message))
                else:
                    results.append(make_fail(synthetic, body, message))
            except Exception as exc:
                logger.error(
                    "%s: rule '%s' raised: %s", self.validator_name, rule_name, exc,
                )
                results.append(
                    make_fail(
                        synthetic, None,
                        f"Rule '{rule_name}' error: {type(exc).__name__}: {exc}",
                    )
                )

        return results

    # ------------------------------------------------------------------ #
    # Rule registration
    # ------------------------------------------------------------------ #

    @classmethod
    def register_rule(cls, name: str, rule_fn: RuleCallable) -> None:
        """
        Register a named business rule.

        Args:
            name:    Unique rule identifier (e.g. ``"no_admin_role"``).
            rule_fn: Callable ``(body, response_data) → (bool, str)``.
                     Returns ``(True, "reason")`` on pass, ``(False, "reason")`` on fail.
        """
        cls._rules[name] = rule_fn
        logger.debug("BusinessRuleValidator: rule registered — '%s'.", name)

    @classmethod
    def unregister_rule(cls, name: str) -> None:
        """Remove a named rule from the registry (useful in tests)."""
        cls._rules.pop(name, None)

    @classmethod
    def clear_rules(cls) -> None:
        """Remove all registered rules (useful in tests)."""
        cls._rules.clear()

    @classmethod
    def registered_rule_names(cls) -> List[str]:
        """Return a list of all currently registered rule names."""
        return list(cls._rules.keys())

    # ------------------------------------------------------------------ #
    # Default placeholder rules
    # ------------------------------------------------------------------ #

    @classmethod
    def _register_defaults(cls) -> None:
        """
        Register the built-in placeholder business rules.

        These are generic sanity checks that apply to any REST API.
        They can be unregistered or overridden at runtime without touching
        this file.
        """
        cls.register_rule(
            "response_not_error_object",
            _rule_response_not_error_object,
        )
        cls.register_rule(
            "id_field_not_negative",
            _rule_id_field_not_negative,
        )
        cls.register_rule(
            "no_internal_stack_trace",
            _rule_no_internal_stack_trace,
        )
        cls.register_rule(
            "status_field_not_empty",
            _rule_status_field_not_empty,
        )
        logger.debug(
            "BusinessRuleValidator: %d default rule(s) registered.",
            len(cls._rules),
        )


# ===========================================================================
# Built-in rule functions (module-level for easy testability)
# ===========================================================================

def _rule_response_not_error_object(
    body: Any,
    response_data: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    FAIL if body is a JSON object containing only an ``error`` key
    (a common pattern for unhandled server errors leaking raw error dicts).
    """
    if isinstance(body, dict) and list(body.keys()) == ["error"]:
        return False, f"Response is a raw error object: {body.get('error')!r}"
    return True, "Response is not a raw error object."


def _rule_id_field_not_negative(
    body: Any,
    response_data: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    FAIL if the response body contains a top-level ``id`` field with a
    negative numeric value — a common sign of a generation or database error.
    """
    if not isinstance(body, dict):
        return True, "No top-level object to check id field."
    id_val = body.get("id")
    if id_val is None:
        return True, "No 'id' field present — rule N/A."
    try:
        if float(id_val) < 0:
            return False, f"'id' field is negative: {id_val}"
        return True, f"'id' field is non-negative: {id_val}"
    except (TypeError, ValueError):
        return True, f"'id' field is non-numeric ({id_val!r}) — rule N/A."


def _rule_no_internal_stack_trace(
    body: Any,
    response_data: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    FAIL if the response body (as a string) contains common stack-trace
    markers that indicate the server leaked an internal exception.
    """
    markers = ("Traceback (most recent call last)", "at java.lang",
               "System.Exception", "NullPointerException",
               "stack overflow", "unhandled exception")
    body_str = str(body).lower() if body is not None else ""
    for marker in markers:
        if marker.lower() in body_str:
            return False, f"Response contains a stack-trace marker: '{marker}'"
    return True, "No internal stack-trace markers detected."


def _rule_status_field_not_empty(
    body: Any,
    response_data: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    FAIL if the response body has a top-level ``status`` field that is
    an empty string or None — status fields should always carry a value.
    """
    if not isinstance(body, dict) or "status" not in body:
        return True, "No 'status' field — rule N/A."
    status_val = body.get("status")
    if status_val is None or status_val == "":
        return False, f"'status' field is empty or None: {status_val!r}"
    return True, f"'status' field is non-empty: {status_val!r}"
