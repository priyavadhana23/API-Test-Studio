"""
validators/validation_manager.py
===================================
Public orchestrator for the Phase 5 validation pipeline.

``ValidationManager`` is the ONLY class the rest of the framework calls.
No external code should directly instantiate individual validators.

Validation pipeline per (TestCase, ExecutionResult) pair
---------------------------------------------------------
    ExecutionResult
        │
        ├─ build_response_data()          → standardised response_data dict
        │
        ├─ Level 1 — Generic checks (always run, no assertion needed)
        │   ├─ StatusCodeValidator.validate()    — actual vs expected code
        │   ├─ ResponseTimeValidator.generic_check()
        │   ├─ JSONValidator.generic_not_empty_check()
        │   ├─ JSONValidator.generic_json_check()   (JSON responses only)
        │   └─ HeaderValidator.generic_content_type_check()
        │
        ├─ Level 1 — Assertion dispatch (routes each Assertion to its validator)
        │   Each Assertion.validation_type → matching IValidator.validate()
        │
        ├─ Level 2 — Schema validation
        │   SchemaValidator.validate()     (only if RESPONSE_SCHEMA assertion exists)
        │
        ├─ Level 3 — Exact response validation
        │   ExactResponseValidator.validate()  (only if RESPONSE_BODY/JSON_PATH assertion
        │                                       with a concrete expected value)
        │
        └─ Business rules — always run for JSON responses
            BusinessRuleValidator.run_all_rules()
        │
        └─ build_validation_result() → ValidationResult

The manager runs validators sequentially.  Parallel execution (Phase 6+)
requires only wrapping the inner loop with ThreadPoolExecutor — the public
interface does not change.

Extensibility
-------------
Register a new validator with one line:
    ValidationManager.register_validator(MyNewValidator())
It is then dispatched to for any assertion whose validation_type it supports.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from constants.validation_types import TestStatus, ValidationType
from models.execution_result import AssertionResult, ExecutionResult
from models.test_case import Assertion, TestCase
from validators.business_rule_validator import BusinessRuleValidator
from validators.exact_response_validator import ExactResponseValidator
from validators.header_validator import HeaderValidator
from validators.json_validator import JSONValidator
from validators.schema_validator import SchemaValidator
from validators.status_code_validator import StatusCodeValidator
from validators.response_time_validator import ResponseTimeValidator
from validators.validation_utils import (
    ValidationResult,
    build_response_data,
    build_validation_result,
)
from interfaces.validator_interface import IValidator
from utilities.logger import get_logger

logger = get_logger(__name__)

# Sentinel: how many sample results to display in the summary
_DEFAULT_SAMPLE_COUNT = 5

# Response-time threshold used for the generic Level-1 check (ms)
_DEFAULT_RT_THRESHOLD_MS = 5_000.0


class ValidationManager:
    """
    Orchestrates all validators and produces ``ValidationResult`` objects.

    Args:
        max_sample_display: Number of individual results shown in the summary.
        rt_threshold_ms:    Generic response-time threshold for Level-1 check.

    Usage::

        manager = ValidationManager()
        validation_results = manager.validate_all(
            test_cases, execution_results, spec_title="My API"
        )
    """

    def __init__(
        self,
        max_sample_display: int = _DEFAULT_SAMPLE_COUNT,
        rt_threshold_ms: float = _DEFAULT_RT_THRESHOLD_MS,
    ) -> None:
        self._max_samples   = max_sample_display
        self._rt_threshold  = rt_threshold_ms

        # Built-in validator instances
        self._status_validator  = StatusCodeValidator()
        self._header_validator  = HeaderValidator()
        self._rt_validator      = ResponseTimeValidator()
        self._json_validator    = JSONValidator()
        self._schema_validator  = SchemaValidator()
        self._exact_validator   = ExactResponseValidator()
        self._biz_validator     = BusinessRuleValidator()

        # Dispatch table: validation_type → IValidator
        # Checked in order; first match wins for assertion dispatch.
        self._dispatch: List[IValidator] = [
            self._status_validator,
            self._header_validator,
            self._rt_validator,
            self._json_validator,
            self._schema_validator,
            self._exact_validator,
            self._biz_validator,
        ]

        logger.info(
            "ValidationManager initialised with %d validators.",
            len(self._dispatch),
        )

    # ------------------------------------------------------------------ #
    # Registration (extension point)
    # ------------------------------------------------------------------ #

    def register_validator(self, validator: IValidator) -> None:
        """
        Append a custom validator to the dispatch table.

        The new validator's ``supports()`` method is called for every
        assertion's ``validation_type`` — no other code changes required.

        Args:
            validator: Any object implementing ``IValidator``.

        Example::

            class XMLValidator(IValidator):
                def supports(self, vt): return vt == "xml_body"
                def validate(self, assertion, response_data): ...

            manager = ValidationManager()
            manager.register_validator(XMLValidator())
        """
        if not isinstance(validator, IValidator):
            raise TypeError(
                f"Expected IValidator, got {type(validator).__name__}."
            )
        self._dispatch.append(validator)
        logger.info(
            "ValidationManager: registered additional validator '%s'.",
            validator.validator_name,
        )

    # ------------------------------------------------------------------ #
    # Public API — batch validation
    # ------------------------------------------------------------------ #

    def validate_all(
        self,
        test_cases: List[TestCase],
        execution_results: List[ExecutionResult],
        spec_title: str = "Unknown API",
    ) -> List[ValidationResult]:
        """
        Validate every execution result and return a list of ValidationResults.

        *test_cases* and *execution_results* must be parallel lists (same
        index means same test case).

        Args:
            test_cases:        The ``TestCase`` objects from Phase 3.
            execution_results: The ``ExecutionResult`` objects from Phase 4.
            spec_title:        API name used in the summary log.

        Returns:
            List of ``ValidationResult`` — one per (TestCase, ExecutionResult) pair.
        """
        if not test_cases or not execution_results:
            logger.warning("ValidationManager.validate_all() called with empty input.")
            return []

        if len(test_cases) != len(execution_results):
            logger.error(
                "test_cases (%d) and execution_results (%d) lengths differ — "
                "truncating to shortest.",
                len(test_cases), len(execution_results),
            )

        logger.info(
            "Validation started for '%s' (%d test case(s)).",
            spec_title, len(test_cases),
        )

        wall_start = time.monotonic()
        results: List[ValidationResult] = []

        for tc, er in zip(test_cases, execution_results):
            vr = self.validate_one(tc, er)
            results.append(vr)

        wall_elapsed = time.monotonic() - wall_start
        self._print_summary(spec_title, results, wall_elapsed)
        return results

    def validate_one(
        self,
        test_case: TestCase,
        execution_result: ExecutionResult,
    ) -> ValidationResult:
        """
        Run the full validation pipeline for one (TestCase, ExecutionResult) pair.

        Args:
            test_case:        The test case that was executed.
            execution_result: The execution result to validate.

        Returns:
            A ``ValidationResult`` — never raises.
        """
        t_start = time.monotonic()
        logger.debug(
            "Validating: %s  (HTTP %s)",
            test_case.name, execution_result.http_status_code,
        )

        all_assertion_results: List[AssertionResult] = []
        passed_validators: List[str] = []
        failed_validators: List[str] = []

        # Build the standardised response dict once — shared by all validators
        response_data = build_response_data(execution_result)

        # ── LEVEL 1a: Generic checks ────────────────────────────────────
        # These run unconditionally regardless of test case assertions.
        # They verify universal API quality attributes.
        self._run_generic_checks(
            test_case, execution_result, response_data,
            all_assertion_results, passed_validators, failed_validators,
        )

        # ── LEVEL 1b: Assertion dispatch ────────────────────────────────
        # Route each Assertion to the first validator that supports its type.
        for assertion in test_case.assertions:
            ar = self._dispatch_assertion(assertion, response_data)
            if ar is not None:
                all_assertion_results.append(ar)

        # ── LEVEL 2: Schema validation ──────────────────────────────────
        # Fires for any RESPONSE_SCHEMA assertion.
        schema_assertions = [
            a for a in test_case.assertions
            if a.validation_type == ValidationType.RESPONSE_SCHEMA.value
        ]
        for sa in schema_assertions:
            ar = self._schema_validator.validate(sa, response_data)
            self._record(ar, "Schema Validator", passed_validators, failed_validators)
            all_assertion_results.append(ar)

        # ── LEVEL 3: Exact response validation ──────────────────────────
        # Fires only for RESPONSE_BODY / JSON_PATH assertions with a
        # concrete (non-sentinel) expected value.
        exact_assertions = [
            a for a in test_case.assertions
            if a.validation_type in (
                ValidationType.RESPONSE_BODY.value,
                ValidationType.JSON_PATH.value,
            )
            and a.expected_value is not True   # True is a Phase 3 sentinel
        ]
        if exact_assertions:
            for ea in exact_assertions:
                ar = self._exact_validator.validate(ea, response_data)
                self._record(
                    ar, "Exact Response Validator",
                    passed_validators, failed_validators,
                )
                all_assertion_results.append(ar)
        else:
            logger.debug(
                "Exact Response Validator: skipped for '%s' (no example assertions).",
                test_case.name,
            )

        # ── Business rules ───────────────────────────────────────────────
        # Always run for responses that have a body (skip for errors/empty).
        if response_data.get("body") is not None:
            biz_results = self._biz_validator.run_all_rules(response_data)
            for br in biz_results:
                self._record(
                    br, "Business Rule Validator",
                    passed_validators, failed_validators,
                )
                all_assertion_results.append(br)

        # ── Assemble final ValidationResult ─────────────────────────────
        elapsed_ms = (time.monotonic() - t_start) * 1000.0
        vr = build_validation_result(
            test_case=test_case,
            execution_result=execution_result,
            assertion_results=all_assertion_results,
            passed_validators=list(dict.fromkeys(passed_validators)),   # dedupe, order-preserving
            failed_validators=list(dict.fromkeys(failed_validators)),
            validation_time_ms=elapsed_ms,
        )

        _status_label = vr.overall_status.upper()
        logger.debug(
            "Validated '%s' → %s  (%d/%d assertions passed)  %.1fms",
            test_case.name, _status_label,
            vr.passed_assertion_count, vr.total_assertions, elapsed_ms,
        )
        return vr

    # ------------------------------------------------------------------ #
    # Generic Level-1 checks
    # ------------------------------------------------------------------ #

    def _run_generic_checks(
        self,
        test_case: TestCase,
        execution_result: ExecutionResult,
        response_data: Dict[str, Any],
        results: List[AssertionResult],
        passed: List[str],
        failed: List[str],
    ) -> None:
        """
        Run all generic Level-1 checks that apply to every response.

        These checks do not require explicit assertions on the TestCase —
        they represent universal API quality standards.
        """
        # Execution error — skip all generic checks except status-code record
        if execution_result.status == TestStatus.ERROR.value:
            logger.debug(
                "Generic checks skipped for '%s' — execution error.",
                test_case.name,
            )
            return

        # 1. Response time
        rt_result = self._rt_validator.generic_check(
            response_data, self._rt_threshold
        )
        self._record(rt_result, "Response Time Validator", passed, failed)
        results.append(rt_result)

        # 2. Not empty (only for non-204 responses)
        status_code = response_data.get("status_code") or 0
        if status_code != 204:
            ne_result = self._json_validator.generic_not_empty_check(response_data)
            self._record(ne_result, "JSON Validator", passed, failed)
            results.append(ne_result)

        # 3. Valid JSON (only for JSON content types)
        ct = (response_data.get("content_type") or "").lower()
        if "json" in ct:
            json_result = self._json_validator.generic_json_check(response_data)
            self._record(json_result, "JSON Validator", passed, failed)
            results.append(json_result)

            # 4. Content-Type contains application/json
            ct_result = self._header_validator.generic_content_type_check(
                response_data, "application/json"
            )
            self._record(ct_result, "Header Validator", passed, failed)
            results.append(ct_result)

    # ------------------------------------------------------------------ #
    # Assertion dispatch
    # ------------------------------------------------------------------ #

    def _dispatch_assertion(
        self,
        assertion: Assertion,
        response_data: Dict[str, Any],
    ) -> Optional[AssertionResult]:
        """
        Route *assertion* to the first registered validator that supports it.

        Schema and exact-response assertions are handled in dedicated phases
        (Level 2 and Level 3) — skip them here to avoid double-evaluation.

        Args:
            assertion:     The ``Assertion`` to route.
            response_data: Standardised response dict.

        Returns:
            ``AssertionResult`` or ``None`` if no validator claimed the assertion.
        """
        # Already handled in Level 2 / Level 3
        if assertion.validation_type in (
            ValidationType.RESPONSE_SCHEMA.value,
            ValidationType.RESPONSE_BODY.value,
            ValidationType.JSON_PATH.value,
        ):
            return None

        for validator in self._dispatch:
            if validator.supports(assertion.validation_type):
                return validator.validate(assertion, response_data)

        logger.debug(
            "No validator found for validation_type='%s' — skipping assertion '%s'.",
            assertion.validation_type, assertion.assertion_id,
        )
        return None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _record(
        ar: AssertionResult,
        validator_name: str,
        passed: List[str],
        failed: List[str],
    ) -> None:
        """Record a validator name in the appropriate bucket."""
        if ar.passed:
            passed.append(validator_name)
        else:
            failed.append(validator_name)

    # ------------------------------------------------------------------ #
    # Summary printer
    # ------------------------------------------------------------------ #

    def _print_summary(
        self,
        spec_title: str,
        results: List[ValidationResult],
        elapsed_sec: float,
    ) -> None:
        """Emit a structured validation summary through the logger."""
        total   = len(results)
        passed  = sum(1 for r in results if r.overall_status == TestStatus.PASSED.value)
        failed  = sum(1 for r in results if r.overall_status == TestStatus.FAILED.value)
        errors  = sum(1 for r in results if r.overall_status == TestStatus.ERROR.value)
        skipped = total - passed - failed - errors
        rate    = (passed / total * 100) if total else 0.0

        # Per-validator statistics
        validator_names = [
            "Status Code Validator",
            "Response Time Validator",
            "JSON Validator",
            "Header Validator",
            "Schema Validator",
            "Business Rule Validator",
            "Exact Response Validator",
        ]
        vstat: Dict[str, int] = {n: 0 for n in validator_names}
        for vr in results:
            for vn in vr.passed_validators:
                if vn in vstat:
                    vstat[vn] += 1

        # Avg validation time
        times = [r.validation_time_ms for r in results if r.validation_time_ms]
        avg_ms = sum(times) / len(times) if times else 0.0

        wide = "=" * 52
        sep  = "─" * 52

        logger.info(wide)
        logger.info("  VALIDATION SUMMARY")
        logger.info(wide)
        logger.info("  API Name    : %s", spec_title)
        logger.info("  Executed    : %d", total)
        logger.info("  Passed      : %d", passed)
        logger.info("  Failed      : %d", failed)
        logger.info("  Errors      : %d", errors)
        logger.info("  Skipped     : %d", skipped)
        logger.info("  Pass Rate   : %.1f%%", rate)
        logger.info("  Total Time  : %.1f s", elapsed_sec)
        logger.info(sep)
        logger.info("  VALIDATOR STATISTICS")
        logger.info(sep)

        exact_count = sum(
            1 for vr in results
            if "Exact Response Validator" in vr.passed_validators
               or "Exact Response Validator" in vr.failed_validators
        )

        for vname in validator_names:
            if vname == "Exact Response Validator":
                if exact_count == 0:
                    logger.info("  %-32s  Skipped (No Examples)", vname)
                else:
                    logger.info("  %-32s  %d Passed", vname, vstat[vname])
            else:
                logger.info("  %-32s  %d Passed", vname, vstat[vname])

        logger.info(sep)
        logger.info("  Avg Validation Time : %.2f ms", avg_ms)
        logger.info(sep)

        # Sample results
        logger.info("  SAMPLE RESULTS (first %d)", self._max_samples)
        logger.info(sep)
        shown = 0
        for vr in results:
            if shown >= self._max_samples:
                break
            if vr.overall_status not in (
                TestStatus.PASSED.value, TestStatus.FAILED.value,
            ):
                continue

            # Derive method + path from URL or test name
            url_label = (vr.request_url or vr.test_name)[:44]
            overall_label = "PASS" if vr.passed else "FAIL"

            # Collect per-category outcomes for this result
            pv = set(vr.passed_validators)
            fv = set(vr.failed_validators)

            def _badge(name: str) -> str:
                short = name.replace(" Validator", "").replace(" ", " ")
                if name in fv:
                    return f"    {short:<22} FAIL"
                if name in pv:
                    return f"    {short:<22} PASS"
                return f"    {short:<22} SKIP"

            logger.info(sep)
            logger.info("  %s", url_label)
            logger.info("  HTTP %-3s", vr.http_status_code or "—")
            for vname in validator_names:
                logger.info(_badge(vname))
            logger.info("  Overall                    %s", overall_label)
            if vr.failure_messages:
                for msg in vr.failure_messages[:2]:
                    logger.info("  Reason: %s", msg[:80])
            shown += 1

        logger.info(wide)
        logger.info("  END OF VALIDATION SUMMARY — %s", spec_title)
        logger.info(wide)
