"""
testcase_generator/generator_manager.py
=========================================
Public orchestrator for the test case generation pipeline.

``GeneratorManager`` is the ONLY class the rest of the framework calls.
No external code should ever directly instantiate PositiveGenerator,
NegativeGenerator, BoundaryGenerator, or SecurityGenerator.

Pipeline
--------
    ApiSpec
       │
       ▼
    For each Endpoint
       │
       ├── PositiveGenerator.generate()
       ├── NegativeGenerator.generate()
       ├── BoundaryGenerator.generate()
       └── SecurityGenerator.generate()
       │
       ▼
    Merge all TestCase lists
       │
       ▼
    deduplicate()
       │
       ▼
    Print generation summary
       │
       ▼
    Return List[TestCase]

Extensibility
-------------
To add a new generator (e.g. PerformanceGenerator):
    1. Create the class implementing ITestCaseGenerator.
    2. Call GeneratorManager.register(PerformanceGenerator()) at startup.
    Nothing else changes.
"""

import time
from typing import Any, Dict, List, Optional

from configs.config_loader import EnvironmentConfig
from interfaces.generator_interface import ITestCaseGenerator
from models.api_spec import ApiSpec
from models.endpoint import Endpoint
from models.test_case import TestCase
from testcase_generator.generator_utils import TestCategory, deduplicate
from utilities.logger import get_logger

logger = get_logger(__name__)


class GeneratorManager:
    """
    Orchestrates the complete test case generation pipeline for an ApiSpec.

    Usage::

        manager = GeneratorManager()
        test_cases = manager.generate(spec, environment_config)

    The manager uses a registered list of ``ITestCaseGenerator`` instances.
    The default set (Positive, Negative, Boundary, Security) is registered
    automatically at instantiation.  Additional generators can be appended
    via ``register()``.
    """

    def __init__(self) -> None:
        self._generators: List[ITestCaseGenerator] = []
        self._register_defaults()

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def _register_defaults(self) -> None:
        """Register the four built-in generators in execution order."""
        from testcase_generator.positive_generator  import PositiveGenerator
        from testcase_generator.negative_generator  import NegativeGenerator
        from testcase_generator.boundary_generator  import BoundaryGenerator
        from testcase_generator.security_generator  import SecurityGenerator

        self._generators = [
            PositiveGenerator(),
            NegativeGenerator(),
            BoundaryGenerator(),
            SecurityGenerator(),
        ]
        logger.debug(
            "GeneratorManager initialised with %d generators: %s",
            len(self._generators),
            [g.generator_name for g in self._generators],
        )

    def register(self, generator: ITestCaseGenerator) -> None:
        """
        Append an additional generator to the pipeline.

        Args:
            generator: Any object implementing ``ITestCaseGenerator``.

        Raises:
            TypeError: If *generator* does not implement the interface.
        """
        if not isinstance(generator, ITestCaseGenerator):
            raise TypeError(
                f"Expected ITestCaseGenerator, got {type(generator).__name__}."
            )
        self._generators.append(generator)
        logger.info("Generator registered: %s", generator.generator_name)

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    def generate(
        self,
        spec: ApiSpec,
        environment_config: Optional[EnvironmentConfig] = None,
    ) -> List[TestCase]:
        """
        Run the full generation pipeline for *spec*.

        Args:
            spec:               The parsed ``ApiSpec`` object from Phase 2.
            environment_config: Active ``EnvironmentConfig`` (optional but
                                recommended — generators use it for auth headers).

        Returns:
            Deduplicated list of ``TestCase`` objects covering all endpoints.
        """
        logger.info(
            "Test case generation started for '%s' (%d endpoints).",
            spec.title, spec.endpoint_count,
        )
        start_time = time.monotonic()

        # Per-endpoint stats for the summary
        # { endpoint_id: { category: count } }
        stats: Dict[str, Dict[str, int]] = {}
        all_cases: List[TestCase] = []

        for endpoint in spec.endpoints:
            logger.debug("Processing endpoint: %s", endpoint.full_name)
            ep_cases: List[TestCase] = []
            ep_stats: Dict[str, int] = {
                TestCategory.POSITIVE: 0,
                TestCategory.NEGATIVE: 0,
                TestCategory.BOUNDARY: 0,
                TestCategory.SECURITY: 0,
            }

            for gen in self._generators:
                if not gen.supports(endpoint):
                    logger.debug(
                        "%s skipped %s (supports() = False).",
                        gen.generator_name, endpoint.full_name,
                    )
                    continue

                try:
                    generated = gen.generate(endpoint, spec.spec_id, environment_config)
                    ep_cases.extend(generated)
                    # Map each case's primary category tag to the stats bucket
                    for cat_key in (
                        TestCategory.POSITIVE, TestCategory.NEGATIVE,
                        TestCategory.BOUNDARY, TestCategory.SECURITY,
                    ):
                        count = sum(1 for tc in generated if cat_key in tc.tags)
                        ep_stats[cat_key] += count
                    logger.debug(
                        "%s generated %d cases for %s.",
                        gen.generator_name, len(generated), endpoint.full_name,
                    )
                except Exception as exc:
                    logger.error(
                        "Generator '%s' failed on %s: %s",
                        gen.generator_name, endpoint.full_name, exc,
                        exc_info=True,
                    )

            all_cases.extend(ep_cases)
            stats[endpoint.endpoint_id] = ep_stats
            logger.info(
                "Endpoint %s → %d test case(s) generated.",
                endpoint.full_name, len(ep_cases),
            )

        # ── Deduplicate ───────────────────────────────────────────────
        unique_cases, removed = deduplicate(all_cases)
        logger.info(
            "Deduplication complete: %d unique, %d removed.",
            len(unique_cases), removed,
        )

        elapsed = time.monotonic() - start_time
        logger.info(
            "Generation complete: %d test cases in %.2fs.",
            len(unique_cases), elapsed,
        )

        # ── Print summary ─────────────────────────────────────────────
        self._print_summary(spec, unique_cases, stats, elapsed)

        return unique_cases

    # ------------------------------------------------------------------ #
    # Summary printer
    # ------------------------------------------------------------------ #

    @staticmethod
    def _print_summary(
        spec: ApiSpec,
        all_cases: List[TestCase],
        stats: Dict[str, Dict[str, int]],
        elapsed: float,
    ) -> None:
        """
        Emit a structured generation summary through the logger.

        Args:
            spec:      The parsed ApiSpec.
            all_cases: Final deduplicated TestCase list.
            stats:     Per-endpoint category counts.
            elapsed:   Wall-clock time in seconds.
        """
        sep  = "─" * 52
        wide = "=" * 52

        logger.info(wide)
        logger.info("  TEST GENERATION SUMMARY")
        logger.info(wide)
        logger.info("  API Name  : %s", spec.title)
        logger.info("  Version   : %s", spec.version)
        logger.info("  Endpoints : %d", spec.endpoint_count)
        logger.info(wide)

        for endpoint in spec.endpoints:
            ep_stat = stats.get(endpoint.endpoint_id, {})
            pos = ep_stat.get(TestCategory.POSITIVE, 0)
            neg = ep_stat.get(TestCategory.NEGATIVE, 0)
            bnd = ep_stat.get(TestCategory.BOUNDARY, 0)
            sec = ep_stat.get(TestCategory.SECURITY,  0)
            total_ep = sum(
                1 for tc in all_cases if tc.endpoint_id == endpoint.endpoint_id
            )
            logger.info(sep)
            logger.info("  %s  %s", endpoint.method, endpoint.path)
            logger.info("  Operation ID : %s", endpoint.operation_id)
            logger.info("  Positive     : %d", pos)
            logger.info("  Negative     : %d", neg)
            logger.info("  Boundary     : %d", bnd)
            logger.info("  Security     : %d", sec)
            logger.info("  Total        : %d", total_ep)

        logger.info(wide)
        logger.info("  OVERALL RESULTS")
        logger.info(wide)
        logger.info("  Total Endpoints         : %d", spec.endpoint_count)
        logger.info("  Total Generated Cases   : %d", len(all_cases))
        logger.info("  Generation Time         : %.2fs", elapsed)
        logger.info(wide)
        logger.info("  END OF GENERATION SUMMARY — %s", spec.title)
        logger.info(wide)
