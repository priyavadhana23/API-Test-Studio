"""
exceptions/parser_exceptions.py
================================
Custom exceptions for the API specification parser layer.

Raised by:
    - api_parser/  (Phase 2)

Hierarchy:
    ParserError
    ├── UnsupportedSpecFormatError
    ├── SpecFileNotFoundError
    ├── SpecParseError
    └── InvalidSpecStructureError
"""


class ParserError(Exception):
    """
    Base class for all API specification parsing errors.

    Catch this to handle any parser problem without caring about the
    specific subtype.
    """


class UnsupportedSpecFormatError(ParserError):
    """
    Raised when an uploaded spec file's format is not supported by the
    platform (e.g. a WSDL or GraphQL schema).

    Args:
        format_hint:  The detected or inferred format string.
        supported:    List of supported format identifiers.

    Example::

        raise UnsupportedSpecFormatError("wsdl", ["openapi_3", "swagger_2"])
    """

    def __init__(self, format_hint: str, supported: list) -> None:
        self.format_hint = format_hint
        self.supported = supported
        super().__init__(
            f"Spec format '{format_hint}' is not supported. "
            f"Supported formats: {supported}"
        )


class SpecFileNotFoundError(ParserError):
    """
    Raised when the spec file path provided does not exist on the
    filesystem.

    Args:
        filepath: The path that was searched.
    """

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        super().__init__(f"Specification file not found: '{filepath}'")


class SpecParseError(ParserError):
    """
    Raised when a spec file is found but its content cannot be parsed
    (e.g. malformed JSON or YAML, missing required top-level keys).

    Args:
        filepath: The file that failed to parse.
        reason:   The underlying error message or description.
    """

    def __init__(self, filepath: str, reason: str) -> None:
        self.filepath = filepath
        self.reason = reason
        super().__init__(f"Failed to parse spec '{filepath}': {reason}")


class InvalidSpecStructureError(ParserError):
    """
    Raised when a spec file is valid YAML/JSON but does not conform to
    the expected structure for its declared format (e.g. an OpenAPI 3
    document missing the ``paths`` key).

    Args:
        filepath:  The file being validated.
        field:     The field or section that is invalid or missing.
        message:   Human-readable description of the structural problem.
    """

    def __init__(self, filepath: str, field: str, message: str) -> None:
        self.filepath = filepath
        self.field = field
        super().__init__(
            f"Invalid spec structure in '{filepath}' — field '{field}': {message}"
        )
