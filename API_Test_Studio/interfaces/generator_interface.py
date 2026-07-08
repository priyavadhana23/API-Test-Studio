"""
interfaces/generator_interface.py
====================================
Abstract base class that every test case generator must implement.

Why this matters:
    Phase 3 will ship multiple generation strategies, each targeting
    a different testing goal:
        - HappyPathGenerator   → valid inputs, expect 2xx
        - EdgeCaseGenerator    → boundary values, empty fields
        - NegativeGenerator    → invalid/missing required params, expect 4xx
        - SecurityGenerator    → injection, auth bypass probes

    The orchestrator runs them all through the same interface so new
    strategies can be added without changing the calling code.

Contract:
    Any class that inherits ``ITestCaseGenerator`` MUST implement:
        - supports()    → declare which endpoint types/methods this handles
        - generate()    → produce a list of TestCase objects for an endpoint

Usage (Phase 3):
    from interfaces.generator_interface import ITestCaseGenerator
    from models.endpoint import Endpoint
    from models.test_case import TestCase

    class HappyPathGenerator(ITestCaseGenerator):
        def supports(self, endpoint: Endpoint) -> bool:
            return True   # applies to all endpoints

        def generate(self, endpoint, spec_id, environment_config) -> list[TestCase]:
            ...
"""

from abc import ABC, abstractmethod
from typing import Any, List

from models.endpoint import Endpoint
from models.test_case import TestCase


class ITestCaseGenerator(ABC):
    """
    Interface (abstract base class) for all test case generators.

    Concrete implementations (Phase 3):
        - HappyPathGenerator
        - EdgeCaseGenerator
        - NegativeTestGenerator
        - SecurityTestGenerator

    A ``GeneratorOrchestrator`` iterates over all registered generators,
    calls ``supports()`` to filter applicable ones for each endpoint, then
    calls ``generate()`` and merges the resulting test cases.
    """

    @abstractmethod
    def supports(self, endpoint: Endpoint) -> bool:
        """
        Return ``True`` if this generator should produce test cases for
        the given endpoint.

        Allows generators to opt out of endpoints they are not designed
        for (e.g. a file-upload generator may only support POST endpoints
        with multipart/form-data bodies).

        Args:
            endpoint: The ``Endpoint`` model being considered.

        Returns:
            ``True`` if this generator applies to the endpoint.
        """

    @abstractmethod
    def generate(
        self,
        endpoint: Endpoint,
        spec_id: str,
        environment_config: Any,
    ) -> List[TestCase]:
        """
        Generate and return a list of ``TestCase`` objects for *endpoint*.

        Args:
            endpoint:           The ``Endpoint`` model to generate cases for.
            spec_id:            ID of the parent ``ApiSpec`` — stored on each
                                ``TestCase`` for traceability.
            environment_config: The active ``EnvironmentConfig`` instance,
                                providing base_url, auth_type, and variables.

        Returns:
            A list of ``TestCase`` instances.  May be empty if the generator
            determines no cases are applicable.

        Raises:
            GeneratorError: (future) On any unrecoverable generation failure.
        """

    @property
    def generator_name(self) -> str:
        """
        Human-readable name for this generator, used in logs and reports.

        Override in subclasses to provide a meaningful name, e.g.
        ``"Happy Path Generator"``.  Defaults to the class name.
        """
        return self.__class__.__name__
