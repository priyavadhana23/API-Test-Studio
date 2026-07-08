"""
testcase_generator/boundary_generator.py
==========================================
Generates boundary-value test cases for numeric, string, enum, array,
and object parameters.

Boundary analysis covers the edges of every allowed value range — the
values most likely to reveal off-by-one errors, buffer overflows, and
type-coercion bugs.

Categories produced
-------------------
Numeric parameters:
    zero, negative, large-positive, min-1 (if schema.minimum), max+1
    (if schema.maximum)

String parameters:
    empty, single-char, min-length-1 (minLength-1), max-length+1,
    very-long (1 000 chars), unicode, emoji, special-characters,
    whitespace-only, null-byte

Enum parameters:
    every valid enum value  +  one invalid value

Array parameters:
    empty array, single-item array, large array (100 items)

Object parameters / request-body objects:
    empty object, missing required nested field

All test cases are set to ``status = "pending"`` and marked as
``is_auto_generated = True``.
"""

from typing import Any, Dict, List, Optional

from constants.app_constants import DataTypes, ParameterLocation
from constants.validation_types import Severity
from interfaces.generator_interface import ITestCaseGenerator
from models.endpoint import Endpoint, Parameter
from models.test_case import TestCase
from testcase_generator.generator_utils import (
    TestCategory,
    expected_error_code,
    expected_success_code,
    valid_body_for,
    valid_path_params_for,
    valid_query_params_for,
    valid_value_for,
)
from testcase_generator.testcase_factory import TestCaseFactory
from utilities.logger import get_logger

logger = get_logger(__name__)

# Reusable boundary string payloads
_VERY_LONG_STRING = "A" * 1000
_UNICODE_STRING   = "Ünïcödé_tëst_vàlüé_日本語_한국어_العربية"
_EMOJI_STRING     = "😀🔥💯🎉🚀"
_SPECIAL_CHARS    = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
_WHITESPACE_ONLY  = "   \t\n  "
_NULL_BYTE        = "value\x00null"


class BoundaryGenerator(ITestCaseGenerator):
    """
    Generates boundary-value test cases for all parameters in an endpoint.

    Covers numeric, string, enum, array, and object boundary conditions.
    Each generated case is self-contained — it modifies exactly one
    parameter to its boundary value while keeping all others valid.
    """

    @property
    def generator_name(self) -> str:
        return "Boundary Generator"

    def supports(self, endpoint: Endpoint) -> bool:
        """
        Return ``True`` for endpoints that have at least one parameter
        or a request body — otherwise there is nothing to bound-test.
        """
        return bool(endpoint.parameters or endpoint.request_body)

    def generate(
        self,
        endpoint: Endpoint,
        spec_id: str,
        environment_config: Any,
    ) -> List[TestCase]:
        """
        Generate boundary-value test cases for *endpoint*.

        One case is generated per boundary value per parameter.
        Each modifies a single parameter; all others are set to valid values.

        Args:
            endpoint:           The endpoint to test.
            spec_id:            Parent ApiSpec ID.
            environment_config: Active environment config.

        Returns:
            List of boundary ``TestCase`` objects.
        """
        cases: List[TestCase] = []
        path_params  = valid_path_params_for(endpoint)
        query_params = valid_query_params_for(endpoint)
        body         = valid_body_for(endpoint)
        err_code     = expected_error_code(endpoint, prefer=400)
        ok_code      = expected_success_code(endpoint)

        for param in endpoint.parameters:
            dtype = param.data_type.lower()
            schema = param.schema or {}

            if dtype in (DataTypes.INTEGER, DataTypes.NUMBER):
                cases.extend(self._numeric_cases(
                    endpoint, spec_id, param, schema,
                    path_params, query_params, body, ok_code, err_code,
                ))
            elif dtype == DataTypes.STRING:
                cases.extend(self._string_cases(
                    endpoint, spec_id, param, schema,
                    path_params, query_params, body, err_code,
                ))
            elif dtype == DataTypes.ARRAY:
                cases.extend(self._array_cases(
                    endpoint, spec_id, param,
                    path_params, query_params, body, ok_code, err_code,
                ))

            if param.enum_values:
                cases.extend(self._enum_cases(
                    endpoint, spec_id, param,
                    path_params, query_params, body, ok_code, err_code,
                ))

        # Object / request-body boundaries
        if endpoint.request_body:
            cases.extend(self._body_object_cases(
                endpoint, spec_id, path_params, query_params, body, err_code,
            ))

        logger.debug(
            "%s → %d boundary test(s) for %s",
            self.generator_name, len(cases), endpoint.full_name,
        )
        return cases

    # ------------------------------------------------------------------ #
    # Numeric boundaries
    # ------------------------------------------------------------------ #

    def _numeric_cases(
        self,
        endpoint: Endpoint,
        spec_id: str,
        param: Parameter,
        schema: Dict[str, Any],
        path_params: Dict[str, Any],
        query_params: Dict[str, Any],
        body: Optional[Any],
        ok_code: int,
        err_code: int,
    ) -> List[TestCase]:
        cases: List[TestCase] = []
        loc = param.location

        def _case(label: str, val: Any, expected: int, sev: str) -> TestCase:
            pq, pp = dict(query_params), dict(path_params)
            if loc == ParameterLocation.QUERY:
                pq[param.name] = val
            elif loc == ParameterLocation.PATH:
                pp[param.name] = val
            return TestCaseFactory.make(
                endpoint=endpoint, spec_id=spec_id,
                name=f"Numeric boundary — {label} for '{param.name}' — {endpoint.full_name}",
                category=TestCategory.BOUNDARY,
                expected_status=expected,
                description=f"Boundary test: '{param.name}' = {val!r} ({label}).",
                path_params=pp, query_params=pq, request_body=body,
                severity=sev,
            )

        cases.append(_case("zero",       0,         ok_code,  Severity.MEDIUM.value))
        cases.append(_case("negative",   -1,        err_code, Severity.MEDIUM.value))
        cases.append(_case("large +ve",  999_999_999, err_code, Severity.MEDIUM.value))
        cases.append(_case("very small", -999_999_999, err_code, Severity.LOW.value))

        if "minimum" in schema:
            mn = schema["minimum"]
            cases.append(_case(f"min ({mn})",   mn,     ok_code,  Severity.HIGH.value))
            cases.append(_case(f"min-1 ({mn-1})", mn-1, err_code, Severity.HIGH.value))
        if "maximum" in schema:
            mx = schema["maximum"]
            cases.append(_case(f"max ({mx})",   mx,     ok_code,  Severity.HIGH.value))
            cases.append(_case(f"max+1 ({mx+1})", mx+1, err_code, Severity.HIGH.value))

        return cases

    # ------------------------------------------------------------------ #
    # String boundaries
    # ------------------------------------------------------------------ #

    def _string_cases(
        self,
        endpoint: Endpoint,
        spec_id: str,
        param: Parameter,
        schema: Dict[str, Any],
        path_params: Dict[str, Any],
        query_params: Dict[str, Any],
        body: Optional[Any],
        err_code: int,
    ) -> List[TestCase]:
        cases: List[TestCase] = []
        loc = param.location

        def _case(label: str, val: Any, sev: str) -> TestCase:
            pq, pp = dict(query_params), dict(path_params)
            if loc == ParameterLocation.QUERY:
                pq[param.name] = val
            elif loc == ParameterLocation.PATH:
                pp[param.name] = val
            return TestCaseFactory.make(
                endpoint=endpoint, spec_id=spec_id,
                name=f"String boundary — {label} for '{param.name}' — {endpoint.full_name}",
                category=TestCategory.BOUNDARY,
                expected_status=err_code,
                description=f"Boundary test: '{param.name}' = {label}.",
                path_params=pp, query_params=pq, request_body=body,
                severity=sev,
            )

        cases.append(_case("single char",     "a",              Severity.MEDIUM.value))
        cases.append(_case("very long string", _VERY_LONG_STRING, Severity.HIGH.value))
        cases.append(_case("unicode",          _UNICODE_STRING,   Severity.MEDIUM.value))
        cases.append(_case("emoji",            _EMOJI_STRING,     Severity.LOW.value))
        cases.append(_case("special chars",    _SPECIAL_CHARS,    Severity.HIGH.value))
        cases.append(_case("whitespace only",  _WHITESPACE_ONLY,  Severity.MEDIUM.value))
        cases.append(_case("null byte",        _NULL_BYTE,        Severity.HIGH.value))

        if "minLength" in schema:
            ml = schema["minLength"]
            if ml > 0:
                cases.append(_case(f"minLength-1 ({ml-1} chars)", "x" * max(0, ml-1), Severity.HIGH.value))
        if "maxLength" in schema:
            ml = schema["maxLength"]
            cases.append(_case(f"maxLength+1 ({ml+1} chars)", "x" * (ml + 1), Severity.HIGH.value))

        return cases

    # ------------------------------------------------------------------ #
    # Enum boundaries
    # ------------------------------------------------------------------ #

    def _enum_cases(
        self,
        endpoint: Endpoint,
        spec_id: str,
        param: Parameter,
        path_params: Dict[str, Any],
        query_params: Dict[str, Any],
        body: Optional[Any],
        ok_code: int,
        err_code: int,
    ) -> List[TestCase]:
        cases: List[TestCase] = []
        loc = param.location

        for val in param.enum_values:
            pq, pp = dict(query_params), dict(path_params)
            if loc == ParameterLocation.QUERY:
                pq[param.name] = val
            elif loc == ParameterLocation.PATH:
                pp[param.name] = val
            cases.append(TestCaseFactory.make(
                endpoint=endpoint, spec_id=spec_id,
                name=f"Enum boundary — valid '{val}' for '{param.name}' — {endpoint.full_name}",
                category=TestCategory.BOUNDARY,
                expected_status=ok_code,
                description=f"Every enum value must be accepted. '{param.name}' = '{val}'.",
                path_params=pp, query_params=pq, request_body=body,
                severity=Severity.HIGH.value,
            ))

        # One invalid enum value
        pq, pp = dict(query_params), dict(path_params)
        invalid_val = "__boundary_invalid_enum__"
        if loc == ParameterLocation.QUERY:
            pq[param.name] = invalid_val
        elif loc == ParameterLocation.PATH:
            pp[param.name] = invalid_val
        cases.append(TestCaseFactory.make(
            endpoint=endpoint, spec_id=spec_id,
            name=f"Enum boundary — invalid value for '{param.name}' — {endpoint.full_name}",
            category=TestCategory.BOUNDARY,
            expected_status=err_code,
            description=f"Value outside declared enum for '{param.name}'. Expect {err_code}.",
            path_params=pp, query_params=pq, request_body=body,
            severity=Severity.HIGH.value,
        ))
        return cases

    # ------------------------------------------------------------------ #
    # Array boundaries
    # ------------------------------------------------------------------ #

    def _array_cases(
        self,
        endpoint: Endpoint,
        spec_id: str,
        param: Parameter,
        path_params: Dict[str, Any],
        query_params: Dict[str, Any],
        body: Optional[Any],
        ok_code: int,
        err_code: int,
    ) -> List[TestCase]:
        cases: List[TestCase] = []
        loc = param.location

        def _case(label: str, val: Any, expected: int, sev: str) -> TestCase:
            pq, pp = dict(query_params), dict(path_params)
            if loc == ParameterLocation.QUERY:
                pq[param.name] = val
            elif loc == ParameterLocation.PATH:
                pp[param.name] = val
            return TestCaseFactory.make(
                endpoint=endpoint, spec_id=spec_id,
                name=f"Array boundary — {label} for '{param.name}' — {endpoint.full_name}",
                category=TestCategory.BOUNDARY,
                expected_status=expected,
                description=f"Array boundary: '{param.name}' = {label}.",
                path_params=pp, query_params=pq, request_body=body,
                severity=sev,
            )

        cases.append(_case("empty array",   [],                   err_code, Severity.HIGH.value))
        cases.append(_case("single item",   ["item"],              ok_code,  Severity.MEDIUM.value))
        cases.append(_case("large array",   ["item"] * 100,        err_code, Severity.MEDIUM.value))
        return cases

    # ------------------------------------------------------------------ #
    # Request-body object boundaries
    # ------------------------------------------------------------------ #

    def _body_object_cases(
        self,
        endpoint: Endpoint,
        spec_id: str,
        path_params: Dict[str, Any],
        query_params: Dict[str, Any],
        body: Optional[Any],
        err_code: int,
    ) -> List[TestCase]:
        cases: List[TestCase] = []
        schema = next(iter(endpoint.request_body.content_types.values()), {})
        required_fields: List[str] = schema.get("required", [])
        properties: Dict[str, Any] = schema.get("properties", {})

        # Empty object boundary
        cases.append(TestCaseFactory.make(
            endpoint=endpoint, spec_id=spec_id,
            name=f"Empty object body — {endpoint.full_name}",
            category=TestCategory.BOUNDARY,
            expected_status=err_code,
            description="Request body is a valid JSON object but has no fields. Expect 400.",
            path_params=path_params, query_params=query_params,
            request_body={},
            severity=Severity.HIGH.value,
        ))

        # Missing each required nested field individually
        for req_field in required_fields:
            if isinstance(body, dict):
                partial = {k: v for k, v in body.items() if k != req_field}
                cases.append(TestCaseFactory.make(
                    endpoint=endpoint, spec_id=spec_id,
                    name=f"Missing required body field '{req_field}' — {endpoint.full_name}",
                    category=TestCategory.BOUNDARY,
                    expected_status=err_code,
                    description=f"Required body field '{req_field}' omitted. Expect 400/422.",
                    path_params=path_params, query_params=query_params,
                    request_body=partial,
                    severity=Severity.HIGH.value,
                ))

        return cases
