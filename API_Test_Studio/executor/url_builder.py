"""
executor/url_builder.py
========================
Constructs fully-resolved request URLs from components.

Responsibilities:
    - Join base URL + endpoint path (handles trailing/leading slashes)
    - Substitute path parameters, e.g. ``/users/{id}`` → ``/users/15``
    - Append query parameters as a properly encoded query string

No HTTP I/O, no authentication, no validation.

Usage:
    url, params = URLBuilder.build(
        base_url="https://api.example.com",
        path="/users/{id}",
        path_params={"id": 15},
        query_params={"verbose": True},
    )
    # url    → "https://api.example.com/users/15"
    # params → {"verbose": True}
"""

import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode, urljoin

from utilities.logger import get_logger

logger = get_logger(__name__)


class URLBuilder:
    """
    Builds final request URLs from a base URL, path template, and parameters.

    All methods are static — no instantiation required.

    Design note:
        Query parameters are returned separately rather than embedded in the
        URL string so that the ``requests`` library can handle encoding
        correctly (it manages lists, special characters, etc.).
    """

    @staticmethod
    def build(
        base_url: str,
        path: str,
        path_params: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build a fully-resolved URL and a clean query-parameter dict.

        Steps:
            1. Normalise the base URL (strip trailing slash).
            2. Substitute path parameters into the path template.
            3. Join base URL + substituted path.
            4. Filter out None-valued query parameters.

        Args:
            base_url:     Root server URL, e.g. ``"https://api.example.com"``.
            path:         Endpoint path template, e.g. ``"/users/{id}"``.
            path_params:  Dict of substitutions, e.g. ``{"id": 15}``.
            query_params: Dict of query string key-value pairs.

        Returns:
            A tuple ``(url, clean_query_params)`` where:
                - ``url`` is the fully resolved URL string with path params
                  already substituted.
                - ``clean_query_params`` is a dict with ``None`` values removed,
                  ready to pass directly to ``requests`` as the ``params``
                  argument.

        Raises:
            ValueError: If *base_url* is empty.
        """
        if not base_url:
            raise ValueError("base_url must not be empty.")

        # ── 1. Normalise base URL ──────────────────────────────────────
        base = base_url.rstrip("/")

        # ── 2. Substitute path parameters ─────────────────────────────
        resolved_path = URLBuilder._substitute_path_params(
            path, path_params or {}
        )

        # ── 3. Join ───────────────────────────────────────────────────
        # Ensure exactly one slash between base and path
        if not resolved_path.startswith("/"):
            resolved_path = "/" + resolved_path
        url = base + resolved_path

        # ── 4. Clean query parameters ─────────────────────────────────
        clean_query: Dict[str, Any] = {
            k: v
            for k, v in (query_params or {}).items()
            if v is not None
        }

        logger.debug(
            "URLBuilder: base='%s'  path='%s'  resolved='%s'  query=%s",
            base_url, path, url, clean_query,
        )
        return url, clean_query

    @staticmethod
    def _substitute_path_params(
        path: str, path_params: Dict[str, Any]
    ) -> str:
        """
        Replace ``{param_name}`` placeholders in *path* with values from
        *path_params*.

        If a placeholder has no matching value in *path_params* it is
        left as-is and a warning is emitted (better than crashing midway
        through a test run).

        Args:
            path:         URL path template, e.g. ``"/orders/{orderId}"``.
            path_params:  Substitution values, e.g. ``{"orderId": "abc123"}``.

        Returns:
            Path string with all matched placeholders replaced.
        """
        if not path_params:
            return path

        result = path
        for name, value in path_params.items():
            placeholder = "{" + name + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value) if value is not None else "")
            else:
                logger.debug(
                    "URLBuilder: path param '%s' has no placeholder in '%s'.",
                    name, path,
                )

        # Warn about any leftover unsubstituted placeholders
        remaining = re.findall(r"\{(\w+)\}", result)
        for leftover in remaining:
            logger.warning(
                "URLBuilder: unsubstituted path placeholder '{%s}' in '%s'. "
                "Verify path_params contains this key.",
                leftover, path,
            )

        return result
