"""
configs package
===============
Exposes the Config class as the single entry point for all configuration.

Usage:
    from configs import Config
    config = Config()
"""

from configs.config_loader import Config, EnvironmentConfig, LoggingConfig

__all__ = ["Config", "EnvironmentConfig", "LoggingConfig"]
