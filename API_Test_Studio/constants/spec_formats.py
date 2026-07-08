"""
constants/spec_formats.py
=========================
Enumerations and metadata for API specification formats supported by
API Test Studio.

Usage:
    from constants.spec_formats import SpecFormat, SpecFormatMeta

    fmt = SpecFormat.OPENAPI_3
    print(fmt.value)                          # "openapi_3"
    print(SpecFormatMeta.extensions(fmt))     # [".yaml", ".yml", ".json"]
"""

from enum import Enum
from typing import Dict, List


class SpecFormat(str, Enum):
    """
    Identifiers for API specification formats.

    These values correspond to the ``supported_spec_formats`` list in
    config.yaml and are used throughout the platform to branch on spec type.
    """

    OPENAPI_3 = "openapi_3"
    """OpenAPI Specification v3.x (YAML or JSON)."""

    SWAGGER_2 = "swagger_2"
    """Swagger / OpenAPI Specification v2.0 (YAML or JSON)."""

    POSTMAN_COLLECTION = "postman_collection"
    """Postman Collection v2.x (JSON)."""

    RAML = "raml"
    """RESTful API Modeling Language (YAML)."""


class SpecFormatMeta:
    """
    Metadata about each specification format.

    All methods are static — no instantiation needed.
    """

    # Map each SpecFormat to its accepted file extensions
    _EXTENSIONS: Dict[SpecFormat, List[str]] = {
        SpecFormat.OPENAPI_3:          [".yaml", ".yml", ".json"],
        SpecFormat.SWAGGER_2:          [".yaml", ".yml", ".json"],
        SpecFormat.POSTMAN_COLLECTION: [".json"],
        SpecFormat.RAML:               [".raml", ".yaml", ".yml"],
    }

    # Map each SpecFormat to a human-readable display name
    _DISPLAY_NAMES: Dict[SpecFormat, str] = {
        SpecFormat.OPENAPI_3:          "OpenAPI 3.x",
        SpecFormat.SWAGGER_2:          "Swagger 2.0",
        SpecFormat.POSTMAN_COLLECTION: "Postman Collection",
        SpecFormat.RAML:               "RAML",
    }

    @classmethod
    def extensions(cls, fmt: SpecFormat) -> List[str]:
        """
        Return the accepted file extensions for *fmt*.

        Args:
            fmt: A ``SpecFormat`` member.

        Returns:
            List of lowercase extension strings including the leading dot.
        """
        return cls._EXTENSIONS.get(fmt, [])

    @classmethod
    def display_name(cls, fmt: SpecFormat) -> str:
        """
        Return the human-readable name for *fmt*.

        Args:
            fmt: A ``SpecFormat`` member.

        Returns:
            Display name string.
        """
        return cls._DISPLAY_NAMES.get(fmt, fmt.value)

    @classmethod
    def from_extension(cls, extension: str) -> List[SpecFormat]:
        """
        Return all ``SpecFormat`` members that accept the given file *extension*.

        Args:
            extension: File extension string (e.g. ``".yaml"``).

        Returns:
            List of matching ``SpecFormat`` members (may be empty).
        """
        ext = extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        return [fmt for fmt, exts in cls._EXTENSIONS.items() if ext in exts]

    @classmethod
    def all_extensions(cls) -> List[str]:
        """Return a deduplicated list of all accepted file extensions."""
        seen: List[str] = []
        for exts in cls._EXTENSIONS.values():
            for e in exts:
                if e not in seen:
                    seen.append(e)
        return seen
