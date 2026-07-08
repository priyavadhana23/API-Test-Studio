"""
database/repository.py
=======================
Repository classes that hide all SQL from the rest of the application.

Every public method accepts and returns Python objects — never raw SQL
tuples.  The repositories convert between ``Db*`` dataclasses and SQLite
rows in both directions.

Repository classes:
    EnvironmentRepository   — CRUD for environments table
    ExecutionRepository     — CRUD + search for execution_runs
    TestCaseRepository      — bulk insert + lookup for test_case_results
    ValidationRepository    — bulk insert + lookup for validation_details

All repositories receive a ``SQLiteManager`` instance at construction
time (constructor injection) so they are easily testable with a stub.

Rule: No ``import sqlite3`` here. All I/O goes through SQLiteManager.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database.models import (
    DbEnvironment,
    DbExecutionRun,
    DbTestCaseResult,
    DbValidationDetail,
)
from database.sqlite_manager import SQLiteManager
from utilities.common_helpers import generate_id
from utilities.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _dumps(obj: Any) -> Optional[str]:
    """Serialise *obj* to a JSON string, or return None for None."""
    if obj is None:
        return None
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(obj)


def _loads(s: Optional[str]) -> Any:
    """Deserialise a JSON string, falling back to the raw string on error."""
    if s is None:
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return s


# ===========================================================================
# EnvironmentRepository
# ===========================================================================

class EnvironmentRepository:
    """CRUD operations for the ``environments`` table."""

    def __init__(self, db: SQLiteManager) -> None:
        self._db = db

    def upsert(self, env: DbEnvironment) -> None:
        """
        Insert or update an environment record.

        Args:
            env: The ``DbEnvironment`` to persist.
        """
        self._db.execute(
            """
            INSERT INTO environments
                (environment_name, base_url, auth_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(environment_name) DO UPDATE SET
                base_url   = excluded.base_url,
                auth_type  = excluded.auth_type,
                updated_at = excluded.updated_at;
            """,
            (env.environment_name, env.base_url, env.auth_type,
             env.created_at, env.updated_at),
        )
        logger.debug("EnvironmentRepository: upserted '%s'.", env.environment_name)

    def get(self, name: str) -> Optional[DbEnvironment]:
        """
        Return the environment with *name*, or ``None`` if absent.

        Args:
            name: The ``environment_name`` primary key.

        Returns:
            ``DbEnvironment`` or ``None``.
        """
        row = self._db.fetchone(
            "SELECT * FROM environments WHERE environment_name = ?;", (name,)
        )
        if not row:
            return None
        return DbEnvironment(
            environment_name=row["environment_name"],
            base_url=row["base_url"],
            auth_type=row["auth_type"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_all(self) -> List[DbEnvironment]:
        """Return all stored environments."""
        rows = self._db.fetchall("SELECT * FROM environments ORDER BY environment_name;")
        return [
            DbEnvironment(
                environment_name=r["environment_name"],
                base_url=r["base_url"],
                auth_type=r["auth_type"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]


# ===========================================================================
# ExecutionRepository
# ===========================================================================

class ExecutionRepository:
    """CRUD + search operations for the ``execution_runs`` table."""

    def __init__(self, db: SQLiteManager) -> None:
        self._db = db

    def insert(self, run: DbExecutionRun) -> None:
        """
        Persist a new execution run record.

        Args:
            run: Fully populated ``DbExecutionRun``.
        """
        self._db.execute(
            """
            INSERT INTO execution_runs (
                run_id, execution_timestamp, api_name, api_version,
                environment_name, specification_file,
                total_endpoints, total_test_cases, total_executed,
                passed, failed, skipped, errors,
                pass_percentage, avg_response_time_ms, total_execution_time_s,
                framework_version
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);
            """,
            (
                run.run_id, run.execution_timestamp, run.api_name, run.api_version,
                run.environment_name, run.specification_file,
                run.total_endpoints, run.total_test_cases, run.total_executed,
                run.passed, run.failed, run.skipped, run.errors,
                run.pass_percentage, run.avg_response_time_ms,
                run.total_execution_time_s, run.framework_version,
            ),
        )
        logger.debug("ExecutionRepository: inserted run '%s'.", run.run_id)

    def get(self, run_id: str) -> Optional[DbExecutionRun]:
        """Return the run with *run_id*, or ``None``."""
        row = self._db.fetchone(
            "SELECT * FROM execution_runs WHERE run_id = ?;", (run_id,)
        )
        return self._row_to_run(row) if row else None

    def list_all(self, limit: int = 100) -> List[DbExecutionRun]:
        """Return the *limit* most-recent runs, newest first."""
        rows = self._db.fetchall(
            "SELECT * FROM execution_runs ORDER BY execution_timestamp DESC LIMIT ?;",
            (limit,),
        )
        return [self._row_to_run(r) for r in rows]

    def latest(self) -> Optional[DbExecutionRun]:
        """Return the most recently stored run, or ``None``."""
        row = self._db.fetchone(
            "SELECT * FROM execution_runs ORDER BY execution_timestamp DESC LIMIT 1;"
        )
        return self._row_to_run(row) if row else None

    def delete(self, run_id: str) -> bool:
        """
        Delete a run and all its child records (cascaded via Python, not SQL).

        Returns ``True`` if the run existed, ``False`` otherwise.
        """
        row = self.get(run_id)
        if not row:
            return False
        self._db.execute(
            "DELETE FROM validation_details WHERE run_id = ?;", (run_id,)
        )
        self._db.execute(
            "DELETE FROM test_case_results WHERE run_id = ?;", (run_id,)
        )
        self._db.execute(
            "DELETE FROM execution_runs WHERE run_id = ?;", (run_id,)
        )
        logger.info("ExecutionRepository: deleted run '%s'.", run_id)
        return True

    # ── Search / filter ──────────────────────────────────────────────────

    def search(
        self,
        api_name: Optional[str] = None,
        environment: Optional[str] = None,
        status_filter: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
    ) -> List[DbExecutionRun]:
        """
        Search execution runs with optional filters.

        Args:
            api_name:      Partial or exact API name match (case-insensitive).
            environment:   Exact environment name.
            status_filter: Not used at run level; kept for interface consistency.
            date_from:     ISO-8601 lower bound on execution_timestamp.
            date_to:       ISO-8601 upper bound on execution_timestamp.
            limit:         Maximum rows to return.

        Returns:
            List of matching ``DbExecutionRun`` objects.
        """
        clauses: List[str] = []
        params: List[Any] = []

        if api_name:
            clauses.append("LOWER(api_name) LIKE LOWER(?)")
            params.append(f"%{api_name}%")
        if environment:
            clauses.append("environment_name = ?")
            params.append(environment)
        if date_from:
            clauses.append("execution_timestamp >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("execution_timestamp <= ?")
            params.append(date_to)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            f"SELECT * FROM execution_runs {where} "
            f"ORDER BY execution_timestamp DESC LIMIT ?;"
        )
        params.append(limit)
        rows = self._db.fetchall(sql, tuple(params))
        return [self._row_to_run(r) for r in rows]

    # ── Statistics helpers ───────────────────────────────────────────────

    def total_runs(self) -> int:
        return int(self._db.fetchscalar("SELECT COUNT(*) FROM execution_runs;", default=0))

    def average_pass_rate(self) -> float:
        v = self._db.fetchscalar("SELECT AVG(pass_percentage) FROM execution_runs;")
        return float(v) if v is not None else 0.0

    def average_response_time(self) -> Optional[float]:
        v = self._db.fetchscalar("SELECT AVG(avg_response_time_ms) FROM execution_runs;")
        return float(v) if v is not None else None

    def most_executed_api(self) -> Optional[str]:
        row = self._db.fetchone(
            "SELECT api_name, COUNT(*) AS cnt FROM execution_runs "
            "GROUP BY api_name ORDER BY cnt DESC LIMIT 1;"
        )
        return row["api_name"] if row else None

    def latest_execution(self) -> Optional[str]:
        return self._db.fetchscalar(
            "SELECT MAX(execution_timestamp) FROM execution_runs;"
        )

    def oldest_execution(self) -> Optional[str]:
        return self._db.fetchscalar(
            "SELECT MIN(execution_timestamp) FROM execution_runs;"
        )

    # ── Internal ─────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_run(row: Any) -> DbExecutionRun:
        return DbExecutionRun(
            run_id=row["run_id"],
            execution_timestamp=row["execution_timestamp"],
            api_name=row["api_name"],
            api_version=row["api_version"],
            environment_name=row["environment_name"],
            specification_file=row["specification_file"],
            total_endpoints=row["total_endpoints"],
            total_test_cases=row["total_test_cases"],
            total_executed=row["total_executed"],
            passed=row["passed"],
            failed=row["failed"],
            skipped=row["skipped"],
            errors=row["errors"],
            pass_percentage=row["pass_percentage"],
            avg_response_time_ms=row["avg_response_time_ms"],
            total_execution_time_s=row["total_execution_time_s"],
            framework_version=row["framework_version"],
        )


# ===========================================================================
# TestCaseRepository
# ===========================================================================

class TestCaseRepository:
    """Bulk-insert and lookup operations for ``test_case_results``."""

    def __init__(self, db: SQLiteManager) -> None:
        self._db = db

    def insert_many(self, results: List[DbTestCaseResult]) -> None:
        """
        Bulk-insert a list of test-case result records.

        Args:
            results: List of ``DbTestCaseResult`` objects.
        """
        if not results:
            return
        self._db.executemany(
            """
            INSERT OR IGNORE INTO test_case_results (
                result_id, run_id, test_id, operation_id, endpoint, http_method,
                category, request_url, request_headers, request_payload,
                response_status_code, response_headers, response_body,
                response_time_ms, validation_status, failure_reason,
                validation_time_ms, executed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);
            """,
            [
                (
                    r.result_id, r.run_id, r.test_id, r.operation_id,
                    r.endpoint, r.http_method, r.category, r.request_url,
                    r.request_headers, r.request_payload, r.response_status_code,
                    r.response_headers, r.response_body, r.response_time_ms,
                    r.validation_status, r.failure_reason, r.validation_time_ms,
                    r.executed_at,
                )
                for r in results
            ],
        )
        logger.debug(
            "TestCaseRepository: inserted %d result(s) for run.", len(results)
        )

    def get_by_run(self, run_id: str) -> List[DbTestCaseResult]:
        """Return all test-case results for *run_id*."""
        rows = self._db.fetchall(
            "SELECT * FROM test_case_results WHERE run_id = ? "
            "ORDER BY executed_at;",
            (run_id,),
        )
        return [self._row_to_result(r) for r in rows]

    def search(
        self,
        run_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 500,
    ) -> List[DbTestCaseResult]:
        """Search test-case results with optional filters."""
        clauses: List[str] = []
        params: List[Any] = []
        if run_id:
            clauses.append("run_id = ?")
            params.append(run_id)
        if operation_id:
            clauses.append("operation_id = ?")
            params.append(operation_id)
        if endpoint:
            clauses.append("endpoint LIKE ?")
            params.append(f"%{endpoint}%")
        if status:
            clauses.append("validation_status = ?")
            params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM test_case_results {where} LIMIT ?;"
        params.append(limit)
        rows = self._db.fetchall(sql, tuple(params))
        return [self._row_to_result(r) for r in rows]

    def most_failed_endpoint(self) -> Optional[str]:
        """Return the endpoint path with the most failures across all runs."""
        row = self._db.fetchone(
            "SELECT endpoint, COUNT(*) AS cnt FROM test_case_results "
            "WHERE validation_status = 'failed' "
            "GROUP BY endpoint ORDER BY cnt DESC LIMIT 1;"
        )
        return row["endpoint"] if row else None

    def count_by_run(self, run_id: str) -> int:
        return int(
            self._db.fetchscalar(
                "SELECT COUNT(*) FROM test_case_results WHERE run_id = ?;",
                (run_id,), default=0,
            )
        )

    @staticmethod
    def _row_to_result(row: Any) -> DbTestCaseResult:
        return DbTestCaseResult(
            result_id=row["result_id"],
            run_id=row["run_id"],
            test_id=row["test_id"],
            operation_id=row["operation_id"],
            endpoint=row["endpoint"],
            http_method=row["http_method"],
            category=row["category"],
            request_url=row["request_url"],
            request_headers=row["request_headers"],
            request_payload=row["request_payload"],
            response_status_code=row["response_status_code"],
            response_headers=row["response_headers"],
            response_body=row["response_body"],
            response_time_ms=row["response_time_ms"],
            validation_status=row["validation_status"],
            failure_reason=row["failure_reason"],
            validation_time_ms=row["validation_time_ms"],
            executed_at=row["executed_at"],
        )


# ===========================================================================
# ValidationRepository
# ===========================================================================

class ValidationRepository:
    """Bulk-insert and lookup for ``validation_details``."""

    def __init__(self, db: SQLiteManager) -> None:
        self._db = db

    def insert_many(self, details: List[DbValidationDetail]) -> None:
        """Bulk-insert validation detail records."""
        if not details:
            return
        self._db.executemany(
            """
            INSERT OR IGNORE INTO validation_details (
                validation_detail_id, result_id, run_id,
                validator_name, status, message, severity,
                execution_time_ms, recorded_at
            ) VALUES (?,?,?,?,?,?,?,?,?);
            """,
            [
                (
                    d.validation_detail_id, d.result_id, d.run_id,
                    d.validator_name, d.status, d.message, d.severity,
                    d.execution_time_ms, d.recorded_at,
                )
                for d in details
            ],
        )
        logger.debug(
            "ValidationRepository: inserted %d detail(s).", len(details)
        )

    def get_by_result(self, result_id: str) -> List[DbValidationDetail]:
        """Return all validation detail records for *result_id*."""
        rows = self._db.fetchall(
            "SELECT * FROM validation_details WHERE result_id = ?;",
            (result_id,),
        )
        return [self._row_to_detail(r) for r in rows]

    def get_by_run(self, run_id: str) -> List[DbValidationDetail]:
        """Return all validation detail records for *run_id*."""
        rows = self._db.fetchall(
            "SELECT * FROM validation_details WHERE run_id = ?;",
            (run_id,),
        )
        return [self._row_to_detail(r) for r in rows]

    def count_by_run(self, run_id: str) -> int:
        return int(
            self._db.fetchscalar(
                "SELECT COUNT(*) FROM validation_details WHERE run_id = ?;",
                (run_id,), default=0,
            )
        )

    @staticmethod
    def _row_to_detail(row: Any) -> DbValidationDetail:
        return DbValidationDetail(
            validation_detail_id=row["validation_detail_id"],
            result_id=row["result_id"],
            run_id=row["run_id"],
            validator_name=row["validator_name"],
            status=row["status"],
            message=row["message"],
            severity=row["severity"],
            execution_time_ms=row["execution_time_ms"],
            recorded_at=row["recorded_at"],
        )
