"""
web_dashboard/backend/middleware/logging_middleware.py
=======================================================
Request-logging and timing middleware.

Reuses the existing ``get_logger`` from utilities/logger.py — no new
logging framework is introduced.

Logged per request:
    method  path  status_code  duration_ms  client_ip

Exceptions are caught, logged at ERROR level, then re-raised so FastAPI's
own exception handlers can return a proper JSON response.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Use the existing framework logger
import sys
from pathlib import Path
_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from utilities.logger import get_logger

logger = get_logger("web_dashboard.backend.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that logs every HTTP request with timing.

    Records:
        - HTTP method and path
        - Response status code
        - Elapsed time in milliseconds
        - Client IP address

    Does NOT log request/response bodies — those may contain sensitive data.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "ERROR  %s %s — %s (%.1f ms) [%s]",
                request.method,
                request.url.path,
                type(exc).__name__,
                elapsed_ms,
                client_ip,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        status = response.status_code

        # Choose log level by status band
        if status < 400:
            log = logger.info
        elif status < 500:
            log = logger.warning
        else:
            log = logger.error

        log(
            "%s  %s %s  %d  %.1f ms  [%s]",
            "→" if status < 400 else "✗",
            request.method,
            request.url.path,
            status,
            elapsed_ms,
            client_ip,
        )

        # Attach timing header for clients / proxies
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        return response
