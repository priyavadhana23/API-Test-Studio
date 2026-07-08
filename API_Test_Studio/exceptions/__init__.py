"""
exceptions package
==================
All custom exceptions for API Test Studio, organised by layer.

Import from the specific submodule for precision, or from here for
convenience:

    # Precise (preferred)
    from exceptions.parser_exceptions import SpecFileNotFoundError

    # Convenient (catches all from a layer)
    from exceptions import ParserError, SpecFileNotFoundError

Hierarchy summary:

    ConfigurationError
    ├── ConfigFileNotFoundError
    ├── ConfigParseError
    ├── MissingConfigKeyError
    └── InvalidEnvironmentError

    ParserError
    ├── UnsupportedSpecFormatError
    ├── SpecFileNotFoundError
    ├── SpecParseError
    └── InvalidSpecStructureError

    ExecutionError
    ├── RequestTimeoutError
    ├── ConnectionError
    ├── AuthenticationError
    └── MaxRetriesExceededError

    ValidationError
    ├── AssertionFailedError
    ├── SchemaValidationError
    └── MissingFieldError
"""

from exceptions.configuration_exceptions import (
    ConfigurationError,
    ConfigFileNotFoundError,
    ConfigParseError,
    MissingConfigKeyError,
    InvalidEnvironmentError,
)
from exceptions.parser_exceptions import (
    ParserError,
    UnsupportedSpecFormatError,
    SpecFileNotFoundError,
    SpecParseError,
    InvalidSpecStructureError,
)
from exceptions.execution_exceptions import (
    ExecutionError,
    RequestTimeoutError,
    ConnectionError,
    AuthenticationError,
    MaxRetriesExceededError,
)
from exceptions.validation_exceptions import (
    ValidationError,
    AssertionFailedError,
    SchemaValidationError,
    MissingFieldError,
)

__all__ = [
    # Configuration
    "ConfigurationError",
    "ConfigFileNotFoundError",
    "ConfigParseError",
    "MissingConfigKeyError",
    "InvalidEnvironmentError",
    # Parser
    "ParserError",
    "UnsupportedSpecFormatError",
    "SpecFileNotFoundError",
    "SpecParseError",
    "InvalidSpecStructureError",
    # Execution
    "ExecutionError",
    "RequestTimeoutError",
    "ConnectionError",
    "AuthenticationError",
    "MaxRetriesExceededError",
    # Validation
    "ValidationError",
    "AssertionFailedError",
    "SchemaValidationError",
    "MissingFieldError",
]
