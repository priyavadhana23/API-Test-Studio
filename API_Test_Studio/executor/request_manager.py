"""
executor/request_manager.py
=============================
Sends HTTP requests using the ``requests`` library.

Responsibilities:
    - Accept a fully-prepared set of request parameters
    - Dispatch to the correct requests method (GET, POST, PUT, …)
    - Measure round-trip time precisely
    - Return the raw ``requests.Response`` to the caller
    - Raise framework exceptions (not requests exceptions) on failure

This class knows nothing about TestCase, authentication strategy,
URL construction, or response parsing.  It only sends HTTP requests.

Extensibility:
    - Session-level configuration (proxies, client certs, custom adapters)
      is handled by the ``_session`` attribute — swap or configure it
      without changing any calling code.
    - Async execution (Phase 6+): replace ``requests.Session`` with
      ``httpx.AsyncClient`` and make ``send()`` a coroutine.
"""

import time
from typing import Any, Dict, Optional, Tuple

import requests
from requests import Response, Session
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    ReadTimeout,
    Timeout,
)

from constants.app_constants import Timeouts
from constants.http_methods import HttpMethod
from exceptions.execution_exceptions import (
    ConnectionError as FrameworkConnectionError,
    RequestTimeoutError,
)
from utilities.logger import get_logger

logger = get_logger(__name__)

# Methods that must not carry a body per RFC 7231
_BODYLESS_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "DELETE"})


class RequestManager:
    """
    Thin, stateful HTTP client wrapping ``requests.Session``.

    A single ``Session`` is reused across requests to benefit from
    connection pooling and persistent headers.

    Args:
        timeout:     Default request timeout in seconds (connection + read).
        verify_ssl:  Whether to verify TLS certificates (default ``True``).
        proxies:     Dict of proxy URLs, e.g. ``{"https": "http://proxy:8080"}``.
                     Passed directly to requests — ``None`` means no proxy.

    Extension hooks (Phase 5+):
        - ``set_client_cert(cert_path, key_path)`` — client-certificate auth
        - ``set_proxy(proxies)``  — runtime proxy switching
        - Replace ``requests.Session`` with ``httpx.AsyncClient`` for async
    """

    def __init__(
        self,
        timeout: int = Timeouts.REQUEST_DEFAULT,
        verify_ssl: bool = True,
        proxies: Optional[Dict[str, str]] = None,
    ) -> None:
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._proxies = proxies or {}
        self._session: Session = self._build_session()
        logger.debug(
            "RequestManager initialised (timeout=%ds, verify_ssl=%s).",
            timeout, verify_ssl,
        )

    # ------------------------------------------------------------------ #
    # Session management
    # ------------------------------------------------------------------ #

    def _build_session(self) -> Session:
        """
        Build and return a ``requests.Session`` with default settings.

        Override this method in subclasses to attach custom adapters,
        retry adapters (urllib3 Retry), or ``httpx`` clients.
        """
        session = Session()
        session.verify = self._verify_ssl
        if self._proxies:
            session.proxies.update(self._proxies)
        return session

    def set_client_cert(self, cert: Any) -> None:
        """
        Configure a client-side TLS certificate for mutual TLS.

        Args:
            cert: Path to cert file, or ``(cert, key)`` tuple.
                  Passed directly to ``requests.Session.cert``.
        """
        self._session.cert = cert
        logger.info("RequestManager: client certificate configured.")

    def set_proxy(self, proxies: Dict[str, str]) -> None:
        """
        Update session-level proxy settings at runtime.

        Args:
            proxies: Dict mapping scheme to proxy URL.
        """
        self._session.proxies.update(proxies)
        logger.info("RequestManager: proxy settings updated: %s", proxies)

    def close(self) -> None:
        """Close the underlying session and release pooled connections."""
        self._session.close()
        logger.debug("RequestManager: session closed.")

    # ------------------------------------------------------------------ #
    # Core send method
    # ------------------------------------------------------------------ #

    def send(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        form_data: Optional[Dict[str, Any]] = None,
        raw_body: Optional[Any] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[Response, float]:
        """
        Send an HTTP request and return the response plus elapsed time.

        Exactly one of *json_body*, *form_data*, or *raw_body* should be
        provided for request methods that carry a body (POST, PUT, PATCH).
        All are optional — passing none sends a body-less request.

        Args:
            method:       HTTP method string (e.g. ``"GET"``).
            url:          Fully-resolved request URL.
            headers:      Request headers dict.
            query_params: Query-string parameters dict.
            json_body:    Python object to serialise as JSON body.
            form_data:    Dict to send as ``application/x-www-form-urlencoded``.
            raw_body:     Raw string or bytes body (for malformed payloads).
            timeout:      Per-request timeout override in seconds.

        Returns:
            A tuple ``(response, elapsed_ms)`` where *elapsed_ms* is the
            round-trip time in milliseconds.

        Raises:
            RequestTimeoutError:          On read/connect timeout.
            FrameworkConnectionError:     On DNS/connection failure.
            ValueError:                   For unrecognised HTTP methods.
        """
        method_upper = method.upper()
        if not HttpMethod.is_valid(method_upper):
            raise ValueError(
                f"Unknown HTTP method: '{method}'. "
                f"Supported: {HttpMethod.values()}"
            )

        effective_timeout = timeout or self._timeout
        kwargs: Dict[str, Any] = {
            "headers":  headers or {},
            "params":   {k: v for k, v in (query_params or {}).items() if v is not None},
            "timeout":  effective_timeout,
        }

        # Body dispatch — only attach body for non-bodyless methods
        # (we still allow it for DELETE and HEAD in case the test is
        # intentionally sending a wrong-method body test)
        if json_body is not None:
            kwargs["json"] = json_body
        elif form_data is not None:
            kwargs["data"] = form_data
        elif raw_body is not None:
            kwargs["data"] = raw_body

        logger.info(
            "REQUEST  %s %s  (timeout=%ds, body=%s, params=%s)",
            method_upper, url, effective_timeout,
            "json" if json_body is not None else
            "form" if form_data is not None else
            "raw"  if raw_body  is not None else "none",
            list(kwargs.get("params", {}).keys()) or "none",
        )
        if headers:
            # Log headers but redact Authorization values for security
            safe_headers = {
                k: ("***REDACTED***" if k.lower() in ("authorization", "x-api-key") else v)
                for k, v in headers.items()
            }
            logger.debug("REQUEST HEADERS: %s", safe_headers)

        t_start = time.monotonic()
        try:
            response: Response = self._session.request(
                method=method_upper,
                url=url,
                **kwargs,
            )
            elapsed_ms = (time.monotonic() - t_start) * 1000.0

            logger.info(
                "RESPONSE %s %s  →  HTTP %d  (%.1f ms)",
                method_upper, url, response.status_code, elapsed_ms,
            )
            return response, elapsed_ms

        except (Timeout, ReadTimeout) as exc:
            elapsed_ms = (time.monotonic() - t_start) * 1000.0
            logger.error(
                "TIMEOUT  %s %s  after %.1f ms: %s",
                method_upper, url, elapsed_ms, exc,
            )
            raise RequestTimeoutError(url=url, timeout_sec=effective_timeout) from exc

        except RequestsConnectionError as exc:
            elapsed_ms = (time.monotonic() - t_start) * 1000.0
            logger.error(
                "CONN ERR %s %s  after %.1f ms: %s",
                method_upper, url, elapsed_ms, exc,
            )
            raise FrameworkConnectionError(url=url, reason=str(exc)) from exc
