"""
database package
=================
Phase 6 — Persistence and Execution History Layer for API Test Studio.

Public API (the only import the rest of the framework needs):

    from database import DatabaseManager

    with DatabaseManager() as db:
        run_id = db.save_run(spec, test_cases, exec_results, val_results, cfg)
        runs   = db.list_runs()
        stats  = db.statistics()

Internal modules (not for direct use outside this package):

    schema          — All DDL (CREATE TABLE) statements
    migrations      — Schema version tracking and incremental migration runner
    models          — Db* dataclasses mirroring each database table row
    sqlite_manager  — Low-level SQLite connection, execute/fetch helpers
    repository      — EnvironmentRepository, ExecutionRepository,
                      TestCaseRepository, ValidationRepository

Extension point for future databases:
    Replace SQLiteManager with PostgresManager / MySQLManager that expose
    the same interface.  DatabaseManager never imports sqlite3 directly.
"""

from database.database_manager import DatabaseManager

__all__ = ["DatabaseManager"]
