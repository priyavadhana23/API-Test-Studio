"""
testcase_generator package
============================
Phase 3 — Intelligent Test Case Generation Engine for API Test Studio.

Public API (the only import the rest of the framework needs):

    from testcase_generator import GeneratorManager

    manager = GeneratorManager()
    test_cases = manager.generate(spec, environment_config)

Internal modules (not for direct use outside this package):

    generator_interface   — Re-export of ITestCaseGenerator ABC
    generator_utils       — Shared helpers: samplers, assertions, dedup
    testcase_factory      — TestCaseFactory.make() — consistent construction
    positive_generator    — PositiveGenerator: happy-path + enum + auth
    negative_generator    — NegativeGenerator: missing/null/empty/wrong-type/auth/body/header
    boundary_generator    — BoundaryGenerator: numeric/string/enum/array/object boundaries
    security_generator    — SecurityGenerator: injection/traversal/large-payload placeholders
    generator_manager     — GeneratorManager: orchestrator and public facade

To add a new generator (e.g. PerformanceGenerator) in a future phase:
    1. Create the class implementing ITestCaseGenerator in this package.
    2. Either register it in GeneratorManager._register_defaults()
       or call manager.register(PerformanceGenerator()) at runtime.
    3. No other code needs to change.
"""

from testcase_generator.generator_manager import GeneratorManager
from testcase_generator.generator_interface import ITestCaseGenerator

__all__ = ["GeneratorManager", "ITestCaseGenerator"]
