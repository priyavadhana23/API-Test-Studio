"""
constants/status_codes.py
=========================
Enumeration and groupings of standard HTTP status codes.

Usage:
    from constants.status_codes import HttpStatus, StatusGroup

    code = HttpStatus.OK
    print(code.value)           # 200
    print(code.description)     # "OK"

    print(StatusGroup.is_success(200))  # True
    print(StatusGroup.is_client_error(404))  # True
"""

from enum import Enum
from typing import Optional


class HttpStatus(Enum):
    """
    Common HTTP status codes with human-readable descriptions.

    Each member's value is the integer status code.
    Access the textual description via the ``.description`` property.

    Example::

        HttpStatus.NOT_FOUND.value        # 404
        HttpStatus.NOT_FOUND.description  # "Not Found"
    """

    # 1xx — Informational
    CONTINUE = 100
    SWITCHING_PROTOCOLS = 101

    # 2xx — Success
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    PARTIAL_CONTENT = 206

    # 3xx — Redirection
    MOVED_PERMANENTLY = 301
    FOUND = 302
    NOT_MODIFIED = 304
    TEMPORARY_REDIRECT = 307
    PERMANENT_REDIRECT = 308

    # 4xx — Client Errors
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    NOT_ACCEPTABLE = 406
    CONFLICT = 409
    GONE = 410
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429

    # 5xx — Server Errors
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504

    # ----------------------------------------------------------------
    # Descriptions lookup
    # ----------------------------------------------------------------

    _DESCRIPTIONS: "dict[int, str]" = {
        100: "Continue",
        101: "Switching Protocols",
        200: "OK",
        201: "Created",
        202: "Accepted",
        204: "No Content",
        206: "Partial Content",
        301: "Moved Permanently",
        302: "Found",
        304: "Not Modified",
        307: "Temporary Redirect",
        308: "Permanent Redirect",
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        406: "Not Acceptable",
        409: "Conflict",
        410: "Gone",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
        501: "Not Implemented",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }

    @property
    def description(self) -> str:
        """Human-readable description of this status code."""
        return self._DESCRIPTIONS.value.get(self.value, "Unknown")

    @classmethod
    def from_code(cls, code: int) -> Optional["HttpStatus"]:
        """
        Look up an ``HttpStatus`` member by its integer code.

        Args:
            code: HTTP status code integer.

        Returns:
            Matching ``HttpStatus`` member, or ``None`` if not found.
        """
        for member in cls:
            if member.value == code:
                return member
        return None

    @classmethod
    def description_for(cls, code: int) -> str:
        """
        Return the description string for an arbitrary status *code*.

        Falls back to ``"Unknown Status"`` for codes not in the enum.

        Args:
            code: Integer HTTP status code.

        Returns:
            Description string.
        """
        return cls._DESCRIPTIONS.value.get(code, "Unknown Status")


class StatusGroup:
    """
    Utility class for categorizing HTTP status codes by group.

    All methods are static so no instantiation is required.

    Example::

        StatusGroup.is_success(201)       # True
        StatusGroup.is_server_error(503)  # True
        StatusGroup.group_name(404)       # "Client Error"
    """

    @staticmethod
    def is_informational(code: int) -> bool:
        """Return ``True`` for 1xx status codes."""
        return 100 <= code <= 199

    @staticmethod
    def is_success(code: int) -> bool:
        """Return ``True`` for 2xx status codes."""
        return 200 <= code <= 299

    @staticmethod
    def is_redirect(code: int) -> bool:
        """Return ``True`` for 3xx status codes."""
        return 300 <= code <= 399

    @staticmethod
    def is_client_error(code: int) -> bool:
        """Return ``True`` for 4xx status codes."""
        return 400 <= code <= 499

    @staticmethod
    def is_server_error(code: int) -> bool:
        """Return ``True`` for 5xx status codes."""
        return 500 <= code <= 599

    @staticmethod
    def is_error(code: int) -> bool:
        """Return ``True`` for any 4xx or 5xx status code."""
        return 400 <= code <= 599

    @staticmethod
    def group_name(code: int) -> str:
        """
        Return the group name for *code*.

        Returns:
            One of ``"Informational"``, ``"Success"``, ``"Redirection"``,
            ``"Client Error"``, ``"Server Error"``, or ``"Unknown"``.
        """
        if 100 <= code <= 199:
            return "Informational"
        if 200 <= code <= 299:
            return "Success"
        if 300 <= code <= 399:
            return "Redirection"
        if 400 <= code <= 499:
            return "Client Error"
        if 500 <= code <= 599:
            return "Server Error"
        return "Unknown"
