"""
testcase_generator/security_generator.py
==========================================
Generates placeholder security test cases for every endpoint.

IMPORTANT — these are PLACEHOLDERS ONLY.
No actual HTTP requests are sent in Phase 3.
The generated ``TestCase`` objects are data structures that Phase 4
(executor) will send when security test execution is implemented.

Each case injects a known-malicious or boundary payload into one
parameter or the request body to probe for common API vulnerabilities.

Security categories covered
---------------------------
- SQL Injection          (string parameters and request bodies)
- Cross-Site Scripting   (string parameters)
- Command Injection      (string parameters)
- Path Traversal         (path and query parameters)
- Large Payload          (request body and string parameters)
- Malformed Encoding     (string parameters)
- Invalid UTF-8          (string parameters)
- Duplicate Headers      (header-level test)
"""

from typing import Any, Dict, List, Optional, Tuple

from constants.app_constants import MimeTypes, ParameterLocation
from constants.validation_types import Severity
from interfaces.generator_interface import ITestCaseGenerator
from models.endpoint import Endpoint, Parameter
from models.test_case import TestCase
from testcase_generator.generator_utils import (
    TestCategory,
    expected_error_code,
    valid_body_for,
    valid_path_params_for,
    valid_query_params_for,
)
from testcase_generator.testcase_factory import TestCaseFactory
from utilities.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Payload libraries — read-only, module-level constants
# ---------------------------------------------------------------------------

_SQL_INJECTIONS: List[Tuple[str, str]] = [
    ("SQL basic OR",    "' OR '1'='1"),
    ("SQL DROP",        "'; DROP TABLE users; --"),
    ("SQL UNION",       "' UNION SELECT null,null,null --"),
    ("SQL blind",       "1; WAITFOR DELAY '0:0:5' --"),
]

_XSS_PAYLOADS: List[Tuple[str, str]] = [
    ("XSS script tag",    "<script>alert('xss')</script>"),
    ("XSS img onerror",   "<img src=x onerror=alert(1)>"),
    ("XSS svg",           "<svg/onload=alert(1)>"),
    ("XSS encoded",       "&#x3C;script&#x3E;alert(1)&#x3C;/script&#x3E;"),
]

_CMD_INJECTIONS: List[Tuple[str, str]] = [
    ("CMD semicolon",  "; ls -la"),
    ("CMD backtick",   "`id`"),
    ("CMD pipe",       "| cat /etc/passwd"),
    ("CMD subshell",   "$(whoami)"),
]

_PATH_TRAVERSALS: List[Tuple[str, str]] = [
    ("Path traversal basic",    "../../../etc/passwd"),
    ("Path traversal encoded",  "..%2F..%2F..%2Fetc%2Fpasswd"),
    ("Path traversal windows",  "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts"),
    ("Path traversal null",     "../../../../etc/passwd%00"),
]

_MALFORMED_ENCODINGS: List[Tuple[str, str]] = [
    ("URL double-encoded",   "%2527"),
    ("Null byte",            "%00"),
    ("Overlong UTF-8",       "\xc0\xaf"),
    ("Invalid percent",      "%GG%ZZ"),
]

_LARGE_PAYLOAD_1MB  = "A" * 1_048_576    # 1 MB string
_LARGE_PAYLOAD_10MB = "A" * 10_485_760   # 10 MB string


class SecurityGenerator(ITestCaseGenerator):
    """
    Generates placeholder security test cases for every endpoint.

    These test cases are marked with ``notes="SECURITY_PLACEHOLDER"``
    to clearly signal to the Phase 4 executor that they require careful
    sandboxed execution and should not be run against production systems
    without explicit authorisation.

    All generated ``TestCase`` objects:
        - Have ``is_auto_generated = True``
        - Have ``status = "pending"``
        - Have ``severity = "critical"`` or ``"high"``
        - Include ``"security"`` in their tags
    """

    @property
    def generator_name(self) -> str:
        return "Security Generator"

    def supports(self, endpoint: Endpoint) -> bool:
        """All endpoints require security testing."""
        return True

    def generate(
        self,
        endpoint: Endpoint,
        spec_id: str,
        environment_config: Any,
    ) -> List[TestCase]:
        """
        Generate placeholder security test cases for *endpoint*.

        Args:
            endpoint:           The endpoint to probe.
            spec_id:            Parent ApiSpec ID.
            environment_config: Active environment config.

        Returns:
            List of security placeholder ``TestCase`` objects.
        """
        cases: List[TestCase] = []
        path_params  = valid_path_params_for(endpoint)
        query_params = valid_query_params_for(endpoint)
        body         = valid_body_for(endpoint)
        err_code     = expected_error_code(endpoint, prefer=400)

        string_params = [
            p for p in endpoint.parameters
            if p.data_type.lower() == "string"
        ]

        # ── SQL Injection ──────────────────────────────────────────────
        for label, payload in _SQL_INJECTIONS:
            for param in string_params:
                cases.append(self._injection_case(
                    endpoint, spec_id, param, payload,
                    f"SQL Injection ({label}) — '{param.name}' — {endpoint.full_name}",
                    "SQL injection payload injected into string parameter.",
                    path_params, query_params, body, err_code,
                ))
            if endpoint.request_body and isinstance(body, dict):
                inj_body = {k: payload if isinstance(v, str) else v for k, v in body.items()}
                cases.append(self._body_case(
                    endpoint, spec_id,
                    f"SQL Injection ({label}) in body — {endpoint.full_name}",
                    "SQL injection in every string field of the request body.",
                    inj_body, path_params, query_params, err_code,
                ))

        # ── XSS ───────────────────────────────────────────────────────
        for label, payload in _XSS_PAYLOADS:
            for param in string_params:
                cases.append(self._injection_case(
                    endpoint, spec_id, param, payload,
                    f"XSS ({label}) — '{param.name}' — {endpoint.full_name}",
                    "XSS payload injected into string parameter.",
                    path_params, query_params, body, err_code,
                ))

        # ── Command Injection ─────────────────────────────────────────
        for label, payload in _CMD_INJECTIONS:
            for param in string_params:
                cases.append(self._injection_case(
                    endpoint, spec_id, param, payload,
                    f"Command Injection ({label}) — '{param.name}' — {endpoint.full_name}",
                    "OS command injection payload in string parameter.",
                    path_params, query_params, body, err_code,
                ))

        # ── Path Traversal ────────────────────────────────────────────
        for label, payload in _PATH_TRAVERSALS:
            # Apply to both path and query string params
            for param in endpoint.parameters:
                if param.location in (ParameterLocation.PATH, ParameterLocation.QUERY):
                    cases.append(self._injection_case(
                        endpoint, spec_id, param, payload,
                        f"Path Traversal ({label}) — '{param.name}' — {endpoint.full_name}",
                        "Directory traversal payload in parameter.",
                        path_params, query_params, body, err_code,
                    ))

        # ── Large Payload ─────────────────────────────────────────────
        if endpoint.request_body:
            cases.append(TestCaseFactory.make(
                endpoint=endpoint, spec_id=spec_id,
                name=f"Large payload (1 MB) — {endpoint.full_name}",
                category=TestCategory.SECURITY,
                expected_status=413,
                description="1 MB string body. Expect 413 Payload Too Large or connection drop.",
                headers={"Content-Type": MimeTypes.JSON},
                path_params=path_params, query_params=query_params,
                request_body={"data": _LARGE_PAYLOAD_1MB},
                severity=Severity.HIGH.value,
                notes="SECURITY_PLACEHOLDER — do not run on production without authorisation.",
            ))
            cases.append(TestCaseFactory.make(
                endpoint=endpoint, spec_id=spec_id,
                name=f"Large payload (10 MB) — {endpoint.full_name}",
                category=TestCategory.SECURITY,
                expected_status=413,
                description="10 MB string body. Expect 413 or server reset.",
                headers={"Content-Type": MimeTypes.JSON},
                path_params=path_params, query_params=query_params,
                request_body={"data": _LARGE_PAYLOAD_10MB},
                severity=Severity.HIGH.value,
                notes="SECURITY_PLACEHOLDER — do not run on production without authorisation.",
            ))

        # ── Malformed Encoding ────────────────────────────────────────
        for label, payload in _MALFORMED_ENCODINGS:
            for param in string_params:
                cases.append(self._injection_case(
                    endpoint, spec_id, param, payload,
                    f"Malformed Encoding ({label}) — '{param.name}' — {endpoint.full_name}",
                    "Malformed/double-encoded value in string parameter.",
                    path_params, query_params, body, err_code,
                ))

        # ── Duplicate Headers ─────────────────────────────────────────
        cases.append(TestCaseFactory.make(
            endpoint=endpoint, spec_id=spec_id,
            name=f"Duplicate Content-Type headers — {endpoint.full_name}",
            category=TestCategory.SECURITY,
            expected_status=err_code,
            description="Two Content-Type headers sent. Some servers misparse and accept one.",
            headers={
                "Content-Type": "application/json",
                "content-type": "text/plain",  # duplicate with different casing
            },
            path_params=path_params, query_params=query_params,
            request_body=body,
            severity=Severity.MEDIUM.value,
            notes="SECURITY_PLACEHOLDER",
        ))

        logger.debug(
            "%s → %d security test(s) for %s",
            self.generator_name, len(cases), endpoint.full_name,
        )
        return cases

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _injection_case(
        endpoint: Endpoint,
        spec_id: str,
        param: Parameter,
        payload: str,
        name: str,
        description: str,
        path_params: Dict[str, Any],
        query_params: Dict[str, Any],
        body: Optional[Any],
        err_code: int,
    ) -> TestCase:
        """Build a single injection test case targeting one parameter."""
        pq = dict(query_params)
        pp = dict(path_params)
        if param.location == ParameterLocation.QUERY:
            pq[param.name] = payload
        elif param.location == ParameterLocation.PATH:
            pp[param.name] = payload

        return TestCaseFactory.make(
            endpoint=endpoint, spec_id=spec_id,
            name=name,
            category=TestCategory.SECURITY,
            expected_status=err_code,
            description=description,
            headers={"Content-Type": MimeTypes.JSON},
            path_params=pp, query_params=pq,
            request_body=body,
            severity=Severity.CRITICAL.value,
            notes="SECURITY_PLACEHOLDER — do not run on production without authorisation.",
        )

    @staticmethod
    def _body_case(
        endpoint: Endpoint,
        spec_id: str,
        name: str,
        description: str,
        inj_body: Any,
        path_params: Dict[str, Any],
        query_params: Dict[str, Any],
        err_code: int,
    ) -> TestCase:
        """Build a single injection test case targeting the request body."""
        return TestCaseFactory.make(
            endpoint=endpoint, spec_id=spec_id,
            name=name,
            category=TestCategory.SECURITY,
            expected_status=err_code,
            description=description,
            headers={"Content-Type": MimeTypes.JSON},
            path_params=path_params, query_params=query_params,
            request_body=inj_body,
            severity=Severity.CRITICAL.value,
            notes="SECURITY_PLACEHOLDER — do not run on production without authorisation.",
        )
