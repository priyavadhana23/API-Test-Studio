"""
database/migrations.py
=======================
Schema version tracking and incremental migration support.

Design:
    - Each migration is a (version: int, description: str, sql: str) tuple.
    - ``apply_migrations()`` is idempotent — already-applied versions are skipped.
    - The ``schema_version`` table records what has been applied.
    - Future changes only require adding a new entry to ``MIGRATIONS`` — no
      existing code needs modification.

Adding a migration (example for a future Phase 7 column):
    MIGRATIONS.append(Migration(
        version=2,
        description="Add report_path column to execution_runs",
        sql="ALTER TABLE execution_runs ADD COLUMN report_path TEXT;",
    ))
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from utilities.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Migration:
    """
    Represents a single schema migration.

    Attributes:
        version:     Monotonically increasing integer version number.
        description: Human-readable description of the change.
        sql:         The SQL statement(s) to execute (semicolon-separated).
    """
    version: int
    description: str
    sql: str


# ---------------------------------------------------------------------------
# Registered migrations
# Version 1 is the initial schema — handled by schema.py DDL.
# Start additional migrations from version 2.
# ---------------------------------------------------------------------------

MIGRATIONS: List[Migration] = [
    # Version 1 is the baseline — tables created by schema.py in SQLiteManager.
    # No SQL needed here for version 1; it is recorded automatically after
    # initial table creation.
]


def apply_migrations(connection) -> None:
    """
    Apply any pending migrations to the database.

    Checks the ``schema_version`` table for already-applied versions and
    runs only the ones that are missing.  Runs each migration in its own
    transaction so a failure does not corrupt the database.

    Args:
        connection: An open ``sqlite3.Connection`` instance.

    Raises:
        Exception: If a migration SQL statement fails (transaction rolled back).
    """
    cursor = connection.cursor()

    # Ensure schema_version table exists (it was created by schema.py)
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version';"
    )
    if not cursor.fetchone():
        logger.warning("migrations: schema_version table not found — skipping.")
        return

    # Determine highest applied version
    cursor.execute("SELECT MAX(version) FROM schema_version;")
    row = cursor.fetchone()
    current_version: int = row[0] if row and row[0] is not None else 0

    pending = [m for m in MIGRATIONS if m.version > current_version]
    if not pending:
        logger.debug("migrations: schema is up to date (version %d).", current_version)
        return

    logger.info(
        "migrations: %d pending migration(s) to apply.", len(pending)
    )

    for migration in sorted(pending, key=lambda m: m.version):
        logger.info(
            "migrations: applying v%d — %s", migration.version, migration.description
        )
        try:
            for statement in migration.sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    cursor.execute(stmt)

            now = datetime.now(tz=timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO schema_version (version, description, applied_at) "
                "VALUES (?, ?, ?);",
                (migration.version, migration.description, now),
            )
            connection.commit()
            logger.info(
                "migrations: v%d applied successfully.", migration.version
            )
        except Exception as exc:
            connection.rollback()
            logger.error(
                "migrations: v%d FAILED — rolled back. Error: %s",
                migration.version, exc,
            )
            raise


def record_baseline(connection) -> None:
    """
    Record version 1 (baseline schema) in schema_version if not present.

    Called by SQLiteManager after the initial table creation so the
    migration history starts clean.

    Args:
        connection: An open ``sqlite3.Connection`` instance.
    """
    cursor = connection.cursor()
    cursor.execute("SELECT version FROM schema_version WHERE version = 1;")
    if not cursor.fetchone():
        now = datetime.now(tz=timezone.utc).isoformat()
        cursor.execute(
            "INSERT INTO schema_version (version, description, applied_at) "
            "VALUES (1, 'Initial schema', ?);",
            (now,),
        )
        connection.commit()
        logger.debug("migrations: baseline version 1 recorded.")
