"""
constants/app_constants.py
==========================
Application-wide string and numeric constants for API Test Studio.

Rules:
    - Every string literal used in more than one place MUST live here.
    - Never import this module from other constants submodules (keep it leaf).
    - Group constants logically and document each group.

Usage:
    from constants.app_constants import AppMeta, FilePaths, MimeTypes, AuthTypes
"""


class AppMeta:
    """Top-level application identity constants."""

    NAME: str = "API Test Studio"
    SHORT_NAME: str = "ATS"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Enterprise-grade Generic API Testing Platform"
    CONFIG_FILE: str = "config.yaml"
    ENVIRONMENTS_FILE: str = "environments.yaml"


class FilePaths:
    """
    Default directory and file names used throughout the project.

    All paths are relative to the project root unless noted otherwise.
    """

    UPLOADED_SPECS_DIR: str = "uploaded_specs"
    REPORTS_DIR: str = "reports"
    HISTORY_DIR: str = "history"
    DATABASE_DIR: str = "database"
    LOGS_DIR: str = "logs"
    SCHEMAS_DIR: str = "schemas"
    CONFIGS_DIR: str = "configs"

    # Generated file suffixes
    REPORT_SUFFIX: str = "_report"
    RESULT_SUFFIX: str = "_result"

    # Placeholder / keep-alive file
    GITKEEP: str = ".gitkeep"


class MimeTypes:
    """
    MIME / Content-Type strings commonly encountered in REST APIs.
    """

    JSON: str = "application/json"
    XML: str = "application/xml"
    FORM_URLENCODED: str = "application/x-www-form-urlencoded"
    MULTIPART_FORM: str = "multipart/form-data"
    TEXT_PLAIN: str = "text/plain"
    TEXT_HTML: str = "text/html"
    OCTET_STREAM: str = "application/octet-stream"
    YAML: str = "application/yaml"


class AuthTypes:
    """
    Supported authentication strategy identifiers.

    These strings must match the ``auth_type`` values used in
    environments.yaml.
    """

    NONE: str = "none"
    API_KEY: str = "api_key"
    BEARER: str = "bearer"
    BASIC: str = "basic"
    OAUTH2: str = "oauth2"

    ALL: tuple = (NONE, API_KEY, BEARER, BASIC, OAUTH2)


class ParameterLocation:
    """
    Locations where an API parameter can appear in a request.
    Mirrors the OpenAPI ``in`` field vocabulary.
    """

    QUERY: str = "query"
    PATH: str = "path"
    HEADER: str = "header"
    COOKIE: str = "cookie"
    BODY: str = "body"

    ALL: tuple = (QUERY, PATH, HEADER, COOKIE, BODY)


class DataTypes:
    """
    Primitive data types used in API schema definitions.
    Mirrors the JSON Schema / OpenAPI type vocabulary.
    """

    STRING: str = "string"
    INTEGER: str = "integer"
    NUMBER: str = "number"
    BOOLEAN: str = "boolean"
    ARRAY: str = "array"
    OBJECT: str = "object"
    NULL: str = "null"

    ALL: tuple = (STRING, INTEGER, NUMBER, BOOLEAN, ARRAY, OBJECT, NULL)


class ReportFormats:
    """Supported output formats for test execution reports."""

    HTML: str = "html"
    JSON: str = "json"
    CSV: str = "csv"
    PDF: str = "pdf"
    XML: str = "xml"

    ALL: tuple = (HTML, JSON, CSV, PDF, XML)
    DEFAULT: str = HTML


class Timeouts:
    """Default timeout values in seconds."""

    REQUEST_DEFAULT: int = 30
    REQUEST_MAX: int = 300
    CONNECTION: int = 10
    READ: int = 60


class LogMessages:
    """
    Standardized log message templates.

    Use these instead of freeform strings to keep log output consistent
    and searchable.
    """

    APP_INIT_START: str = "Initializing %s v%s ..."
    APP_INIT_SUCCESS: str = "%s initialized successfully."
    APP_INIT_FAILURE: str = "Initialization failed: %s"

    CONFIG_LOADED: str = "Configuration loaded (environment: %s)."
    CONFIG_ERROR: str = "Failed to load configuration: %s"

    DIR_VERIFIED: str = "Directory verified: %s"
    DIR_CREATED: str = "Directory created: %s"
    DIR_MISSING: str = "Required directory missing and could not be created: %s"

    SPEC_UPLOADED: str = "Specification file uploaded: %s"
    SPEC_PARSE_START: str = "Parsing specification: %s"
    SPEC_PARSE_SUCCESS: str = "Specification parsed successfully (%d endpoints found)."
    SPEC_PARSE_ERROR: str = "Failed to parse specification: %s"

    TEST_RUN_START: str = "Test run started (suite: %s, env: %s)."
    TEST_RUN_COMPLETE: str = "Test run complete: %d passed, %d failed, %d skipped."
    TEST_CASE_PASS: str = "[PASS] %s"
    TEST_CASE_FAIL: str = "[FAIL] %s — %s"
    TEST_CASE_ERROR: str = "[ERROR] %s — %s"
