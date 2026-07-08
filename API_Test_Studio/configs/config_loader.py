"""
configs/config_loader.py
========================
Centralized configuration loader for API Test Studio.

Responsibilities:
    - Load and parse config.yaml and environments.yaml
    - Expose a unified Config object to all modules
    - Support active-environment resolution
    - Validate required configuration keys on load

Usage:
    from configs.config_loader import Config

    config = Config()
    print(config.app_name)
    print(config.active_environment.base_url)
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_yaml(filepath: Path) -> Dict[str, Any]:
    """
    Read and parse a YAML file.

    Args:
        filepath: Absolute or relative path to the YAML file.

    Returns:
        Parsed YAML content as a dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file cannot be parsed.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Configuration file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    return data if data is not None else {}


# ---------------------------------------------------------------------------
# EnvironmentConfig
# ---------------------------------------------------------------------------

class EnvironmentConfig:
    """
    Represents a single named environment (e.g. development, staging).

    Attributes:
        name:       Human-readable environment name.
        base_url:   Root URL for the API under test.
        auth_type:  Authentication strategy (none, bearer, api_key, …).
        headers:    Default headers sent with every request.
        variables:  Arbitrary key-value substitutions for this environment.
    """

    def __init__(self, env_key: str, data: Dict[str, Any]) -> None:
        self.env_key: str = env_key
        self.name: str = data.get("name", env_key)
        self.base_url: str = data.get("base_url", "")
        self.auth_type: str = data.get("auth_type", "none")
        self.headers: Dict[str, str] = data.get("headers", {})
        self.variables: Dict[str, Any] = data.get("variables", {})

    def get_variable(self, key: str, default: Optional[Any] = None) -> Any:
        """Return an environment variable by key, or *default* if absent."""
        return self.variables.get(key, default)

    def __repr__(self) -> str:
        return (
            f"EnvironmentConfig(env_key={self.env_key!r}, "
            f"base_url={self.base_url!r}, auth_type={self.auth_type!r})"
        )


# ---------------------------------------------------------------------------
# LoggingConfig
# ---------------------------------------------------------------------------

class LoggingConfig:
    """
    Strongly-typed wrapper around the *logging* section of config.yaml.

    Attributes:
        level:                 Root log level string (DEBUG, INFO, …).
        console_enabled:       Whether to emit logs to stdout.
        file_enabled:          Whether to write logs to a rotating file.
        log_dir:               Directory for log files (relative to project root).
        log_filename_prefix:   Prefix applied to every log file name.
        max_bytes:             Maximum size of a single log file before rotation.
        backup_count:          Number of rotated files to keep.
        fmt:                   Log record format string.
        date_fmt:              Date-time format within log records.
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        self.level: str = data.get("level", "INFO").upper()
        self.console_enabled: bool = data.get("console_enabled", True)
        self.file_enabled: bool = data.get("file_enabled", True)
        self.log_dir: str = data.get("log_dir", "logs")
        self.log_filename_prefix: str = data.get("log_filename_prefix", "api_test_studio")
        self.max_bytes: int = data.get("max_bytes", 10_485_760)
        self.backup_count: int = data.get("backup_count", 7)
        self.fmt: str = data.get("format", "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        self.date_fmt: str = data.get("date_format", "%Y-%m-%d %H:%M:%S")

    def __repr__(self) -> str:
        return f"LoggingConfig(level={self.level!r}, file_enabled={self.file_enabled})"


# ---------------------------------------------------------------------------
# Config  (singleton-style facade)
# ---------------------------------------------------------------------------

class Config:
    """
    Central configuration object for API Test Studio.

    Loads *config.yaml* and *environments.yaml* from the ``configs/`` directory
    that sits next to this file, then exposes all settings as typed attributes.

    This class is intended to be instantiated **once** at application startup
    and passed (or imported) wherever configuration is needed.

    Example::

        config = Config()
        print(config.app_name)             # "API Test Studio"
        print(config.active_environment.base_url)

    Args:
        config_dir: Override the directory that contains the YAML files.
                    Defaults to the ``configs/`` folder next to this module.
    """

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        self._config_dir: Path = config_dir or Path(__file__).parent
        self._raw: Dict[str, Any] = {}
        self._environments: Dict[str, EnvironmentConfig] = {}

        self._load()

    # ------------------------------------------------------------------
    # Private loading logic
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load and parse both YAML files, populating all attributes."""
        raw_config = _load_yaml(self._config_dir / "config.yaml")
        raw_envs = _load_yaml(self._config_dir / "environments.yaml")

        self._raw = raw_config

        # Application metadata
        app_section: Dict[str, Any] = raw_config.get("application", {})
        self.app_name: str = app_section.get("name", "API Test Studio")
        self.app_version: str = app_section.get("version", "0.0.0")
        self.app_description: str = app_section.get("description", "")
        self.app_author: str = app_section.get("author", "")

        # Logging config
        self.logging: LoggingConfig = LoggingConfig(raw_config.get("logging", {}))

        # Paths
        self.paths: Dict[str, str] = raw_config.get("paths", {})

        # Supported spec formats
        self.supported_spec_formats: list = raw_config.get("supported_spec_formats", [])

        # Execution defaults
        self.execution: Dict[str, Any] = raw_config.get("execution", {})

        # Reporting defaults
        self.reporting: Dict[str, Any] = raw_config.get("reporting", {})

        # Environments
        for env_key, env_data in raw_envs.items():
            if isinstance(env_data, dict):
                self._environments[env_key] = EnvironmentConfig(env_key, env_data)

        # Active environment
        active_key: str = raw_config.get("active_environment", "development")
        self.active_environment_key: str = active_key
        self.active_environment: EnvironmentConfig = self._resolve_environment(active_key)

    def _resolve_environment(self, key: str) -> EnvironmentConfig:
        """
        Return the EnvironmentConfig for *key*.

        Falls back to an empty EnvironmentConfig if the key is not found so the
        application can still boot and report a useful warning.
        """
        if key not in self._environments:
            raise KeyError(
                f"Active environment '{key}' is not defined in environments.yaml. "
                f"Available environments: {list(self._environments.keys())}"
            )
        return self._environments[key]

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_environment(self, key: str) -> EnvironmentConfig:
        """
        Retrieve any environment by its key.

        Args:
            key: Environment key (e.g. 'staging', 'production').

        Returns:
            The matching EnvironmentConfig.

        Raises:
            KeyError: If the key is not defined in environments.yaml.
        """
        if key not in self._environments:
            raise KeyError(f"Environment '{key}' not found. Available: {list(self._environments.keys())}")
        return self._environments[key]

    def list_environments(self) -> list:
        """Return a list of all configured environment keys."""
        return list(self._environments.keys())

    def get_path(self, key: str) -> str:
        """
        Return a configured path by its key (from the *paths* section).

        Args:
            key: Path key, e.g. 'uploaded_specs', 'reports'.

        Returns:
            The path string, or an empty string if not found.
        """
        return self.paths.get(key, "")

    def get_raw(self, *keys: str, default: Any = None) -> Any:
        """
        Traverse the raw config dict using a sequence of keys.

        Example::

            timeout = config.get_raw("execution", "default_timeout_seconds", default=30)

        Args:
            *keys:   Ordered keys to traverse.
            default: Value returned when the key path is absent.

        Returns:
            The value at the key path, or *default*.
        """
        node: Any = self._raw
        for key in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(key, default)
        return node

    def __repr__(self) -> str:
        return (
            f"Config(app={self.app_name!r}, version={self.app_version!r}, "
            f"active_env={self.active_environment_key!r})"
        )
