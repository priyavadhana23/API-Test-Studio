"""
executor/payload_builder.py
=============================
Builds the request payload from a ``TestCase`` object.

Responsibilities:
    - Determine the correct Content-Type for the request
    - Serialize the body to the right format (JSON, form-data, raw string)
    - Handle special cases: empty body, None body, invalid/malformed JSON,
      raw string payloads (security tests)
    - Return a ``PreparedPayload`` value object consumed by RequestManager

No HTTP I/O, no authentication, no validation.

Design:
    The builder inspects ``tc.request_body`` type and ``tc.headers`` to
    decide serialisation strategy — the TestCase is the single source of
    truth for what the request should look like.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from constants.app_constants import MimeTypes
from utilities.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PreparedPayload:
    """
    Value object carrying the fully-prepared request body and headers.

    Attributes:
        json_body:    Python dict/list to pass as ``json=`` to requests.
                      Mutually exclusive with ``raw_body`` and ``form_data``.
        raw_body:     Raw string or bytes to pass as ``data=`` to requests.
                      Used for deliberately malformed payloads.
        form_data:    Dict to pass as ``data=`` for form-encoded requests.
        content_type: The Content-Type header value that should be sent.
        has_body:     Whether this payload carries any content.
    """

    json_body: Optional[Any] = None
    raw_body: Optional[Any] = None
    form_data: Optional[Dict[str, Any]] = None
    content_type: Optional[str] = None
    has_body: bool = False

    def to_requests_kwargs(self) -> Dict[str, Any]:
        """
        Produce the kwargs dict to unpack into ``requests.request(**kwargs)``.

        Returns:
            Dict with at most one of ``json``, ``data`` set.
        """
        kwargs: Dict[str, Any] = {}
        if self.json_body is not None:
            kwargs["json"] = self.json_body
        elif self.form_data is not None:
            kwargs["data"] = self.form_data
        elif self.raw_body is not None:
            kwargs["data"] = self.raw_body
        return kwargs


class PayloadBuilder:
    """
    Builds a ``PreparedPayload`` from a ``TestCase``'s body and headers.

    All methods are static — no instantiation required.

    Strategy selection (in priority order):
        1. If ``tc.request_body`` is a raw string → send as raw data
           (used for deliberate malformed/invalid JSON tests).
        2. If Content-Type header says ``multipart/form-data`` or
           ``application/x-www-form-urlencoded`` → send as form data.
        3. If ``tc.request_body`` is a dict or list → send as JSON.
        4. If ``tc.request_body`` is ``None`` or ``{}`` → empty / no body.
    """

    @staticmethod
    def build(
        request_body: Optional[Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> PreparedPayload:
        """
        Build a ``PreparedPayload`` for the given body and headers.

        Args:
            request_body: The body from ``TestCase.request_body``.
            headers:      The headers from ``TestCase.headers`` (used to
                          detect Content-Type intent).

        Returns:
            A ``PreparedPayload`` ready to unpack into requests kwargs.
        """
        headers = headers or {}
        content_type = PayloadBuilder._detect_content_type(headers, request_body)

        # ── 1. No body ─────────────────────────────────────────────────
        if request_body is None:
            logger.debug("PayloadBuilder: no body (None).")
            return PreparedPayload(has_body=False, content_type=content_type)

        # ── 2. Raw string (malformed JSON, security payloads, etc.) ───
        if isinstance(request_body, str):
            logger.debug(
                "PayloadBuilder: raw string body (%d chars).", len(request_body)
            )
            return PreparedPayload(
                raw_body=request_body,
                content_type=content_type or MimeTypes.JSON,
                has_body=True,
            )

        # ── 3. Empty dict/list → treat as empty body ───────────────────
        if isinstance(request_body, (dict, list)) and not request_body:
            logger.debug("PayloadBuilder: empty %s body.", type(request_body).__name__)
            return PreparedPayload(
                json_body=request_body,
                content_type=content_type or MimeTypes.JSON,
                has_body=True,
            )

        # ── 4. Form data ───────────────────────────────────────────────
        ct_lower = (content_type or "").lower()
        if "form" in ct_lower:
            if isinstance(request_body, dict):
                logger.debug(
                    "PayloadBuilder: form-data body (%d fields).", len(request_body)
                )
                return PreparedPayload(
                    form_data=request_body,
                    content_type=content_type,
                    has_body=True,
                )

        # ── 5. JSON body (dict or list) ────────────────────────────────
        if isinstance(request_body, (dict, list)):
            logger.debug(
                "PayloadBuilder: JSON body (%s).", type(request_body).__name__
            )
            return PreparedPayload(
                json_body=request_body,
                content_type=MimeTypes.JSON,
                has_body=True,
            )

        # ── 6. Fallback: anything else as raw ─────────────────────────
        logger.debug(
            "PayloadBuilder: fallback raw body (type=%s).", type(request_body).__name__
        )
        return PreparedPayload(
            raw_body=str(request_body),
            content_type=content_type or MimeTypes.JSON,
            has_body=True,
        )

    @staticmethod
    def _detect_content_type(
        headers: Dict[str, str],
        body: Optional[Any],
    ) -> Optional[str]:
        """
        Resolve the Content-Type for the request.

        Priority:
            1. Explicitly set Content-Type header on the test case.
            2. Infer from body type (dict → JSON, str → JSON by default).
            3. Return ``None`` if no body.

        Args:
            headers: The test case headers dict.
            body:    The request body value.

        Returns:
            Content-Type string or ``None``.
        """
        # Case-insensitive search for Content-Type
        for key, value in headers.items():
            if key.lower() == "content-type":
                return value

        if body is None:
            return None
        if isinstance(body, str):
            return MimeTypes.JSON
        if isinstance(body, dict):
            return MimeTypes.JSON
        return MimeTypes.JSON
