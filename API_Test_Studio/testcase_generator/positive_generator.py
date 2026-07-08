"""
testcase_generator/positive_generator.py
==========================================
Generates positive (happy-path) test cases for every endpoint.

A positive test proves that the API behaves correctly when given:
    - Valid values for every required parameter
    - A valid, well-formed request body
    - Correct authentication credentials
    - The correct HTTP method
    - Valid query parameters with permitted values
    - Valid path parameter substitutions

For enum parameters an individual positive test case is also produced
for every declared enum value so full coverage is confirmed.

Category tags produced:
    positive, enum
"""

from typing import Any, Dict, List, Optional

from constants.app_constants import MimeTypes, ParameterLocation
from constants.validation_types import Severity
from interfaces.generator_interface import ITestCaseGenerator
from models.api_spec import ApiSpec
from models.endpoint import Endpoint, Parameter
from models.test_case import TestCase
from testcase_generator.generator_utils import (
    TestCategory,
    endpoint_requires_auth,
    expected_success_code,
    make_body_not_empty_assertion,
    make_content_type_assertion,
    make_schema_assertion,
    valid_body_for,
    valid_path_params_for,
    valid_query_params_for,
    valid_value_for,
)
from testcase_generator.testcase_factory import TestCaseFactory
from utilities.logger import get_logger

logger = get_logger(__name__)


class PositiveGenerator(ITestCaseGenerator):
    """
    Generates happy-path test cases that prove the API works under ideal
    conditions.

    Produces:
        1. One baseline valid-request test per endpoint — all required
           parameters supplied with correct types and values.
        2. One valid-enum test per enum parameter value (verifies every
           accepted enum option returns a success response).
        3. One auth test per authenticated endpoint confirming that a
           valid token/key returns a non-4xx response.
        4. One content-type test confirming the response carries the
           expected MIME type.

    All generated ``TestCase`` objects have ``status = "pending"`` and
    ``is_auto_generated = True``.
    """

    @property
    def generator_name(self) -> str:
        return "Positive Generator"

    def supports(self, endpoint: Endpoint) -> bool:
        """All endpoints support positive testing."""
        return True

    def generate(
        self,
        endpoint: Endpoint,
        spec_id: str,
        environment_config: Any,
    ) -> List[TestCase]:
        """
        Generate positive test cases for *endpoint*.

        Args:
            endpoint:           The endpoint to test.
            spec_id:            Parent ApiSpec ID.
            environment_config: Active environment (base_url, auth_type, …).

        Returns:
            List of positive ``TestCase`` objects.
        """
        cases: List[TestCase] = []
        success_code = expected_success_code(endpoint)
        path_params = valid_path_params_for(endpoint)
        query_params = valid_query_params_for(endpoint)
        body = valid_body_for(endpoint)

        # ── 1. Baseline valid request ─────────────────────────────────
        extra = []
        if endpoint.responses and success_code in endpoint.responses:
            resp = endpoint.responses[success_code]
            if resp.content_types:
                extra.append(make_schema_assertion(
                    f"Response schema valid for {endpoint.full_name}"
                ))
                extra.append(make_content_type_assertion(
                    next(iter(resp.content_types.keys()), MimeTypes.JSON)
                ))
        if success_code != 204:          # 204 No Content has no body
            extra.append(make_body_not_empty_assertion())

        cases.append(TestCaseFactory.make(
            endpoint=endpoint,
            spec_id=spec_id,
            name=f"Valid request — {endpoint.full_name}",
            category=TestCategory.POSITIVE,
            expected_status=success_code,
            description=(
                f"Positive test: send a fully valid request to {endpoint.full_name} "
                f"with all required parameters and a well-formed body. "
                f"Expect HTTP {success_code}."
            ),
            headers=_default_headers(endpoint),
            query_params=query_params,
            path_params=path_params,
            request_body=body,
            extra_assertions=extra,
            severity=Severity.CRITICAL.value,
        ))

        # ── 2. Per-enum positive tests ────────────────────────────────
        for param in endpoint.parameters:
            if not param.enum_values:
                continue
            for enum_val in param.enum_values:
                modified_q = dict(query_params)
                modified_p = dict(path_params)
                if param.location == ParameterLocation.QUERY:
                    modified_q[param.name] = enum_val
                elif param.location == ParameterLocation.PATH:
                    modified_p[param.name] = enum_val

                cases.append(TestCaseFactory.make(
                    endpoint=endpoint,
                    spec_id=spec_id,
                    name=f"Valid enum '{enum_val}' for '{param.name}' — {endpoint.full_name}",
                    category=TestCategory.ENUM,
                    expected_status=success_code,
                    description=(
                        f"Positive enum test: '{param.name}' = '{enum_val}'. "
                        f"All enum values must be accepted."
                    ),
                    headers=_default_headers(endpoint),
                    query_params=modified_q,
                    path_params=modified_p,
                    request_body=body,
                    severity=Severity.HIGH.value,
                ))

        # ── 3. Auth confirmation test ─────────────────────────────────
        if endpoint_requires_auth(endpoint):
            cases.append(TestCaseFactory.make(
                endpoint=endpoint,
                spec_id=spec_id,
                name=f"Valid authentication — {endpoint.full_name}",
                category=TestCategory.AUTH,
                expected_status=success_code,
                description=(
                    f"Auth positive test: valid credentials supplied. "
                    f"Expect HTTP {success_code}, not 401/403."
                ),
                headers=_auth_headers(endpoint, environment_config),
                query_params=query_params,
                path_params=path_params,
                request_body=body,
                severity=Severity.CRITICAL.value,
            ))

        logger.debug(
            "%s → %d positive test(s) for %s",
            self.generator_name, len(cases), endpoint.full_name,
        )
        return cases


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _default_headers(endpoint: Endpoint) -> Dict[str, str]:
    """
    Build a minimal set of request headers for a positive test.

    Args:
        endpoint: The endpoint being tested.

    Returns:
        Dict of header name → value.
    """
    headers: Dict[str, str] = {
        "Accept": MimeTypes.JSON,
    }
    if endpoint.request_body:
        content_type = next(
            iter(endpoint.request_body.content_types.keys()), MimeTypes.JSON
        )
        headers["Content-Type"] = content_type
    return headers


def _auth_headers(endpoint: Endpoint, environment_config: Any) -> Dict[str, str]:
    """
    Produce headers with a valid (placeholder) auth token.

    The actual credential value is a placeholder; Phase 4 will substitute
    real credentials from the environment config.

    Args:
        endpoint:           The endpoint being tested.
        environment_config: Active environment config.

    Returns:
        Headers dict including an Authorization or API key header.
    """
    headers = _default_headers(endpoint)
    auth_type = getattr(environment_config, "auth_type", "none").lower()
    if auth_type in ("bearer", "oauth2"):
        headers["Authorization"] = "Bearer <VALID_TOKEN>"
    elif auth_type == "basic":
        headers["Authorization"] = "Basic <VALID_BASE64_CREDENTIALS>"
    elif auth_type == "api_key":
        headers["X-API-Key"] = "<VALID_API_KEY>"
    else:
        # Infer from the endpoint's declared security schemes
        for sec_entry in endpoint.security:
            for scheme in sec_entry.get("schemes", []):
                sl = scheme.lower()
                if "bearer" in sl or "jwt" in sl:
                    headers["Authorization"] = "Bearer <VALID_TOKEN>"
                    break
                if "api" in sl and "key" in sl:
                    headers["X-API-Key"] = "<VALID_API_KEY>"
                    break
    return headers
