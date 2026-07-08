"""
testcase_generator/testcase_factory.py
========================================
Central factory for constructing ``TestCase`` objects.

Every generator calls ``TestCaseFactory.make()`` instead of instantiating
``TestCase`` directly.  This ensures:
    - Consistent field population across all generators
    - A single place to set defaults (severity, status, is_auto_generated)
    - Operation ID and category tag always present
    - No scattered TestCase(...) constructor calls with mismatched arguments

Usage:
    from testcase_generator.testcase_factory import TestCaseFactory

    tc = TestCaseFactory.make(
        endpoint=endpoint,
        spec_id="spec_abc",
        name="Valid POST /users",
        category="positive",
        expected_status=201,
        request_body={"name": "Alice"},
        severity="high",
    )
"""

from typing import Any, Dict, List, Optional

from constants.validation_types import Severity, TestStatus
from models.endpoint import Endpoint
from models.test_case import Assertion, TestCase
from testcase_generator.generator_utils import make_test_id, make_status_assertion


class TestCaseFactory:
    """
    Factory class for building ``TestCase`` objects consistently.

    All methods are static — no instantiation required.
    """

    @staticmethod
    def make(
        endpoint: Endpoint,
        spec_id: str,
        name: str,
        category: str,
        expected_status: int,
        *,
        description: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        path_params: Optional[Dict[str, Any]] = None,
        request_body: Optional[Any] = None,
        extra_assertions: Optional[List[Assertion]] = None,
        severity: str = Severity.MEDIUM.value,
        notes: Optional[str] = None,
        override_method: Optional[str] = None,
    ) -> TestCase:
        """
        Construct and return a fully populated ``TestCase``.

        A status-code assertion is always added automatically based on
        *expected_status*.  Additional assertions can be passed via
        *extra_assertions*.

        Args:
            endpoint:          The ``Endpoint`` this test case targets.
            spec_id:           ID of the parent ``ApiSpec``.
            name:              Human-readable test case name.
            category:          Category label (use ``TestCategory`` constants).
            expected_status:   Expected HTTP response status code.
            description:       Optional detailed description.
            headers:           Request headers dict (merged with defaults).
            query_params:      Query string parameters dict.
            path_params:       Path parameter substitutions dict.
            request_body:      Request body payload.
            extra_assertions:  Additional ``Assertion`` objects beyond status check.
            severity:          Test severity level (use ``Severity`` constants).
            notes:             Free-text notes for the test case.
            override_method:   Use a different HTTP method (for wrong-method tests).

        Returns:
            A fully populated ``TestCase`` instance.
        """
        method = override_method or endpoint.method
        assertions: List[Assertion] = [
            make_status_assertion(
                expected_status,
                f"[{category.upper()}] {name}",
            )
        ]
        if extra_assertions:
            assertions.extend(extra_assertions)

        return TestCase(
            test_id=make_test_id("tc_"),
            spec_id=spec_id,
            endpoint_id=endpoint.endpoint_id,
            name=name,
            description=description or f"{category.upper()} test for {endpoint.full_name}",
            method=method,
            path=endpoint.path,
            headers=headers or {},
            query_params=query_params or {},
            path_params=path_params or {},
            request_body=request_body,
            assertions=assertions,
            severity=severity,
            tags=[category, endpoint.method.lower(), endpoint.operation_id],
            status=TestStatus.PENDING.value,
            is_auto_generated=True,
            notes=notes,
        )
