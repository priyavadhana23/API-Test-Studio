"""
utilities/common_helpers.py
============================
General-purpose helper functions used across API Test Studio.

This module intentionally has no dependencies on other project modules
(except the logger) so it can be imported anywhere without circular imports.

Provides:
    - String sanitization and normalization
    - Dictionary deep-merge
    - Timestamp generation
    - Unique ID generation
    - Safe type coercion
    - URL construction helpers
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin, urlparse

from utilities.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(tz=timezone.utc)


def timestamp_str(fmt: str = "%Y%m%d_%H%M%S") -> str:
    """
    Return the current UTC time as a formatted string.

    Useful for generating unique filenames or log prefixes.

    Args:
        fmt: ``strftime``-compatible format string.

    Returns:
        Formatted timestamp string.
    """
    return utc_now().strftime(fmt)


def iso_timestamp() -> str:
    """Return the current UTC time in ISO 8601 format."""
    return utc_now().isoformat()


# ---------------------------------------------------------------------------
# Unique ID helpers
# ---------------------------------------------------------------------------

def generate_id(prefix: str = "") -> str:
    """
    Generate a UUID4-based unique identifier.

    Args:
        prefix: Optional string prepended to the UUID (e.g. ``"tc_"``).

    Returns:
        Unique ID string, e.g. ``"tc_3f2504e0-4f89-11d3-9a0c-0305e82c3301"``.
    """
    uid = str(uuid.uuid4())
    return f"{prefix}{uid}" if prefix else uid


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def sanitize_filename(name: str, replacement: str = "_") -> str:
    """
    Replace characters that are unsafe in filenames with *replacement*.

    Unsafe characters: ``/ \\ : * ? " < > |``

    Args:
        name:        Original string.
        replacement: Character used in place of unsafe characters.

    Returns:
        Sanitized filename string.
    """
    return re.sub(r'[/\\:*?"<>|]', replacement, name)


def slugify(text: str) -> str:
    """
    Convert *text* to a URL/filename-safe lowercase slug.

    Example::

        slugify("My API  Test!")  # → "my_api_test"

    Args:
        text: Input string.

    Returns:
        Lowercase slug with spaces and special characters replaced by ``_``.
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)          # remove non-word chars
    text = re.sub(r"[\s_-]+", "_", text)           # collapse whitespace/hyphens
    text = re.sub(r"^_+|_+$", "", text)            # strip leading/trailing _
    return text


def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate *text* to *max_length* characters, appending *suffix* if cut.

    Args:
        text:       Input string.
        max_length: Maximum allowed length (including suffix).
        suffix:     String appended when truncation occurs.

    Returns:
        Possibly truncated string.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def is_blank(value: Optional[str]) -> bool:
    """Return ``True`` if *value* is ``None`` or contains only whitespace."""
    return value is None or not value.strip()


# ---------------------------------------------------------------------------
# Dictionary helpers
# ---------------------------------------------------------------------------

def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge *override* into *base* and return a new dictionary.

    Keys in *override* take precedence over *base*.  Nested dicts are merged
    rather than replaced.

    Args:
        base:     The base dictionary.
        override: Values to merge / overwrite.

    Returns:
        A new merged dictionary (neither input is mutated).
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def flatten_dict(
    data: Dict[str, Any],
    parent_key: str = "",
    separator: str = ".",
) -> Dict[str, Any]:
    """
    Flatten a nested dictionary into a single-level dict using *separator*.

    Example::

        flatten_dict({"a": {"b": 1}})  # → {"a.b": 1}

    Args:
        data:       Nested dictionary.
        parent_key: Prefix for top-level keys (used in recursion).
        separator:  String placed between key levels.

    Returns:
        Flattened dictionary.
    """
    items: Dict[str, Any] = {}
    for key, value in data.items():
        new_key = f"{parent_key}{separator}{key}" if parent_key else key
        if isinstance(value, dict):
            items.update(flatten_dict(value, new_key, separator))
        else:
            items[new_key] = value
    return items


# ---------------------------------------------------------------------------
# Safe type coercion
# ---------------------------------------------------------------------------

def safe_int(value: Any, default: int = 0) -> int:
    """
    Convert *value* to ``int``, returning *default* on failure.

    Args:
        value:   Any value to coerce.
        default: Fallback value.

    Returns:
        Integer representation of *value*, or *default*.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.debug("safe_int: could not convert %r to int, using default %d", value, default)
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Convert *value* to ``float``, returning *default* on failure.

    Args:
        value:   Any value to coerce.
        default: Fallback value.

    Returns:
        Float representation of *value*, or *default*.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.debug("safe_float: could not convert %r to float, using default %f", value, default)
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """
    Convert *value* to ``bool``, understanding common truthy strings.

    Truthy strings: ``"true"``, ``"1"``, ``"yes"``, ``"on"`` (case-insensitive).

    Args:
        value:   Any value to coerce.
        default: Fallback value.

    Returns:
        Boolean representation of *value*, or *default*.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    if isinstance(value, int):
        return bool(value)
    return default


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def build_url(base_url: str, *path_segments: str) -> str:
    """
    Construct a URL by joining *base_url* with *path_segments*.

    Each segment is stripped of leading/trailing slashes before joining.

    Example::

        build_url("https://api.example.com", "v1", "users")
        # → "https://api.example.com/v1/users"

    Args:
        base_url:       The root URL.
        *path_segments: Additional path parts.

    Returns:
        Assembled URL string.
    """
    url = base_url.rstrip("/")
    for segment in path_segments:
        url = f"{url}/{segment.strip('/')}"
    return url


def is_valid_url(url: str) -> bool:
    """
    Return ``True`` if *url* is a syntactically valid HTTP/HTTPS URL.

    Args:
        url: URL string to validate.

    Returns:
        ``True`` if valid, ``False`` otherwise.
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False
