"""
testcase_generator/generator_utils.py
======================================
Shared, stateless helpers used by every concrete generator.

Responsibilities:
    - Produce type-appropriate valid and invalid sample values for parameters
    - Build Assertion objects consistently
    - Generate unique, traceable test-case IDs
    - Deduplicate test-case lists by content fingerprint
    - Resolve the expected success status code for an endpoint
    - Infer whether an endpoint requires authentication

No generator-specific logic lives here — only reusable primitives.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from constants.app_constants import DataTypes, ParameterLocation
from constants.validation_types import AssertionOperator, ValidationType, Severity
from models.endpoint import Endpoint, Parameter
from models.test_case import Assertion, TestCase
from utilities.common_helpers import generate_id
from utilities.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Test case category labels  (used as tags and in summaries)
# ---------------------------------------------------------------------------

class TestCategory:
    """String constants for test-case category labels."""
    POSITIVE       = "positive"
    NEGATIVE       = "negative"
    BOUNDARY       = "boundary"
    SECURITY       = "security"
    NULL           = "null"
    EMPTY          = "empty"
    DATATYPE       = "datatype"
    ENUM           = "enum"
    AUTH           = "auth"
    HEADER         = "header"
    METHOD         = "method"
    QUERY_PARAM    = "query_param"
    PATH_PARAM     = "path_param"
    REQUEST_BODY   = "request_body"


# ---------------------------------------------------------------------------
# Unique test-case ID generation
# ---------------------------------------------------------------------------

def make_test_id(prefix: str = "tc_") -> str:
    """
    Return a new unique test-case ID.

    Args:
        prefix: Short string prepended to the UUID (default ``"tc_"``).

    Returns:
        Unique ID string, e.g. ``"tc_3f2504e0-…"``.
    """
    return generate_id(prefix)


# ---------------------------------------------------------------------------
# Valid sample values per data type
# ---------------------------------------------------------------------------

_VALID_SAMPLES: Dict[str, Any] = {
    DataTypes.STRING:  "test_value",
    DataTypes.INTEGER: 1,
    DataTypes.NUMBER:  1.0,
    DataTypes.BOOLEAN: True,
    DataTypes.ARRAY:   ["item1", "item2"],
    DataTypes.OBJECT:  {"key": "value"},
    DataTypes.NULL:    None,
}

_INVALID_SAMPLES: Dict[str, List[Any]] = {
    DataTypes.STRING:  [123, True, [], {}],
    DataTypes.INTEGER: ["not_an_int", "abc", True, [], {}],
    DataTypes.NUMBER:  ["not_a_number", "abc", [], {}],
    DataTypes.BOOLEAN: ["not_a_bool", 999, [], {}],
    DataTypes.ARRAY:   ["not_an_array", 123, {}],
    DataTypes.OBJECT:  ["not_an_object", 123, []],
}


def valid_value_for(param: Parameter) -> Any:
    """
    Return a type-appropriate valid sample value for *param*.

    Priority:
        1. Use ``param.example`` if present.
        2. Use the first ``param.enum_values`` entry if enum is defined.
        3. Fall back to the static type-based sample table.

    Args:
        param: The ``Parameter`` to produce a value for.

    Returns:
        A sample value suitable for a positive test case.
    """
    if param.example is not None:
        return param.example
    if param.enum_values:
        return param.enum_values[0]
    return _VALID_SAMPLES.get(param.data_type.lower(), "test_value")


def invalid_values_for(data_type: str) -> List[Any]:
    """
    Return a list of values that are wrong type for *data_type*.

    Args:
        data_type: JSON Schema type string (e.g. ``"string"``, ``"integer"``).

    Returns:
        List of wrong-type sample values.
    """
    return _INVALID_SAMPLES.get(data_type.lower(), ["invalid_value"])


def valid_body_for(endpoint: Endpoint) -> Optional[Dict[str, Any]]:
    """
    Produce a minimal valid request body for *endpoint* based on the
    declared schema's required properties.

    Returns ``None`` when the endpoint has no request body.

    Args:
        endpoint: The ``Endpoint`` model.

    Returns:
        A dict with one valid sample value per required property, or
        ``None`` if there is no request body.
    """
    if not endpoint.request_body:
        return None

    # Use the first declared content-type schema
    schema = next(iter(endpoint.request_body.content_types.values()), {})
    properties: Dict[str, Any] = schema.get("properties", {})
    required_fields: List[str] = schema.get("required", [])

    body: Dict[str, Any] = {}
    for field_name, field_schema in properties.items():
        if field_name in required_fields or required_fields == []:
            ftype = field_schema.get("type", DataTypes.STRING)
            fenum = field_schema.get("enum", [])
            fexample = field_schema.get("example")
            if fexample is not None:
                body[field_name] = fexample
            elif fenum:
                body[field_name] = fenum[0]
            else:
                body[field_name] = _VALID_SAMPLES.get(ftype, "value")

    # If schema has no properties at all, use a simple placeholder
    if not body and endpoint.request_body:
        body = {"data": "test"}

    return body


def valid_path_params_for(endpoint: Endpoint) -> Dict[str, Any]:
    """
    Return a dict of valid sample values for all path parameters.

    Args:
        endpoint: The ``Endpoint`` model.

    Returns:
        Mapping of parameter name → valid sample value.
    """
    return {
        p.name: valid_value_for(p)
        for p in endpoint.parameters
        if p.location == ParameterLocation.PATH
    }


def valid_query_params_for(endpoint: Endpoint) -> Dict[str, Any]:
    """
    Return a dict of valid sample values for all non-required query
    parameters (required ones are covered by positive tests separately).

    Args:
        endpoint: The ``Endpoint`` model.

    Returns:
        Mapping of parameter name → valid sample value.
    """
    return {
        p.name: valid_value_for(p)
        for p in endpoint.parameters
        if p.location == ParameterLocation.QUERY
    }


# ---------------------------------------------------------------------------
# Success status code resolution
# ---------------------------------------------------------------------------

def expected_success_code(endpoint: Endpoint) -> int:
    """
    Return the most appropriate success HTTP status code for *endpoint*.

    Logic:
        - POST → prefer 201, then 200
        - All others → prefer 200, then lowest 2xx declared
        - Fallback → 200

    Args:
        endpoint: The ``Endpoint`` model.

    Returns:
        Integer HTTP status code.
    """
    declared_codes = sorted(endpoint.responses.keys())
    success_codes = [c for c in declared_codes if 200 <= c <= 299]

    if endpoint.method.upper() == "POST":
        if 201 in success_codes:
            return 201
    if 200 in success_codes:
        return 200
    return success_codes[0] if success_codes else 200


def expected_error_code(endpoint: Endpoint, prefer: int = 400) -> int:
    """
    Return the most appropriate client-error status code for *endpoint*.

    Args:
        endpoint: The ``Endpoint`` model.
        prefer:   Preferred code (default 400).

    Returns:
        Integer HTTP status code.
    """
    declared = set(endpoint.responses.keys())
    for code in (prefer, 400, 422, 401, 403, 404):
        if code in declared:
            return code
    return prefer


# ---------------------------------------------------------------------------
# Authentication detection
# ---------------------------------------------------------------------------

def endpoint_requires_auth(endpoint: Endpoint) -> bool:
    """
    Return ``True`` if the endpoint declares any authentication requirement
    other than ``"none"``.

    Args:
        endpoint: The ``Endpoint`` model.

    Returns:
        ``True`` if auth is required.
    """
    for sec_entry in endpoint.security:
        schemes = sec_entry.get("schemes", [])
        for scheme in schemes:
            if scheme and scheme.lower() != "none":
                return True
    return False


# ---------------------------------------------------------------------------
# Assertion builders
# ---------------------------------------------------------------------------

def make_status_assertion(
    expected_code: int,
    description: str = "",
) -> Assertion:
    """
    Build an ``Assertion`` that checks the HTTP response status code.

    Args:
        expected_code: Expected integer status code.
        description:   Human-readable context string.

    Returns:
        Configured ``Assertion`` instance.
    """
    return Assertion(
        assertion_id=make_test_id("asrt_"),
        validation_type=ValidationType.STATUS_CODE.value,
        operator=AssertionOperator.EQUALS.value,
        target="status_code",
        expected_value=expected_code,
        description=description or f"Response status code should be {expected_code}",
    )


def make_schema_assertion(description: str = "") -> Assertion:
    """
    Build an ``Assertion`` that validates the response body against its
    declared JSON Schema.

    Args:
        description: Human-readable context string.

    Returns:
        Configured ``Assertion`` instance.
    """
    return Assertion(
        assertion_id=make_test_id("asrt_"),
        validation_type=ValidationType.RESPONSE_SCHEMA.value,
        operator=AssertionOperator.EQUALS.value,
        target="response_body",
        expected_value=True,
        description=description or "Response body should match declared schema",
    )


def make_body_not_empty_assertion() -> Assertion:
    """Build an Assertion that verifies the response body is not empty."""
    return Assertion(
        assertion_id=make_test_id("asrt_"),
        validation_type=ValidationType.NOT_EMPTY.value,
        operator=AssertionOperator.IS_NOT_NULL.value,
        target="response_body",
        expected_value=True,
        description="Response body should not be empty",
    )


def make_content_type_assertion(expected_mime: str = "application/json") -> Assertion:
    """
    Build an Assertion that checks the response Content-Type header.

    Args:
        expected_mime: Expected MIME type string.

    Returns:
        Configured ``Assertion`` instance.
    """
    return Assertion(
        assertion_id=make_test_id("asrt_"),
        validation_type=ValidationType.CONTENT_TYPE.value,
        operator=AssertionOperator.CONTAINS.value,
        target="Content-Type",
        expected_value=expected_mime,
        description=f"Response Content-Type should contain '{expected_mime}'",
    )


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _fingerprint(tc: TestCase) -> str:
    """
    Produce a stable content fingerprint for a TestCase.

    Two test cases with identical (endpoint_id, name, tags, method,
    path_params, query_params, request_body) are considered duplicates.

    Args:
        tc: The ``TestCase`` to fingerprint.

    Returns:
        A hex digest string.
    """
    key = {
        "endpoint_id": tc.endpoint_id,
        "name": tc.name,
        "method": tc.method,
        "tags": sorted(tc.tags),
        "path_params": tc.path_params,
        "query_params": tc.query_params,
        "body": str(tc.request_body),
    }
    raw = json.dumps(key, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()  # noqa: S324 — not cryptographic


def deduplicate(test_cases: List[TestCase]) -> Tuple[List[TestCase], int]:
    """
    Remove duplicate test cases by content fingerprint.

    Args:
        test_cases: Flat list of all generated ``TestCase`` objects.

    Returns:
        A tuple ``(unique_cases, removed_count)``.
    """
    seen: Dict[str, bool] = {}
    unique: List[TestCase] = []
    for tc in test_cases:
        fp = _fingerprint(tc)
        if fp not in seen:
            seen[fp] = True
            unique.append(tc)
    removed = len(test_cases) - len(unique)
    if removed:
        logger.debug("Deduplication removed %d duplicate test cases.", removed)
    return unique, removed
