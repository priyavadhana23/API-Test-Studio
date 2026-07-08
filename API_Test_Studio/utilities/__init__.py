"""
utilities package
=================
Reusable helpers shared across all API Test Studio modules.

Submodules:
    logger          - Logging factory and get_logger() shortcut
    file_utils      - File I/O, JSON, YAML, CSV, and path helpers
    common_helpers  - String, dict, type coercion, URL, and timestamp utils
"""

from utilities.logger import LoggerFactory, get_logger
from utilities.file_utils import (
    resolve_path,
    ensure_directory,
    path_exists,
    is_file,
    is_directory,
    get_file_extension,
    get_filename,
    list_files,
    read_text_file,
    write_text_file,
    read_json,
    write_json,
    read_yaml,
    write_yaml,
    read_csv,
    write_csv,
)
from utilities.common_helpers import (
    utc_now,
    timestamp_str,
    iso_timestamp,
    generate_id,
    sanitize_filename,
    slugify,
    truncate,
    is_blank,
    deep_merge,
    flatten_dict,
    safe_int,
    safe_float,
    safe_bool,
    build_url,
    is_valid_url,
)

__all__ = [
    # Logger
    "LoggerFactory",
    "get_logger",
    # File utils
    "resolve_path",
    "ensure_directory",
    "path_exists",
    "is_file",
    "is_directory",
    "get_file_extension",
    "get_filename",
    "list_files",
    "read_text_file",
    "write_text_file",
    "read_json",
    "write_json",
    "read_yaml",
    "write_yaml",
    "read_csv",
    "write_csv",
    # Common helpers
    "utc_now",
    "timestamp_str",
    "iso_timestamp",
    "generate_id",
    "sanitize_filename",
    "slugify",
    "truncate",
    "is_blank",
    "deep_merge",
    "flatten_dict",
    "safe_int",
    "safe_float",
    "safe_bool",
    "build_url",
    "is_valid_url",
]
