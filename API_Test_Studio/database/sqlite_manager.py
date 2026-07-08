"""
database/sqlite_manager.py
============================
Low-level SQLite connection manager.

Responsibilities:
    - Open and configure the SQLite connection (WAL mode, foreign keys, etc.)
    - Create all tables on first run
    - Apply pending migrations
    - Provide execute / executemany / fetchone / fetchall helpers
    - Manage transactions (commit / rollback)
    - Support context-manager usage

This class is the ONLY place in the project that imports ``sqlite3``.
All other database code calls this class so the underlying driver can
be swapped for psycopg2, pymysql, etc. with a single replacement.

Extension for PostgreSQL / MySQL (Phase 8+):
    Create ``PostgresManager`` with the same public interface as
    ``SQLiteManager``.  ``DatabaseManager`` accepts any object that
    satisfies the interface — no callers change.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from database.migrations import apply_migrations, record_baseline
from database.schema import ALL_DDL
from utilities.logger import get_logger

logger = get_logger(__name__)


class SQLiteManager:
    """
    Thread-safe SQLite connection wrapper for API Test Studio.

    Designed for single-threaded sequential writes (the framework's normal
    operation mode).  For concurrent access in a future web server phase,
    set ``check_same_thread=False`` and add a threading.Lock around writes.

    Args:
        db_path: Absolute or relative path to the ``.db`` file.
                 The parent directory is created if it does not exist.

    Usage (context manager — preferred)::

        with SQLiteManager("database/ats.db") as db:
            db.execute("INSERT INTO …", (…,))

    Usage (manual)::

        db = SQLiteManager("database/ats.db")
        db.connect()
        db.execute("SELECT …")
        db.close()
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        logger.debug("SQLiteManager created for: %s", self._db_path)

    # ------------------------------------------------------------------ #
    # Connection lifecycle
    # ------------------------------------------------------------------ #

    def connect(self) -> None:
        """
        Open the database connection, create tables, and run migrations.

        The parent directory is created automatically if absent.
        Called automatically by ``__enter__``.
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=True,
        )
        self._conn.row_factory = sqlite3.Row   # rows accessible by column name

        # Performance and safety settings
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA synchronous = NORMAL;")

        self._create_schema()
        apply_migrations(self._conn)
        logger.info("SQLiteManager: connected to '%s'.", self._db_path.name)

    def close(self) -> None:
        """Commit any pending transaction and close the connection."""
        if self._conn:
            try:
                self._conn.commit()
            except Exception:
                pass
            self._conn.close()
            self._conn = None
            logger.debug("SQLiteManager: connection closed.")

    def _create_schema(self) -> None:
        """Execute all DDL statements and record the baseline migration."""
        assert self._conn is not None
        cursor = self._conn.cursor()
        for ddl in ALL_DDL:
            cursor.execute(ddl)
        self._conn.commit()
        record_baseline(self._conn)
        logger.debug("SQLiteManager: schema verified / created.")

    # ------------------------------------------------------------------ #
    # Query helpers
    # ------------------------------------------------------------------ #

    def execute(
        self,
        sql: str,
        params: Tuple[Any, ...] = (),
    ) -> sqlite3.Cursor:
        """
        Execute a single SQL statement.

        Args:
            sql:    SQL string with ``?`` placeholders.
            params: Tuple of bind parameters.

        Returns:
            The ``sqlite3.Cursor`` for the executed statement.

        Raises:
            RuntimeError: If called before ``connect()``.
        """
        self._assert_connected()
        cursor = self._conn.cursor()  # type: ignore[union-attr]
        cursor.execute(sql, params)
        return cursor

    def executemany(
        self,
        sql: str,
        params_seq: Iterable[Tuple[Any, ...]],
    ) -> sqlite3.Cursor:
        """
        Execute a SQL statement once per item in *params_seq*.

        Args:
            sql:        SQL string with ``?`` placeholders.
            params_seq: Iterable of parameter tuples.

        Returns:
            The ``sqlite3.Cursor``.
        """
        self._assert_connected()
        cursor = self._conn.cursor()  # type: ignore[union-attr]
        cursor.executemany(sql, params_seq)
        return cursor

    def fetchone(
        self,
        sql: str,
        params: Tuple[Any, ...] = (),
    ) -> Optional[sqlite3.Row]:
        """
        Execute *sql* and return the first row, or ``None``.

        Args:
            sql:    SELECT statement.
            params: Bind parameters.

        Returns:
            ``sqlite3.Row`` (dict-like) or ``None``.
        """
        return self.execute(sql, params).fetchone()

    def fetchall(
        self,
        sql: str,
        params: Tuple[Any, ...] = (),
    ) -> List[sqlite3.Row]:
        """
        Execute *sql* and return all rows.

        Args:
            sql:    SELECT statement.
            params: Bind parameters.

        Returns:
            List of ``sqlite3.Row`` objects.
        """
        return self.execute(sql, params).fetchall()

    def fetchscalar(
        self,
        sql: str,
        params: Tuple[Any, ...] = (),
        default: Any = None,
    ) -> Any:
        """
        Execute *sql* and return the first column of the first row.

        Useful for ``SELECT COUNT(*)``, ``SELECT MAX(…)``, etc.

        Args:
            sql:     SQL query.
            params:  Bind parameters.
            default: Value returned when no rows match.

        Returns:
            Scalar value or *default*.
        """
        row = self.fetchone(sql, params)
        if row is None:
            return default
        return row[0]

    # ------------------------------------------------------------------ #
    # Transaction management
    # ------------------------------------------------------------------ #

    def commit(self) -> None:
        """Commit the current transaction."""
        self._assert_connected()
        self._conn.commit()  # type: ignore[union-attr]
        logger.debug("SQLiteManager: committed.")

    def rollback(self) -> None:
        """Roll back the current transaction."""
        self._assert_connected()
        self._conn.rollback()  # type: ignore[union-attr]
        logger.warning("SQLiteManager: rolled back.")

    def db_size_bytes(self) -> int:
        """Return the current size of the database file in bytes."""
        try:
            return self._db_path.stat().st_size
        except FileNotFoundError:
            return 0

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _assert_connected(self) -> None:
        if self._conn is None:
            raise RuntimeError(
                "SQLiteManager is not connected. Call connect() or use as a context manager."
            )

    # ------------------------------------------------------------------ #
    # Context-manager support
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "SQLiteManager":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
