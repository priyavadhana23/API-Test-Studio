"""
executor/retry_handler.py
==========================
Configurable retry logic with exponential back-off for transient
HTTP and network failures.

Design principles:
    - Retry only on transient errors (timeouts, connection drops,
      specific 5xx codes) — never on 4xx client errors.
    - Exponential back-off with optional jitter to spread retries.
    - All retry policy is captured in ``RetryPolicy`` so callers never
      embed retry constants.
    - Zero side-effects between retries — the caller provides the
      callable to retry.

Usage:
    policy = RetryPolicy(max_retries=3, backoff_base=1.0, backoff_max=30.0)
    handler = RetryHandler(policy)

    result = handler.execute(my_callable, url="https://example.com")
"""

import time
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Set, Tuple, Type

from exceptions.execution_exceptions import MaxRetriesExceededError
from utilities.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetryPolicy:
    """
    Immutable configuration for the retry strategy.

    Attributes:
        max_retries:       Maximum number of retry attempts (0 = no retries).
        backoff_base:      Initial wait between retries in seconds.
        backoff_multiplier: Multiplier applied after each retry (exponential).
        backoff_max:       Upper bound on wait time in seconds.
        jitter:            Add a random fraction of the wait to avoid thundering-herd.
        retry_on_status:   Set of HTTP status codes that trigger a retry (e.g. {503}).
        retry_on_exceptions: Tuple of exception types that trigger a retry.
    """

    max_retries: int = 3
    backoff_base: float = 1.0
    backoff_multiplier: float = 2.0
    backoff_max: float = 30.0
    jitter: bool = True
    retry_on_status: Set[int] = field(default_factory=lambda: {500, 502, 503, 504})
    retry_on_exceptions: Tuple[Type[Exception], ...] = field(
        default_factory=lambda: (
            ConnectionError,
            TimeoutError,
            OSError,
        )
    )

    @classmethod
    def no_retry(cls) -> "RetryPolicy":
        """Return a policy that performs no retries."""
        return cls(max_retries=0)

    @classmethod
    def aggressive(cls) -> "RetryPolicy":
        """Return a policy that retries up to 5 times with fast back-off."""
        return cls(max_retries=5, backoff_base=0.5, backoff_max=10.0)


class RetryHandler:
    """
    Executes a callable with automatic retry on transient failures.

    The handler wraps any callable — typically ``RequestManager.send()`` —
    and re-calls it up to ``policy.max_retries`` times on qualifying errors,
    waiting an exponentially increasing duration between attempts.

    Args:
        policy: The ``RetryPolicy`` governing retry behaviour.
    """

    def __init__(self, policy: Optional[RetryPolicy] = None) -> None:
        self._policy = policy or RetryPolicy()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Call *func* with *args* and *kwargs*, retrying on transient errors.

        Args:
            func:     The callable to execute (e.g. ``RequestManager.send``).
            *args:    Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of *func* on success.

        Raises:
            MaxRetriesExceededError: When all retry attempts are exhausted.
            Exception:               Any non-retryable exception from *func*.
        """
        policy = self._policy
        last_exc: Optional[Exception] = None
        url = kwargs.get("url", args[0] if args else "unknown")

        for attempt in range(policy.max_retries + 1):  # attempt 0 = first try
            try:
                result = func(*args, **kwargs)

                # Check if the response status warrants a retry
                status = getattr(result, "status_code", None)
                if status and status in policy.retry_on_status and attempt < policy.max_retries:
                    logger.warning(
                        "RetryHandler: HTTP %d received (attempt %d/%d). Retrying '%s'.",
                        status, attempt + 1, policy.max_retries, url,
                    )
                    self._wait(attempt)
                    continue

                if attempt > 0:
                    logger.info(
                        "RetryHandler: succeeded on attempt %d for '%s'.",
                        attempt + 1, url,
                    )
                return result

            except policy.retry_on_exceptions as exc:
                last_exc = exc
                if attempt < policy.max_retries:
                    wait = self._wait_seconds(attempt)
                    logger.warning(
                        "RetryHandler: %s on attempt %d/%d for '%s'. "
                        "Waiting %.1fs before retry.",
                        type(exc).__name__, attempt + 1, policy.max_retries,
                        url, wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "RetryHandler: all %d attempt(s) exhausted for '%s'. "
                        "Last error: %s",
                        policy.max_retries + 1, url, exc,
                    )

            except Exception as exc:
                # Non-retryable — re-raise immediately
                logger.debug(
                    "RetryHandler: non-retryable exception %s for '%s': %s",
                    type(exc).__name__, url, exc,
                )
                raise

        raise MaxRetriesExceededError(
            url=str(url),
            max_retries=policy.max_retries,
            last_error=str(last_exc),
        )

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _wait_seconds(self, attempt: int) -> float:
        """
        Compute the wait duration for the given attempt index.

        Formula: ``min(base * multiplier^attempt, max)``
        Jitter adds up to 20% random variation.

        Args:
            attempt: Zero-based attempt index.

        Returns:
            Wait duration in seconds.
        """
        p = self._policy
        wait = min(p.backoff_base * (p.backoff_multiplier ** attempt), p.backoff_max)
        if p.jitter:
            wait *= (1.0 + random.uniform(0, 0.2))
        return wait

    def _wait(self, attempt: int) -> None:
        """Sleep for the computed backoff duration."""
        duration = self._wait_seconds(attempt)
        logger.debug("RetryHandler: backing off for %.2fs.", duration)
        time.sleep(duration)
