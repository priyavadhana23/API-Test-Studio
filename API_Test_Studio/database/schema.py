"""
database/schema.py
===================
All DDL (CREATE TABLE) statements for the API Test Studio database.

Design principles:
    - All SQL lives here and only here — repositories import these constants.
    - No business logic, no Python objects — pure SQL strings.
    - Schema version is tracked in the ``schema_version`` table so future
      migrations can check what's already applied.
    - Designed for SQLite today; compatible with PostgreSQL / MySQL with
      minimal column-type substitution (TEXT → VARCHAR, INTEGER → SERIAL, etc.).

Table relationships:
    environments       ←──┐
    execution_runs     ────┤ (environment_name FK)
         │                │
         └── test_case_results ── validation_details
"""

# ---------------------------------------------------------------------------
# Schema version tracking
# ---------------------------------------------------------------------------

CREATE_SCHEMA_VERSION_TABLE: str = """
CREATE TABLE IF NOT EXISTS schema_version (
    version         INTEGER PRIMARY KEY,
    description     TEXT    NOT NULL,
    applied_at      TEXT    NOT NULL   -- ISO-8601 UTC timestamp
);
"""

# ---------------------------------------------------------------------------
# Environments
# ---------------------------------------------------------------------------

CREATE_ENVIRONMENTS_TABLE: str = """
CREATE TABLE IF NOT EXISTS environments (
    environment_name  TEXT PRIMARY KEY,
    base_url          TEXT,
    auth_type         TEXT    NOT NULL DEFAULT 'none',
    created_at        TEXT    NOT NULL,   -- ISO-8601 UTC
    updated_at        TEXT    NOT NULL    -- ISO-8601 UTC
);
"""

# ---------------------------------------------------------------------------
# Execution runs  (one row per ParserManager → GeneratorManager → ExecutionManager cycle)
# ---------------------------------------------------------------------------

CREATE_EXECUTION_RUNS_TABLE: str = """
CREATE TABLE IF NOT EXISTS execution_runs (
    run_id                TEXT PRIMARY KEY,
    execution_timestamp   TEXT NOT NULL,   -- ISO-8601 UTC
    api_name              TEXT NOT NULL,
    api_version           TEXT,
    environment_name      TEXT,
    specification_file    TEXT,
    total_endpoints       INTEGER NOT NULL DEFAULT 0,
    total_test_cases      INTEGER NOT NULL DEFAULT 0,
    total_executed        INTEGER NOT NULL DEFAULT 0,
    passed                INTEGER NOT NULL DEFAULT 0,
    failed                INTEGER NOT NULL DEFAULT 0,
    skipped               INTEGER NOT NULL DEFAULT 0,
    errors                INTEGER NOT NULL DEFAULT 0,
    pass_percentage       REAL    NOT NULL DEFAULT 0.0,
    avg_response_time_ms  REAL,
    total_execution_time_s REAL,
    framework_version     TEXT,
    FOREIGN KEY (environment_name) REFERENCES environments(environment_name)
);
"""

# ---------------------------------------------------------------------------
# Test case results  (one row per TestCase × ExecutionResult × ValidationResult)
# ---------------------------------------------------------------------------

CREATE_TEST_CASE_RESULTS_TABLE: str = """
CREATE TABLE IF NOT EXISTS test_case_results (
    result_id             TEXT PRIMARY KEY,
    run_id                TEXT NOT NULL,
    test_id               TEXT NOT NULL,
    operation_id          TEXT,
    endpoint              TEXT NOT NULL,   -- URL path template
    http_method           TEXT NOT NULL,
    category              TEXT,            -- positive / negative / boundary / security
    request_url           TEXT,
    request_headers       TEXT,            -- JSON-encoded dict
    request_payload       TEXT,            -- JSON-encoded body
    response_status_code  INTEGER,
    response_headers      TEXT,            -- JSON-encoded dict
    response_body         TEXT,            -- JSON-encoded or raw string
    response_time_ms      REAL,
    validation_status     TEXT,            -- passed / failed / error / skipped
    failure_reason        TEXT,            -- first failure message, if any
    validation_time_ms    REAL,
    executed_at           TEXT,            -- ISO-8601 UTC
    FOREIGN KEY (run_id) REFERENCES execution_runs(run_id)
);
"""

# ---------------------------------------------------------------------------
# Validation details  (one row per validator that ran for a test case result)
# ---------------------------------------------------------------------------

CREATE_VALIDATION_DETAILS_TABLE: str = """
CREATE TABLE IF NOT EXISTS validation_details (
    validation_detail_id  TEXT PRIMARY KEY,
    result_id             TEXT NOT NULL,
    run_id                TEXT NOT NULL,
    validator_name        TEXT NOT NULL,
    status                TEXT NOT NULL,   -- passed / failed
    message               TEXT,
    severity              TEXT,
    execution_time_ms     REAL,
    recorded_at           TEXT NOT NULL,   -- ISO-8601 UTC
    FOREIGN KEY (result_id) REFERENCES test_case_results(result_id),
    FOREIGN KEY (run_id)    REFERENCES execution_runs(run_id)
);
"""

# ---------------------------------------------------------------------------
# Indexes for fast lookup
# ---------------------------------------------------------------------------

CREATE_INDEXES: list = [
    "CREATE INDEX IF NOT EXISTS idx_tcr_run_id    ON test_case_results(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_tcr_test_id   ON test_case_results(test_id);",
    "CREATE INDEX IF NOT EXISTS idx_tcr_op_id     ON test_case_results(operation_id);",
    "CREATE INDEX IF NOT EXISTS idx_tcr_endpoint  ON test_case_results(endpoint);",
    "CREATE INDEX IF NOT EXISTS idx_tcr_status    ON test_case_results(validation_status);",
    "CREATE INDEX IF NOT EXISTS idx_vd_result_id  ON validation_details(result_id);",
    "CREATE INDEX IF NOT EXISTS idx_vd_run_id     ON validation_details(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_er_api_name   ON execution_runs(api_name);",
    "CREATE INDEX IF NOT EXISTS idx_er_timestamp  ON execution_runs(execution_timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_er_env        ON execution_runs(environment_name);",
]

# All DDL statements in creation order
ALL_DDL: list = [
    CREATE_SCHEMA_VERSION_TABLE,
    CREATE_ENVIRONMENTS_TABLE,
    CREATE_EXECUTION_RUNS_TABLE,
    CREATE_TEST_CASE_RESULTS_TABLE,
    CREATE_VALIDATION_DETAILS_TABLE,
    *CREATE_INDEXES,
]
