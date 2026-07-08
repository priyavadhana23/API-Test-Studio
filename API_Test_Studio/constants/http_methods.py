"""
constants/http_methods.py
=========================
Enumeration of standard HTTP request methods.

Usage:
    from constants.http_methods import HttpMethod

    method = HttpMethod.GET
    print(method.value)   # "GET"
    print(HttpMethod.is_valid("POST"))  # True
"""

from enum import Enum


class HttpMethod(str, Enum):
    """
    Standard HTTP methods as defined by RFC 7231 and RFC 5789.

    Inheriting from ``str`` allows instances to be used directly wherever
    a plain string is expected (e.g. in request libraries).

    Example::

        HttpMethod.GET == "GET"   # True
    """

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """
        Return ``True`` if *value* is a recognized HTTP method name.

        Args:
            value: HTTP method string (case-insensitive).

        Returns:
            ``True`` if valid, ``False`` otherwise.
        """
        return value.upper() in cls._value2member_map_

    @classmethod
    def values(cls) -> list:
        """Return a list of all valid HTTP method strings."""
        return [m.value for m in cls]

    # Methods that typically carry a request body
    BODY_METHODS: "frozenset[str]" = frozenset({"POST", "PUT", "PATCH"})

    @classmethod
    def has_body(cls, method: str) -> bool:
        """
        Return ``True`` if *method* conventionally carries a request body.

        Args:
            method: HTTP method string.

        Returns:
            ``True`` for POST, PUT, and PATCH.
        """
        return method.upper() in cls.BODY_METHODS
