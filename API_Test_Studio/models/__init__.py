"""
models package
==============
Pure data models (dataclasses) for API Test Studio.

No business logic lives in this package — these are data carriers only.

Available models:
    ApiSpec           - Top-level parsed API specification
    Endpoint          - A single API endpoint
    Parameter         - An endpoint parameter (path, query, header, cookie)
    RequestBody       - An endpoint's request body definition
    ExpectedResponse  - A declared response for a given status code
    TestCase          - A generated test case
    Assertion         - A single assertion rule within a test case
    ExecutionResult   - The outcome of executing a test case
    AssertionResult   - The outcome of evaluating one assertion
"""

from models.api_spec import ApiSpec
from models.endpoint import Endpoint, Parameter, RequestBody, ExpectedResponse
from models.test_case import TestCase, Assertion
from models.execution_result import ExecutionResult, AssertionResult

__all__ = [
    "ApiSpec",
    "Endpoint",
    "Parameter",
    "RequestBody",
    "ExpectedResponse",
    "TestCase",
    "Assertion",
    "ExecutionResult",
    "AssertionResult",
]
