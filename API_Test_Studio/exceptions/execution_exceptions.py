"""
exceptions/execution_exceptions.py
====================================
Custom exceptions for the HTTP request execution layer.

Raised by:
    - executor/  (Phase 4)

Hierarchy:
    ExecutionError
    ├── RequestTimeoutError
    ├── ConnectionError
    ├── AuthenticationError
    └── MaxRetriesExceededError
"""


class ExecutionError(Exception):
    """
    Base class for all request execution errors.

    Catch this to handle any execution problem without caring about the
    specific subtype.
    """


class RequestTimeoutError(ExecutionError):
    """
    Raised when an HTTP request exceeds the configured timeout.

    Args:
        url:         The URL that timed out.
        timeout_sec: The timeout threshold that was exceeded (seconds).

    Example::

        raise RequestTimeoutError("https://api.example.com/users", 30)
    """

    def __init__(self, url: str, timeout_sec: int) -> None:
        self.url = url
        self.timeout_sec = timeout_sec
        super().__init__(
            f"Request to '{url}' timed out after {timeout_sec}s."
        )


class ConnectionError(ExecutionError):
    """
    Raised when the executor cannot establish a TCP connection to the
    target host (e.g. DNS failure, refused connection, network error).

    Args:
        url:    The URL that could not be reached.
        reason: The underlying network error message.
    """

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"Could not connect to '{url}': {reason}")


class AuthenticationError(ExecutionError):
    """
    Raised when the executor receives an HTTP 401 or 403 response,
    indicating that the configured credentials are invalid or insufficient.

    Args:
        url:         The URL that returned the auth error.
        status_code: The HTTP status code received (401 or 403).
    """

    def __init__(self, url: str, status_code: int) -> None:
        self.url = url
        self.status_code = status_code
        label = "Unauthorized" if status_code == 401 else "Forbidden"
        super().__init__(
            f"Authentication failed for '{url}' — HTTP {status_code} {label}."
        )


class MaxRetriesExceededError(ExecutionError):
    """
    Raised when a request has been retried the maximum number of times
    and all attempts have failed.

    Args:
        url:         The URL being called.
        max_retries: The retry limit that was reached.
        last_error:  The error message from the final attempt.
    """

    def __init__(self, url: str, max_retries: int, last_error: str) -> None:
        self.url = url
        self.max_retries = max_retries
        self.last_error = last_error
        super().__init__(
            f"All {max_retries} retry attempt(s) failed for '{url}'. "
            f"Last error: {last_error}"
        )
