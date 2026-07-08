"""
exceptions/configuration_exceptions.py
=======================================
Custom exceptions for the configuration layer.

Raised by:
    - configs/config_loader.py
    - Any module that validates configuration values at startup

Hierarchy:
    ConfigurationError
    ├── ConfigFileNotFoundError
    ├── ConfigParseError
    ├── MissingConfigKeyError
    └── InvalidEnvironmentError
"""


class ConfigurationError(Exception):
    """
    Base class for all configuration-related errors.

    Catch this to handle any configuration problem without caring about
    the specific subtype.
    """


class ConfigFileNotFoundError(ConfigurationError):
    """
    Raised when a required configuration file (config.yaml or
    environments.yaml) cannot be found on the filesystem.

    Args:
        filepath: The path that was searched.

    Example::

        raise ConfigFileNotFoundError("configs/config.yaml")
    """

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        super().__init__(f"Configuration file not found: '{filepath}'")


class ConfigParseError(ConfigurationError):
    """
    Raised when a configuration file exists but cannot be parsed
    (e.g. malformed YAML).

    Args:
        filepath: The file that failed to parse.
        reason:   The underlying parse error message.
    """

    def __init__(self, filepath: str, reason: str) -> None:
        self.filepath = filepath
        self.reason = reason
        super().__init__(f"Failed to parse configuration file '{filepath}': {reason}")


class MissingConfigKeyError(ConfigurationError):
    """
    Raised when a required configuration key is absent.

    Args:
        key:      The missing key (dot-notation recommended, e.g. ``"logging.level"``).
        filepath: The file where the key was expected.
    """

    def __init__(self, key: str, filepath: str = "config.yaml") -> None:
        self.key = key
        self.filepath = filepath
        super().__init__(f"Required configuration key '{key}' is missing in '{filepath}'")


class InvalidEnvironmentError(ConfigurationError):
    """
    Raised when the active environment key does not exist in
    environments.yaml.

    Args:
        environment:  The requested environment key.
        available:    List of valid environment keys.
    """

    def __init__(self, environment: str, available: list) -> None:
        self.environment = environment
        self.available = available
        super().__init__(
            f"Environment '{environment}' is not defined. "
            f"Available environments: {available}"
        )
