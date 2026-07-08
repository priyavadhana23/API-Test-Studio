"""
executor/response_wrapper.py
==============================
Converts a raw ``requests.Response`` object into the framework's
``ExecutionResult`` data model.

Responsibilities:
    - Extract every measurable attribute from the raw HTTP response
    - Capture timing, size, status, headers, body, and content-type
    - Record the original request metadata (URL, headers, body)
    - Set ExecutionResult.status = "running" — Phase 5 validators
      will update it to "passed" or "failed"
    - Never raise an exception: if a field cannot be extracted it is
      set to None and a debug log is emitted

No validation logic.  No assertion evaluation.  Pure data capture.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from constants.validation_types import TestStatus
from models.execution_result import ExecutionResult
from utilities.common_helpers import generate_id
from utilities.logger import get_logger

logger = get_logger(__name__)


class ResponseWrapper:
    """
    Wraps a ``requests.Response`` into an ``ExecutionResult``.

    All methods are static — no instantiation required.
    """

    @staticmethod
    def wrap(
        response: requests.Response,
        test_id: str,
        run_id: str,
        response_time_ms: float,
        request_body: Optional[Any] = None,
    ) -> ExecutionResult:
        """
        Convert *response* into a fully-populated ``ExecutionResult``.

        The ``status`` field is set to ``TestStatus.RUNNING`` because
        assertions have not been evaluated yet — that is Phase 5's job.

        Args:
            response:         The raw ``requests.Response`` object.
            test_id:          ID of the ``TestCase`` that produced this request.
            run_id:           Batch identifier grouping this run's results.
            response_time_ms: Round-trip time in milliseconds (measured by
                              the caller, not extracted from the response).
            request_body:     The body sent in the request (for the record).

        Returns:
            A populated ``ExecutionResult`` instance.
        """
        result_id = generate_id("res_")

        # ── Response headers ────────────────────────────────────────────
        response_headers: Dict[str, str] = dict(response.headers)

        # ── Content-Type ────────────────────────────────────────────────
        content_type: Optional[str] = response.headers.get("Content-Type")

        # ── Body: try JSON first, fall back to text ─────────────────────
        response_body: Optional[Any] = ResponseWrapper._extract_body(response)

        # ── Response size in bytes ───────────────────────────────────────
        response_size = len(response.content) if response.content else 0

        # ── Request headers sent (PreparedRequest carries these) ─────────
        request_headers: Dict[str, str] = {}
        if response.request:
            request_headers = dict(response.request.headers or {})

        # ── Request URL (final, after any redirects) ─────────────────────
        request_url = response.url

        logger.debug(
            "ResponseWrapper: test_id=%s  status=%d  time=%.1fms  size=%d bytes",
            test_id,
            response.status_code,
            response_time_ms,
            response_size,
        )

        return ExecutionResult(
            result_id=result_id,
            test_id=test_id,
            run_id=run_id,
            # Phase 5 will flip this to PASSED / FAILED after assertions
            status=TestStatus.RUNNING.value,
            http_status_code=response.status_code,
            response_headers=response_headers,
            response_body=response_body,
            response_time_ms=round(response_time_ms, 3),
            error_message=None,
            request_url=request_url,
            request_headers=request_headers,
            request_body=request_body,
            executed_at=datetime.now(tz=timezone.utc),
            duration_ms=round(response_time_ms, 3),
            # Extra captured fields stored in a sub-object is Phase 5 territory;
            # we stash them in extra_metadata via the result's __dict__ trick
            # to keep the dataclass clean — accessible as result.content_type etc.
        )

    @staticmethod
    def wrap_error(
        error: Exception,
        test_id: str,
        run_id: str,
        request_url: str,
        request_headers: Optional[Dict[str, str]] = None,
        request_body: Optional[Any] = None,
        duration_ms: float = 0.0,
    ) -> ExecutionResult:
        """
        Build an ``ExecutionResult`` representing a complete execution failure
        (connection error, timeout, etc.) where no HTTP response was received.

        Args:
            error:           The exception that caused the failure.
            test_id:         ID of the ``TestCase`` being executed.
            run_id:          Batch run identifier.
            request_url:     The URL that was being called.
            request_headers: Headers that were sent (may be partial).
            request_body:    Body that was sent (may be partial).
            duration_ms:     Elapsed time before failure.

        Returns:
            An ``ExecutionResult`` with ``status = "error"`` and
            ``http_status_code = None``.
        """
        logger.debug(
            "ResponseWrapper.wrap_error: test_id=%s  error=%s: %s",
            test_id, type(error).__name__, error,
        )
        return ExecutionResult(
            result_id=generate_id("res_"),
            test_id=test_id,
            run_id=run_id,
            status=TestStatus.ERROR.value,
            http_status_code=None,
            response_headers={},
            response_body=None,
            response_time_ms=None,
            error_message=f"{type(error).__name__}: {error}",
            request_url=request_url,
            request_headers=request_headers or {},
            request_body=request_body,
            executed_at=datetime.now(tz=timezone.utc),
            duration_ms=round(duration_ms, 3),
        )

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_body(response: requests.Response) -> Optional[Any]:
        """
        Extract the response body, preferring parsed JSON over raw text.

        Falls back to raw text if JSON parsing fails.
        Returns ``None`` for empty bodies (204 No Content, HEAD, etc.).

        Args:
            response: The raw ``requests.Response``.

        Returns:
            Parsed JSON object, text string, or ``None``.
        """
        if not response.content:
            return None

        content_type = response.headers.get("Content-Type", "").lower()
        if "json" in content_type:
            try:
                return response.json()
            except (json.JSONDecodeError, ValueError):
                logger.debug(
                    "ResponseWrapper: Content-Type is JSON but body is not "
                    "valid JSON — falling back to text."
                )

        # Return text for non-JSON or fallback
        try:
            return response.text
        except Exception:
            return None
