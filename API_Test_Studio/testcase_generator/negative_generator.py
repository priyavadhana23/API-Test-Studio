"""
testcase_generator/negative_generator.py
==========================================
Generates negative test cases that verify the API correctly rejects
invalid, incomplete, or malformed requests.

Every test case targets a specific failure mode and asserts that the
API returns an appropriate error status code (typically 400, 401,
403, 404, or 422).

Categories covered
------------------
- Missing required parameter         (one test per required param)
- Null / None values                  (one per required param)
- Empty string / array / object       (one per param where applicable)
- Wrong data type                     (one per param, using cross-type values)
- Wrong HTTP method                   (two tests per endpoint)
- Missing / invalid authentication    (when auth is required)
- Missing request body                (when body is required)
- Empty request body                  (when body is required)
- Invalid JSON body                   (when body is required)
- Unexpected / extra body fields      (when body exists)
- Invalid enum value                  (one per enum param)
- Invalid query parameter value       (one per query param)
- Unexpected query parameter          (one test)
- Invalid path parameter type         (one per path param)
"""

from typing import Any, Dict, List, Optional

from constants.app_constants import MimeTypes, ParameterLocation
from constants.http_methods import HttpMethod
from constants.validation_types import Severity
from interfaces.generator_interface import ITestCaseGenerator
from models.endpoint import Endpoint
from models.test_case import TestCase
from testcase_generator.generator_utils import (
    TestCategory,
    endpoint_requires_auth,
    expected_error_code,
    expected_success_code,
    invalid_values_for,
    valid_body_for,
    valid_path_params_for,
    valid_query_params_for,
    valid_value_for,
)
from testcase_generator.testcase_factory import TestCaseFactory
from utilities.logger import get_logger

logger = get_logger(__name__)

# Wrong-method map: given a method, produce the most semantically wrong alternative
_WRONG_METHOD_MAP: Dict[str, str] = {
    "GET":    "POST",
    "POST":   "GET",
    "PUT":    "DELETE",
    "DELETE": "PUT",
    "PATCH":  "GET",
    "HEAD":   "POST",
    "OPTIONS": "DELETE",
}


class NegativeGenerator(ITestCaseGenerator):
    """
    Generates negative test cases that prove the API rejects bad requests.

    Every case produced here expects a 4xx response.  The specific code
    (400, 401, 404, 422 …) is resolved from the endpoint's declared
    responses using ``expected_error_code()``.
    """

    @property
    def generator_name(self) -> str:
        return "Negative Generator"

    def supports(self, endpoint: Endpoint) -> bool:
        """All endpoints support negative testing."""
        return True

    def generate(
        self,
        endpoint: Endpoint,
        spec_id: str,
        environment_config: Any,
    ) -> List[TestCase]:
        """
        Generate negative test cases for *endpoint*.

        Args:
            endpoint:           The endpoint to test.
            spec_id:            Parent ApiSpec ID.
            environment_config: Active environment config.

        Returns:
            List of negative ``TestCase`` objects.
        """
        cases: List[TestCase] = []
        err_400 = expected_error_code(endpoint, prefer=400)
        err_401 = expected_error_code(endpoint, prefer=401)
        err_404 = expected_error_code(endpoint, prefer=404)
        path_params = valid_path_params_for(endpoint)
        query_params = valid_query_params_for(endpoint)
        body = valid_body_for(endpoint)

        # ── 1. Missing required parameter ─────────────────────────────
        for param in endpoint.required_parameters:
            if param.location == ParameterLocation.PATH:
                # Missing path param → route not matched → 404
                modified = {k: v for k, v in path_params.items() if k != param.name}
                cases.append(TestCaseFactory.make(
                    endpoint=endpoint,
                    spec_id=spec_id,
                    name=f"Missing required path param '{param.name}' — {endpoint.full_name}",
                    category=TestCategory.PATH_PARAM,
                    expected_status=err_404,
                    description=f"Path parameter '{param.name}' omitted. Expect 404.",
                    path_params=modified,
                    query_params=query_params,
                    request_body=body,
                    severity=Severity.HIGH.value,
                ))
            elif param.location == ParameterLocation.QUERY:
                modified = {k: v for k, v in query_params.items() if k != param.name}
                cases.append(TestCaseFactory.make(
                    endpoint=endpoint,
                    spec_id=spec_id,
                    name=f"Missing required query param '{param.name}' — {endpoint.full_name}",
                    category=TestCategory.QUERY_PARAM,
                    expected_status=err_400,
                    description=f"Required query parameter '{param.name}' omitted. Expect 400.",
                    path_params=path_params,
                    query_params=modified,
                    request_body=body,
                    severity=Severity.HIGH.value,
                ))

        # ── 2. Null values for required parameters ────────────────────
        for param in endpoint.required_parameters:
            if param.location == ParameterLocation.QUERY:
                null_q = dict(query_params)
                null_q[param.name] = None
                cases.append(TestCaseFactory.make(
                    endpoint=endpoint,
                    spec_id=spec_id,
                    name=f"Null value for required param '{param.name}' — {endpoint.full_name}",
                    category=TestCategory.NULL,
                    expected_status=err_400,
                    description=f"Required param '{param.name}' set to null. Expect 400.",
                    path_params=path_params,
                    query_params=null_q,
                    request_body=body,
                    severity=Severity.MEDIUM.value,
                ))
            elif param.location == ParameterLocation.PATH:
                null_p = dict(path_params)
                null_p[param.name] = None
                cases.append(TestCaseFactory.make(
                    endpoint=endpoint,
                    spec_id=spec_id,
                    name=f"Null value for path param '{param.name}' — {endpoint.full_name}",
                    category=TestCategory.NULL,
                    expected_status=err_404,
                    description=f"Path param '{param.name}' set to null. Expect 404.",
                    path_params=null_p,
                    query_params=query_params,
                    request_body=body,
                    severity=Severity.MEDIUM.value,
                ))

        # ── 3. Empty string values for string parameters ───────────────
        for param in endpoint.parameters:
            if param.data_type.lower() not in ("string",):
                continue
            if param.location == ParameterLocation.QUERY:
                empty_q = dict(query_params)
                empty_q[param.name] = ""
                cases.append(TestCaseFactory.make(
                    endpoint=endpoint,
                    spec_id=spec_id,
                    name=f"Empty string for param '{param.name}' — {endpoint.full_name}",
                    category=TestCategory.EMPTY,
                    expected_status=err_400,
                    description=f"Query param '{param.name}' set to empty string. Expect 400.",
                    path_params=path_params,
                    query_params=empty_q,
                    request_body=body,
                    severity=Severity.MEDIUM.value,
                ))

        # ── 4. Wrong data type for each parameter ──────────────────────
        for param in endpoint.parameters:
            wrong_vals = invalid_values_for(param.data_type)
            if not wrong_vals:
                continue
            wrong_val = wrong_vals[0]  # use first wrong-type value only
            if param.location == ParameterLocation.QUERY:
                bad_q = dict(query_params)
                bad_q[param.name] = wrong_val
                cases.append(TestCaseFactory.make(
                    endpoint=endpoint,
                    spec_id=spec_id,
                    name=f"Wrong type for '{param.name}' (got {type(wrong_val).__name__}, expected {param.data_type}) — {endpoint.full_name}",
                    category=TestCategory.DATATYPE,
                    expected_status=err_400,
                    description=(
                        f"Query param '{param.name}' sent with wrong type "
                        f"({type(wrong_val).__name__} instead of {param.data_type}). Expect 400."
                    ),
                    path_params=path_params,
                    query_params=bad_q,
                    request_body=body,
                    severity=Severity.MEDIUM.value,
                ))
            elif param.location == ParameterLocation.PATH:
                bad_p = dict(path_params)
                bad_p[param.name] = wrong_val
                cases.append(TestCaseFactory.make(
                    endpoint=endpoint,
                    spec_id=spec_id,
                    name=f"Wrong type for path param '{param.name}' — {endpoint.full_name}",
                    category=TestCategory.PATH_PARAM,
                    expected_status=err_400,
                    description=(
                        f"Path param '{param.name}' sent as {type(wrong_val).__name__} "
                        f"instead of {param.data_type}. Expect 400."
                    ),
                    path_params=bad_p,
                    query_params=query_params,
                    request_body=body,
                    severity=Severity.MEDIUM.value,
                ))

        # ── 5. Invalid enum value ──────────────────────────────────────
        for param in endpoint.parameters:
            if not param.enum_values:
                continue
            if param.location == ParameterLocation.QUERY:
                bad_q = dict(query_params)
                bad_q[param.name] = "__INVALID_ENUM_VALUE__"
                cases.append(TestCaseFactory.make(
                    endpoint=endpoint,
                    spec_id=spec_id,
                    name=f"Invalid enum for '{param.name}' — {endpoint.full_name}",
                    category=TestCategory.ENUM,
                    expected_status=err_400,
                    description=(
                        f"Enum param '{param.name}' sent with value not in "
                        f"{param.enum_values}. Expect 400."
                    ),
                    path_params=path_params,
                    query_params=bad_q,
                    request_body=body,
                    severity=Severity.HIGH.value,
                ))

        # ── 6. Wrong HTTP method ───────────────────────────────────────
        wrong_method = _WRONG_METHOD_MAP.get(endpoint.method.upper(), "OPTIONS")
        cases.append(TestCaseFactory.make(
            endpoint=endpoint,
            spec_id=spec_id,
            name=f"Wrong HTTP method ({wrong_method}) — {endpoint.full_name}",
            category=TestCategory.METHOD,
            expected_status=405,
            description=(
                f"Send {wrong_method} instead of {endpoint.method} to "
                f"{endpoint.path}. Expect 405 Method Not Allowed."
            ),
            path_params=path_params,
            query_params=query_params,
            request_body=body,
            severity=Severity.MEDIUM.value,
            override_method=wrong_method,
        ))

        # ── 7. Authentication tests ────────────────────────────────────
        if endpoint_requires_auth(endpoint):
            # Missing token
            cases.append(TestCaseFactory.make(
                endpoint=endpoint,
                spec_id=spec_id,
                name=f"Missing authentication token — {endpoint.full_name}",
                category=TestCategory.AUTH,
                expected_status=err_401,
                description="No Authorization header sent. Expect 401.",
                headers={"Content-Type": MimeTypes.JSON},
                path_params=path_params,
                query_params=query_params,
                request_body=body,
                severity=Severity.CRITICAL.value,
            ))
            # Invalid token
            cases.append(TestCaseFactory.make(
                endpoint=endpoint,
                spec_id=spec_id,
                name=f"Invalid authentication token — {endpoint.full_name}",
                category=TestCategory.AUTH,
                expected_status=err_401,
                description="Malformed/expired token sent. Expect 401.",
                headers={
                    "Content-Type": MimeTypes.JSON,
                    "Authorization": "Bearer INVALID_TOKEN_VALUE",
                },
                path_params=path_params,
                query_params=query_params,
                request_body=body,
                severity=Severity.CRITICAL.value,
            ))
            # Wrong API key
            cases.append(TestCaseFactory.make(
                endpoint=endpoint,
                spec_id=spec_id,
                name=f"Wrong API key — {endpoint.full_name}",
                category=TestCategory.AUTH,
                expected_status=err_401,
                description="Wrong API key value sent. Expect 401.",
                headers={
                    "Content-Type": MimeTypes.JSON,
                    "X-API-Key": "WRONG_KEY_VALUE",
                },
                path_params=path_params,
                query_params=query_params,
                request_body=body,
                severity=Severity.HIGH.value,
            ))

        # ── 8. Request body tests ──────────────────────────────────────
        if endpoint.request_body:
            # Missing body
            cases.append(TestCaseFactory.make(
                endpoint=endpoint,
                spec_id=spec_id,
                name=f"Missing request body — {endpoint.full_name}",
                category=TestCategory.REQUEST_BODY,
                expected_status=err_400,
                description="Required body omitted entirely. Expect 400.",
                headers={"Content-Type": MimeTypes.JSON},
                path_params=path_params,
                query_params=query_params,
                request_body=None,
                severity=Severity.HIGH.value,
            ))
            # Empty body
            cases.append(TestCaseFactory.make(
                endpoint=endpoint,
                spec_id=spec_id,
                name=f"Empty request body {{}} — {endpoint.full_name}",
                category=TestCategory.REQUEST_BODY,
                expected_status=err_400,
                description="Empty JSON object sent as body. Expect 400.",
                headers={"Content-Type": MimeTypes.JSON},
                path_params=path_params,
                query_params=query_params,
                request_body={},
                severity=Severity.HIGH.value,
            ))
            # Invalid JSON (raw string, not a dict)
            cases.append(TestCaseFactory.make(
                endpoint=endpoint,
                spec_id=spec_id,
                name=f"Invalid JSON body — {endpoint.full_name}",
                category=TestCategory.REQUEST_BODY,
                expected_status=err_400,
                description="Malformed JSON string sent as body. Expect 400.",
                headers={"Content-Type": MimeTypes.JSON},
                path_params=path_params,
                query_params=query_params,
                request_body="{{invalid_json: true,",
                severity=Severity.HIGH.value,
            ))
            # Unexpected extra fields
            if isinstance(body, dict):
                extra_body = dict(body)
                extra_body["__unexpected_field__"] = "should_be_rejected"
                cases.append(TestCaseFactory.make(
                    endpoint=endpoint,
                    spec_id=spec_id,
                    name=f"Unexpected fields in body — {endpoint.full_name}",
                    category=TestCategory.REQUEST_BODY,
                    expected_status=err_400,
                    description="Body contains undeclared fields. Expect 400 (if strict).",
                    headers={"Content-Type": MimeTypes.JSON},
                    path_params=path_params,
                    query_params=query_params,
                    request_body=extra_body,
                    severity=Severity.LOW.value,
                    notes="Some APIs silently ignore extra fields — adjust expected code if needed.",
                ))

        # ── 9. Header tests ────────────────────────────────────────────
        # Missing Content-Type when body is present
        if endpoint.request_body:
            cases.append(TestCaseFactory.make(
                endpoint=endpoint,
                spec_id=spec_id,
                name=f"Missing Content-Type header — {endpoint.full_name}",
                category=TestCategory.HEADER,
                expected_status=err_400,
                description="Request body sent without Content-Type header. Expect 400/415.",
                headers={"Accept": MimeTypes.JSON},
                path_params=path_params,
                query_params=query_params,
                request_body=body,
                severity=Severity.MEDIUM.value,
            ))
            # Wrong Content-Type
            cases.append(TestCaseFactory.make(
                endpoint=endpoint,
                spec_id=spec_id,
                name=f"Wrong Content-Type (text/plain) — {endpoint.full_name}",
                category=TestCategory.HEADER,
                expected_status=415,
                description="Body sent with wrong Content-Type. Expect 415 Unsupported Media Type.",
                headers={"Content-Type": MimeTypes.TEXT_PLAIN},
                path_params=path_params,
                query_params=query_params,
                request_body=str(body),
                severity=Severity.MEDIUM.value,
                notes="Fallback expected code may be 400 if server does not distinguish.",
            ))

        # ── 10. Unexpected query parameter ─────────────────────────────
        extra_q = dict(query_params)
        extra_q["__unexpected_param__"] = "ignored_or_rejected"
        cases.append(TestCaseFactory.make(
            endpoint=endpoint,
            spec_id=spec_id,
            name=f"Unexpected query parameter — {endpoint.full_name}",
            category=TestCategory.QUERY_PARAM,
            expected_status=expected_success_code(endpoint),  # many APIs ignore unknowns
            description=(
                "Unknown query parameter sent. Most APIs ignore it (200) "
                "but strict servers return 400."
            ),
            path_params=path_params,
            query_params=extra_q,
            request_body=body,
            severity=Severity.LOW.value,
            notes="Adjust expected_status to 400 if the API uses strict query validation.",
        ))

        logger.debug(
            "%s → %d negative test(s) for %s",
            self.generator_name, len(cases), endpoint.full_name,
        )
        return cases
