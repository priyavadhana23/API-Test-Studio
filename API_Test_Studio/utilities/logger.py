"""
utilities/logger.py
===================
Centralized logging factory for API Test Studio.

Design decisions:
    - One ``LoggerFactory`` sets up handlers once at application startup.
    - Every module calls ``get_logger(__name__)`` — no handler duplication.
    - Console handler: colored, human-readable output.
    - File handler: TimedRotatingFileHandler — one file per day, kept for N days.
    - Configuration is read from a ``LoggingConfig`` instance; no values are
      hardcoded here.

Usage:
    # At application startup (call once):
    from utilities.logger import LoggerFactory
    from configs import Config
    LoggerFactory.initialize(Config().logging)

    # In every other module:
    from utilities.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Ready.")
"""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

# Guard against the LoggingConfig import creating a circular dependency at
# module-import time — we accept it as an ``Any``-typed parameter and access
# its attributes by name.
from typing import Any


# ---------------------------------------------------------------------------
# ANSI colour codes for console output
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"

_LEVEL_COLOURS: dict = {
    "DEBUG":    "\033[36m",   # Cyan
    "INFO":     "\033[32m",   # Green
    "WARNING":  "\033[33m",   # Yellow
    "ERROR":    "\033[31m",   # Red
    "CRITICAL": "\033[35m",   # Magenta
}


class _ColourFormatter(logging.Formatter):
    """
    Custom formatter that injects ANSI colour codes around the log-level name
    when writing to a terminal.  Falls back to plain text on non-TTY streams.
    """

    def __init__(self, fmt: str, date_fmt: str, use_colour: bool = True) -> None:
        super().__init__(fmt=fmt, datefmt=date_fmt)
        self._use_colour = use_colour

    def formatMessage(self, record: logging.LogRecord) -> str:  # noqa: N802
        if self._use_colour:
            colour = _LEVEL_COLOURS.get(record.levelname, "")
            record.levelname = f"{colour}{_BOLD}{record.levelname:<8}{_RESET}"
        return super().formatMessage(record)


# ---------------------------------------------------------------------------
# LoggerFactory
# ---------------------------------------------------------------------------

class LoggerFactory:
    """
    One-time logging configurator.

    Call ``LoggerFactory.initialize(logging_config)`` **once** at startup.
    After that, every call to ``get_logger(name)`` returns a properly
    configured child logger with no duplicate handlers.

    Class attributes:
        _initialized: Guards against double-initialization.
    """

    _initialized: bool = False
    _root_logger_name: str = "api_test_studio"

    @classmethod
    def initialize(cls, logging_cfg: Any, project_root: Optional[Path] = None) -> None:
        """
        Configure the root ``api_test_studio`` logger.

        Args:
            logging_cfg:  A ``LoggingConfig`` instance (or any object with the
                          same attributes: level, console_enabled, file_enabled,
                          log_dir, log_filename_prefix, backup_count, fmt,
                          date_fmt).
            project_root: Absolute path to the project root directory.
                          Defaults to the grandparent of this file.

        Raises:
            RuntimeError: If called more than once in the same process.
        """
        if cls._initialized:
            return  # idempotent — safe to call again without harm

        root = logging.getLogger(cls._root_logger_name)
        root.setLevel(getattr(logging, logging_cfg.level, logging.DEBUG))
        root.propagate = False  # prevent double-logging via Python root logger

        fmt = logging_cfg.fmt
        date_fmt = logging_cfg.date_fmt

        # ── Console handler ──────────────────────────────────────────────
        if logging_cfg.console_enabled:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, logging_cfg.level, logging.DEBUG))
            use_colour = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
            console_handler.setFormatter(_ColourFormatter(fmt, date_fmt, use_colour=use_colour))
            root.addHandler(console_handler)

        # ── File handler (daily rotation) ────────────────────────────────
        if logging_cfg.file_enabled:
            if project_root is None:
                # Two levels up from utilities/logger.py → project root
                project_root = Path(__file__).resolve().parent.parent

            log_dir: Path = project_root / logging_cfg.log_dir
            log_dir.mkdir(parents=True, exist_ok=True)

            log_file: Path = log_dir / f"{logging_cfg.log_filename_prefix}.log"

            file_handler = TimedRotatingFileHandler(
                filename=str(log_file),
                when="midnight",        # rotate at midnight
                interval=1,            # every 1 day
                backupCount=logging_cfg.backup_count,
                encoding="utf-8",
                utc=False,
            )
            file_handler.suffix = "%Y-%m-%d"
            file_handler.setLevel(getattr(logging, logging_cfg.level, logging.DEBUG))
            file_handler.setFormatter(
                logging.Formatter(fmt=fmt, datefmt=date_fmt)
            )
            root.addHandler(file_handler)

        cls._initialized = True
        root.debug("LoggerFactory initialized (level=%s).", logging_cfg.level)

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Return a child logger namespaced under ``api_test_studio``.

        Args:
            name: Typically ``__name__`` of the calling module.

        Returns:
            A ``logging.Logger`` instance.
        """
        # Prefix with the root name so all loggers share the same handlers.
        if not name.startswith(cls._root_logger_name):
            name = f"{cls._root_logger_name}.{name}"
        return logging.getLogger(name)

    @classmethod
    def reset(cls) -> None:
        """
        Remove all handlers and reset initialization state.

        Intended for use in tests only — do not call in production code.
        """
        root = logging.getLogger(cls._root_logger_name)
        for handler in root.handlers[:]:
            handler.close()
            root.removeHandler(handler)
        cls._initialized = False


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """
    Module-level shortcut for ``LoggerFactory.get_logger``.

    This is the only import any module should need::

        from utilities.logger import get_logger
        logger = get_logger(__name__)

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A configured ``logging.Logger`` instance.
    """
    return LoggerFactory.get_logger(name)
