"""
executor/execution_manager.py
===============================
Public orchestrator for the Phase 4 execution pipeline.

``ExecutionManager`` is the ONLY class the rest of the framework calls.
No external code should directly instantiate RequestManager, URLBuilder,
PayloadBuilder, AuthenticationManager, or ResponseWrapper.

Pipeline per TestCase
---------------------
    TestCase
       │
       ├─ URLBuilder.build()            → (url, clean_query_params)
       ├─ PayloadBuilder.build()        → PreparedPayload
       ├─ AuthenticationManager.prepare() → merged headers
       │
       └─ RetryHandler.execute(
              RequestManager.send()     → (requests.Response, elapsed_ms)
          )
       │
       └─ ResponseWrapper.wrap()        → ExecutionResult
                                         (status = RUNNING, no assertions)

The manager runs test cases sequentially by default.  Async / parallel
execution is a Phase 6 concern — the interface does not change.

Execution Summary
-----------------
After all test cases are executed, a structured summary is emitted
through the logger showing counts, timing, status code distribution,
and a sample of individual results.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from configs.config_loader import EnvironmentConfig
from constants.app_constants import Timeouts
from constants.validation_types import TestStatus
from exceptions.execution_exceptions import ExecutionError
from executor.authentication_manager import AuthConfig, AuthenticationManager
from executor.payload_builder import PayloadBuilder
from executor.request_manager import RequestManager
from executor.response_wrapper import ResponseWrapper
from executor.retry_handler import RetryHandler, RetryPolicy
from executor.url_builder import URLBuilder
from models.api_spec import ApiSpec
from models.execution_result import ExecutionResult
from models.test_case import TestCase
from utilities.common_helpers import generate_id
from utilities.logger import get_logger

logger = get_logger(__name__)


class ExecutionManager:
    """
    Orchestrates the full HTTP execution pipeline for a list of TestCases.

    Args:
        environment_config: Active ``EnvironmentConfig`` (provides base_url,
                            auth_type, credentials, default headers).
        timeout:            Per-request timeout in seconds.  Defaults to the
                            value in ``config.yaml`` → ``execution.default_timeout_seconds``.
        verify_ssl:         Whether to verify TLS certificates.
        retry_policy:       ``RetryPolicy`` governing retry behaviour.
                            Defaults to ``RetryPolicy()`` (3 retries, exponential back-off).
        max_sample_display: Number of individual results shown in the summary.

    Usage::

        manager = ExecutionManager(env_config)
        results = manager.run(test_cases)
    """

    def __init__(
        self,
        environment_config: Optional[EnvironmentConfig] = None,
        timeout: int = Timeouts.REQUEST_DEFAULT,
        verify_ssl: bool = True,
        retry_policy: Optional[RetryPolicy] = None,
        max_sample_display: int = 10,
    ) -> None:
        self._env_config    = environment_config
        self._timeout       = timeout
        self._verify_ssl    = verify_ssl
        self._retry_policy  = retry_policy or RetryPolicy()
        self._max_samples   = max_sample_display
        self._request_mgr   = RequestManager(timeout=timeout, verify_ssl=verify_ssl)
        self._retry_handler = RetryHandler(self._retry_policy)

        logger.info(
            "ExecutionManager initialised "
            "(timeout=%ds, verify_ssl=%s, max_retries=%d).",
            timeout, verify_ssl, self._retry_policy.max_retries,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run(
        self,
        test_cases: List[TestCase],
        run_id: Optional[str] = None,
        spec_title: str = "Unknown API",
    ) -> List[ExecutionResult]:
        """
        Execute every TestCase in *test_cases* and return ExecutionResults.

        Args:
            test_cases:  List of ``TestCase`` objects from Phase 3.
            run_id:      Optional batch identifier. Auto-generated if omitted.
            spec_title:  API name used in the summary log (cosmetic only).

        Returns:
            List of ``ExecutionResult`` objects in the same order as
            *test_cases*.  Every case is represented — failures produce
            an error-status result rather than being dropped.
        """
        if not test_cases:
            logger.warning("ExecutionManager.run() called with an empty test list.")
            return []

        run_id = run_id or generate_id("run_")
        total  = len(test_cases)

        logger.info("=" * 52)
        logger.info("EXECUTION STARTED  —  %s", spec_title)
        logger.info("Run ID     : %s", run_id)
        logger.info("Test cases : %d", total)
        logger.info("Base URL   : %s", self._base_url())
        logger.info("=" * 52)

        results: List[ExecutionResult] = []
        wall_start = time.monotonic()

        for idx, tc in enumerate(test_cases, start=1):
            logger.debug(
                "[%d/%d] Executing: %s  (%s %s)",
                idx, total, tc.name, tc.method, tc.path,
            )
            result = self._execute_one(tc, run_id)
            results.append(result)

        wall_elapsed = time.monotonic() - wall_start

        self._print_summary(spec_title, results, wall_elapsed)
        return results

    def run_single(
        self,
        test_case: TestCase,
        run_id: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a single ``TestCase`` and return its ``ExecutionResult``.

        Args:
            test_case: The test case to execute.
            run_id:    Optional batch identifier.

        Returns:
            The ``ExecutionResult`` for this case.
        """
        run_id = run_id or generate_id("run_")
        return self._execute_one(test_case, run_id)

    def close(self) -> None:
        """Release the underlying HTTP session and connection pool."""
        self._request_mgr.close()
        logger.debug("ExecutionManager: HTTP session closed.")

    # ------------------------------------------------------------------ #
    # Single-case execution pipeline
    # ------------------------------------------------------------------ #

    def _execute_one(self, tc: TestCase, run_id: str) -> ExecutionResult:
        """
        Run the full pipeline for one TestCase.

        Steps:
            1. Build URL  (URLBuilder)
            2. Build payload  (PayloadBuilder)
            3. Prepare auth headers  (AuthenticationManager)
            4. Merge all headers
            5. Send request with retry  (RetryHandler → RequestManager)
            6. Wrap response  (ResponseWrapper)

        Args:
            tc:     The ``TestCase`` to execute.
            run_id: Batch run identifier.

        Returns:
            ``ExecutionResult`` — never raises.
        """
        base_url = self._base_url()
        url = base_url   # fallback before URLBuilder runs

        try:
            # ── Step 1: Build URL ──────────────────────────────────────
            url, clean_query = URLBuilder.build(
                base_url=base_url,
                path=tc.path,
                path_params=tc.path_params or {},
                query_params=tc.query_params or {},
            )

            # ── Step 2: Build payload ──────────────────────────────────
            payload = PayloadBuilder.build(
                request_body=tc.request_body,
                headers=tc.headers or {},
            )

            # ── Step 3: Prepare auth headers ───────────────────────────
            # If the test case already carries explicit auth headers
            # (e.g. NegativeGenerator's "Invalid token" tests), honour
            # them and skip environment-level auth injection.
            tc_headers = dict(tc.headers or {})
            has_explicit_auth = any(
                k.lower() in ("authorization", "x-api-key")
                for k in tc_headers
            )

            if has_explicit_auth:
                # The generator set specific auth headers — use them as-is
                auth_headers = tc_headers
                logger.debug(
                    "ExecutionManager: using test-case explicit auth headers for '%s'.",
                    tc.name,
                )
            else:
                # Apply environment-level auth
                auth_cfg = AuthConfig.from_environment(self._env_config) \
                    if self._env_config else AuthConfig()
                auth_headers = AuthenticationManager.prepare(
                    auth_config=auth_cfg,
                    existing_headers=tc_headers,
                )

            # ── Step 4: Merge headers — payload Content-Type last ──────
            merged_headers = dict(auth_headers)
            if payload.content_type and "Content-Type" not in merged_headers:
                merged_headers["Content-Type"] = payload.content_type

            # ── Step 5: Send with retry ────────────────────────────────
            body_kwargs = payload.to_requests_kwargs()

            response, elapsed_ms = self._retry_handler.execute(
                self._request_mgr.send,
                method=tc.method,
                url=url,
                headers=merged_headers,
                query_params=clean_query,
                **body_kwargs,
            )

            # ── Step 6: Wrap response ──────────────────────────────────
            return ResponseWrapper.wrap(
                response=response,
                test_id=tc.test_id,
                run_id=run_id,
                response_time_ms=elapsed_ms,
                request_body=tc.request_body,
            )

        except ExecutionError as exc:
            # Framework-level failure (timeout, connection refused, etc.)
            logger.warning(
                "ExecutionManager: execution error for '%s': %s", tc.name, exc
            )
            return ResponseWrapper.wrap_error(
                error=exc,
                test_id=tc.test_id,
                run_id=run_id,
                request_url=url,
                request_body=tc.request_body,
            )

        except Exception as exc:
            # Unexpected failure — log and produce an error result
            logger.error(
                "ExecutionManager: unexpected error for '%s': %s",
                tc.name, exc, exc_info=True,
            )
            return ResponseWrapper.wrap_error(
                error=exc,
                test_id=tc.test_id,
                run_id=run_id,
                request_url=url,
                request_body=tc.request_body,
            )

    # ------------------------------------------------------------------ #
    # Execution summary
    # ------------------------------------------------------------------ #

    def _print_summary(
        self,
        spec_title: str,
        results: List[ExecutionResult],
        elapsed_sec: float,
    ) -> None:
        """
        Emit a structured execution summary through the logger.

        Shows overall counts, status-code distribution, error count,
        and a sample of individual results.

        Args:
            spec_title:  API name.
            results:     All execution results for this run.
            elapsed_sec: Total wall-clock time in seconds.
        """
        total    = len(results)
        errors   = sum(1 for r in results if r.status == TestStatus.ERROR.value)
        received = total - errors

        # Status-code frequency table
        code_counts: Dict[int, int] = {}
        for r in results:
            if r.http_status_code is not None:
                code_counts[r.http_status_code] = \
                    code_counts.get(r.http_status_code, 0) + 1

        # Timing stats (only for completed requests)
        times = [
            r.response_time_ms
            for r in results
            if r.response_time_ms is not None
        ]
        avg_ms  = sum(times) / len(times) if times else 0.0
        min_ms  = min(times) if times else 0.0
        max_ms  = max(times) if times else 0.0

        wide = "=" * 52
        sep  = "─" * 52

        logger.info(wide)
        logger.info("  EXECUTION SUMMARY")
        logger.info(wide)
        logger.info("  API              : %s", spec_title)
        logger.info("  Total Test Cases : %d", total)
        logger.info("  Responses Received: %d", received)
        logger.info("  Execution Errors : %d", errors)
        logger.info("  Total Time       : %.1f s", elapsed_sec)
        logger.info("  Avg Response Time: %.1f ms", avg_ms)
        logger.info("  Min Response Time: %.1f ms", min_ms)
        logger.info("  Max Response Time: %.1f ms", max_ms)
        logger.info(sep)
        logger.info("  STATUS CODE DISTRIBUTION")
        logger.info(sep)
        for code in sorted(code_counts):
            bar_len = min(30, code_counts[code])
            bar = "█" * bar_len
            logger.info("  HTTP %-3d │ %s %d", code, bar, code_counts[code])

        # Sample individual results
        logger.info(sep)
        logger.info("  SAMPLE RESULTS (first %d)", self._max_samples)
        logger.info(sep)
        for r in results[: self._max_samples]:
            if r.status == TestStatus.ERROR.value:
                logger.info(
                    "  [ERROR ] %-50s  err=%s",
                    (r.request_url or "—")[:50],
                    (r.error_message or "")[:60],
                )
            else:
                size_kb = 0.0
                if r.response_body:
                    try:
                        size_kb = len(str(r.response_body)) / 1024
                    except Exception:
                        pass
                logger.info(
                    "  [HTTP%-3d] %-44s  %6.1f ms  %.2f KB",
                    r.http_status_code or 0,
                    (r.request_url or "—")[:44],
                    r.response_time_ms or 0.0,
                    size_kb,
                )

        logger.info(wide)
        logger.info("  END OF EXECUTION SUMMARY — %s", spec_title)
        logger.info(wide)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _base_url(self) -> str:
        """
        Return the base URL from the active environment config.

        Falls back to an empty string if no environment is configured,
        which will trigger a ``ValueError`` in ``URLBuilder.build()``
        with a clear error message.
        """
        if self._env_config and self._env_config.base_url:
            return self._env_config.base_url.rstrip("/")
        return ""

    # ------------------------------------------------------------------ #
    # Context-manager support
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "ExecutionManager":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
