"""
database/database_manager.py
==============================
Public facade for the entire Phase 6 persistence layer.

``DatabaseManager`` is the ONLY class the rest of the framework calls.
No external code should directly instantiate SQLiteManager, repositories,
or execute SQL of any kind.

Responsibilities:
    - initialise the database (create tables, run migrations)
    - convert Phase 2-5 domain objects → Db* row objects → SQL
    - save a complete execution run (run + test results + validation details + environment)
    - retrieve, list, search, compare, and delete runs
    - compute statistics across all stored runs
    - export a run's data to JSON or CSV in the history/ directory
    - print a structured persistence summary through the logger

Extension for future databases:
    Replace ``SQLiteManager`` with ``PostgresManager`` or ``MySQLManager``
    that expose the same interface (execute / fetchone / fetchall / etc.).
    ``DatabaseManager`` never imports sqlite3 directly — the swap is
    transparent to all callers.
"""

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from constants.app_constants import AppMeta
from database.models import (
    DbEnvironment,
    DbExecutionRun,
    DbTestCaseResult,
    DbValidationDetail,
    RunComparison,
)
from database.repository import (
    EnvironmentRepository,
    ExecutionRepository,
    TestCaseRepository,
    ValidationRepository,
)
from database.sqlite_manager import SQLiteManager
from utilities.common_helpers import generate_id
from utilities.logger import get_logger

logger = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _dumps(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(obj)


class DatabaseManager:
    """
    Single public interface to the API Test Studio persistence layer.

    Args:
        db_path:      Path to the SQLite database file.
                      Defaults to ``database/api_test_studio.db`` relative
                      to the project root.
        history_dir:  Directory where JSON/CSV exports are written.
                      Defaults to ``history/`` relative to the project root.

    Usage::

        mgr = DatabaseManager()
        mgr.init_db()
        run_id = mgr.save_run(spec, test_cases, exec_results, val_results, cfg)
        print(mgr.get_run(run_id))
    """

    def __init__(
        self,
        db_path: str = "database/api_test_studio.db",
        history_dir: str = "history",
    ) -> None:
        self._db_path    = db_path
        self._history_dir = Path(history_dir)
        self._db: Optional[SQLiteManager] = None

        # Repositories — initialised after connect()
        self._env_repo:  Optional[EnvironmentRepository]  = None
        self._run_repo:  Optional[ExecutionRepository]    = None
        self._tc_repo:   Optional[TestCaseRepository]     = None
        self._val_repo:  Optional[ValidationRepository]   = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def init_db(self) -> None:
        """
        Open the database, create tables, apply migrations, wire repositories.

        Safe to call multiple times — subsequent calls are no-ops if already
        connected.
        """
        if self._db is not None:
            return

        self._history_dir.mkdir(parents=True, exist_ok=True)
        self._db = SQLiteManager(self._db_path)
        self._db.connect()

        self._env_repo  = EnvironmentRepository(self._db)
        self._run_repo  = ExecutionRepository(self._db)
        self._tc_repo   = TestCaseRepository(self._db)
        self._val_repo  = ValidationRepository(self._db)

        logger.info(
            "DatabaseManager: initialised — '%s'.",
            Path(self._db_path).name,
        )

    def close(self) -> None:
        """Commit and close the database connection."""
        if self._db:
            self._db.close()
            self._db = None
            logger.info("DatabaseManager: connection closed.")

    def __enter__(self) -> "DatabaseManager":
        self.init_db()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Save a complete run (the main Phase 6 entry point)
    # ------------------------------------------------------------------ #

    def save_run(
        self,
        spec: Any,               # ApiSpec
        test_cases: List[Any],   # List[TestCase]
        exec_results: List[Any], # List[ExecutionResult]
        val_results: List[Any],  # List[ValidationResult]
        config: Any,             # Config
        total_execution_time_s: float = 0.0,
    ) -> str:
        """
        Persist one complete execution run and return its run_id.

        Steps:
            1. Upsert the environment record.
            2. Compute run-level aggregates.
            3. Insert the ``execution_runs`` row.
            4. Build and bulk-insert ``test_case_results`` rows.
            5. Build and bulk-insert ``validation_details`` rows.
            6. Commit.

        Args:
            spec:                   The parsed ``ApiSpec`` object.
            test_cases:             Generated ``TestCase`` list.
            exec_results:           ``ExecutionResult`` list from Phase 4.
            val_results:            ``ValidationResult`` list from Phase 5.
            config:                 Loaded ``Config`` instance.
            total_execution_time_s: Wall-clock time for the full run (s).

        Returns:
            The ``run_id`` string of the newly created record.
        """
        self._assert_init()
        t_start = time.monotonic()

        env = config.active_environment
        now = _now_iso()

        # ── 1. Upsert environment ──────────────────────────────────────
        self._env_repo.upsert(DbEnvironment(       # type: ignore[union-attr]
            environment_name=env.name,
            base_url=env.base_url,
            auth_type=env.auth_type,
            created_at=now,
            updated_at=now,
        ))

        # ── 2. Aggregate run-level stats ───────────────────────────────
        total   = len(val_results)
        passed  = sum(1 for v in val_results if v.overall_status == "passed")
        failed  = sum(1 for v in val_results if v.overall_status == "failed")
        skipped = sum(1 for v in val_results if v.overall_status == "skipped")
        errors  = sum(1 for v in val_results if v.overall_status == "error")
        pass_pct = (passed / total * 100.0) if total else 0.0

        times = [
            e.response_time_ms for e in exec_results
            if e.response_time_ms is not None
        ]
        avg_rt = sum(times) / len(times) if times else None

        # Use Phase 4's run_id if available, else generate a fresh one
        run_id = exec_results[0].run_id if exec_results else generate_id("run_")

        db_run = DbExecutionRun(
            run_id=run_id,
            execution_timestamp=now,
            api_name=spec.title,
            api_version=spec.version,
            environment_name=env.name,
            specification_file=str(Path(spec.source_file).name),
            total_endpoints=spec.endpoint_count,
            total_test_cases=len(test_cases),
            total_executed=len(exec_results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            pass_percentage=round(pass_pct, 2),
            avg_response_time_ms=round(avg_rt, 3) if avg_rt else None,
            total_execution_time_s=round(total_execution_time_s, 3),
            framework_version=AppMeta.VERSION,
        )
        self._run_repo.insert(db_run)              # type: ignore[union-attr]

        # ── 3. Build test-case result rows ─────────────────────────────
        # Build lookup maps for O(1) access
        tc_by_id  = {tc.test_id: tc for tc in test_cases}
        er_by_tid = {er.test_id: er for er in exec_results}

        tc_rows: List[DbTestCaseResult] = []
        for vr in val_results:
            tc  = tc_by_id.get(vr.test_id)
            er  = er_by_tid.get(vr.test_id)
            if not tc or not er:
                continue

            # Pick first tag that looks like a category
            _CAT_TAGS = {"positive","negative","boundary","security",
                         "enum","auth","header","method","query_param",
                         "path_param","request_body","null","empty","datatype"}
            category = next((t for t in tc.tags if t in _CAT_TAGS), None)

            tc_rows.append(DbTestCaseResult(
                result_id=er.result_id,
                run_id=run_id,
                test_id=tc.test_id,
                operation_id=vr.operation_id or "",
                endpoint=tc.path,
                http_method=tc.method,
                category=category,
                request_url=er.request_url,
                request_headers=_dumps(er.request_headers),
                request_payload=_dumps(er.request_body),
                response_status_code=er.http_status_code,
                response_headers=_dumps(er.response_headers),
                response_body=_dumps(er.response_body)
                    if not isinstance(er.response_body, str)
                    else (er.response_body[:2000] if er.response_body else None),
                response_time_ms=er.response_time_ms,
                validation_status=vr.overall_status,
                failure_reason=vr.failure_messages[0][:500]
                    if vr.failure_messages else None,
                validation_time_ms=vr.validation_time_ms,
                executed_at=er.executed_at.isoformat()
                    if er.executed_at else now,
            ))

        self._tc_repo.insert_many(tc_rows)         # type: ignore[union-attr]

        # ── 4. Build validation detail rows ───────────────────────────
        val_rows: List[DbValidationDetail] = []
        er_by_rid = {er.result_id: er for er in exec_results}

        for vr in val_results:
            er = er_by_tid.get(vr.test_id)
            if not er:
                continue
            result_id = er.result_id
            recorded  = _now_iso()

            for vname in vr.passed_validators:
                val_rows.append(DbValidationDetail(
                    validation_detail_id=generate_id("vd_"),
                    result_id=result_id,
                    run_id=run_id,
                    validator_name=vname,
                    status="passed",
                    message=None,
                    severity=vr.severity,
                    execution_time_ms=None,
                    recorded_at=recorded,
                ))
            for vname in vr.failed_validators:
                msg = next(
                    (m for m in vr.failure_messages if m),
                    None,
                )
                val_rows.append(DbValidationDetail(
                    validation_detail_id=generate_id("vd_"),
                    result_id=result_id,
                    run_id=run_id,
                    validator_name=vname,
                    status="failed",
                    message=msg[:500] if msg else None,
                    severity=vr.severity,
                    execution_time_ms=None,
                    recorded_at=recorded,
                ))

        self._val_repo.insert_many(val_rows)       # type: ignore[union-attr]

        # ── 5. Commit ─────────────────────────────────────────────────
        self._db.commit()                          # type: ignore[union-attr]
        elapsed = time.monotonic() - t_start

        logger.info(
            "DatabaseManager: run '%s' saved — %d tc results, "
            "%d validation details in %.2fs.",
            run_id, len(tc_rows), len(val_rows), elapsed,
        )
        self._print_persistence_summary(
            run_id, db_run, len(tc_rows), len(val_rows), elapsed,
        )
        return run_id

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #

    def get_run(self, run_id: str) -> Optional[DbExecutionRun]:
        """Return the ``DbExecutionRun`` for *run_id*, or ``None``."""
        self._assert_init()
        return self._run_repo.get(run_id)          # type: ignore[union-attr]

    def list_runs(self, limit: int = 50) -> List[DbExecutionRun]:
        """Return the *limit* most-recent runs, newest first."""
        self._assert_init()
        return self._run_repo.list_all(limit)      # type: ignore[union-attr]

    def latest_run(self) -> Optional[DbExecutionRun]:
        """Return the most recently stored run."""
        self._assert_init()
        return self._run_repo.latest()             # type: ignore[union-attr]

    def delete_run(self, run_id: str) -> bool:
        """Delete a run and all its child records."""
        self._assert_init()
        ok = self._run_repo.delete(run_id)         # type: ignore[union-attr]
        if ok:
            self._db.commit()                      # type: ignore[union-attr]
        return ok

    def get_test_results(self, run_id: str) -> List[DbTestCaseResult]:
        """Return all test-case results for *run_id*."""
        self._assert_init()
        return self._tc_repo.get_by_run(run_id)    # type: ignore[union-attr]

    def get_validation_details(self, run_id: str) -> List[DbValidationDetail]:
        """Return all validation detail rows for *run_id*."""
        self._assert_init()
        return self._val_repo.get_by_run(run_id)   # type: ignore[union-attr]

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def search_runs(
        self,
        api_name: Optional[str] = None,
        environment: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
    ) -> List[DbExecutionRun]:
        """Search execution runs by API name, environment, or date range."""
        self._assert_init()
        return self._run_repo.search(               # type: ignore[union-attr]
            api_name=api_name,
            environment=environment,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

    def search_test_results(
        self,
        run_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 500,
    ) -> List[DbTestCaseResult]:
        """Search test-case results with optional filters."""
        self._assert_init()
        return self._tc_repo.search(                # type: ignore[union-attr]
            run_id=run_id,
            operation_id=operation_id,
            endpoint=endpoint,
            status=status,
            limit=limit,
        )

    # ------------------------------------------------------------------ #
    # Run comparison
    # ------------------------------------------------------------------ #

    def compare_runs(
        self, run_id_a: str, run_id_b: str
    ) -> Optional[RunComparison]:
        """
        Compare two execution runs and return a ``RunComparison`` object.

        Args:
            run_id_a: The baseline (older) run ID.
            run_id_b: The comparison (newer) run ID.

        Returns:
            ``RunComparison`` or ``None`` if either run is not found.
        """
        self._assert_init()
        a = self._run_repo.get(run_id_a)           # type: ignore[union-attr]
        b = self._run_repo.get(run_id_b)           # type: ignore[union-attr]
        if not a or not b:
            logger.warning(
                "compare_runs: one or both run IDs not found (%s, %s).",
                run_id_a, run_id_b,
            )
            return None

        avg_a = a.avg_response_time_ms
        avg_b = b.avg_response_time_ms
        avg_delta = (avg_b - avg_a) if (avg_a is not None and avg_b is not None) else None

        cmp = RunComparison(
            run_id_a=run_id_a,
            run_id_b=run_id_b,
            api_name=a.api_name,
            passed_a=a.passed,        passed_b=b.passed,
            passed_delta=b.passed - a.passed,
            failed_a=a.failed,        failed_b=b.failed,
            failed_delta=b.failed - a.failed,
            errors_a=a.errors,        errors_b=b.errors,
            errors_delta=b.errors - a.errors,
            pass_pct_a=a.pass_percentage, pass_pct_b=b.pass_percentage,
            pass_pct_delta=round(b.pass_percentage - a.pass_percentage, 2),
            avg_rt_a=avg_a, avg_rt_b=avg_b,
            avg_rt_delta=round(avg_delta, 2) if avg_delta is not None else None,
        )
        logger.info("compare_runs: %s", cmp.summary())
        return cmp

    # ------------------------------------------------------------------ #
    # Statistics
    # ------------------------------------------------------------------ #

    def statistics(self) -> Dict[str, Any]:
        """
        Return a summary statistics dictionary across all stored runs.

        Returns:
            Dict with keys: total_runs, average_pass_rate,
            average_response_time_ms, most_executed_api,
            most_failed_endpoint, latest_execution, oldest_execution.
        """
        self._assert_init()
        return {
            "total_runs":              self._run_repo.total_runs(),    # type: ignore
            "average_pass_rate":       round(self._run_repo.average_pass_rate(), 2),  # type: ignore
            "average_response_time_ms": self._run_repo.average_response_time(),     # type: ignore
            "most_executed_api":       self._run_repo.most_executed_api(),           # type: ignore
            "most_failed_endpoint":    self._tc_repo.most_failed_endpoint(),         # type: ignore
            "latest_execution":        self._run_repo.latest_execution(),            # type: ignore
            "oldest_execution":        self._run_repo.oldest_execution(),            # type: ignore
        }

    def db_size_kb(self) -> float:
        """Return the SQLite file size in kilobytes."""
        if self._db:
            return round(self._db.db_size_bytes() / 1024, 2)
        return 0.0

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #

    def export_run_json(self, run_id: str) -> Optional[Path]:
        """
        Export one run (with all test results) to a JSON file in history/.

        Args:
            run_id: The run to export.

        Returns:
            Path to the written file, or ``None`` if the run was not found.
        """
        self._assert_init()
        run = self._run_repo.get(run_id)           # type: ignore[union-attr]
        if not run:
            logger.warning("export_run_json: run '%s' not found.", run_id)
            return None

        tc_results  = self._tc_repo.get_by_run(run_id)   # type: ignore
        val_details = self._val_repo.get_by_run(run_id)  # type: ignore

        payload = {
            "run":               vars(run),
            "test_case_results": [vars(r) for r in tc_results],
            "validation_details": [vars(d) for d in val_details],
            "exported_at":       _now_iso(),
        }

        filename = self._history_dir / f"run_{run_id[:8]}_{run.api_name.replace(' ', '_')}.json"
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text(
            json.dumps(payload, default=str, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("DatabaseManager: exported run '%s' → %s", run_id[:8], filename.name)
        return filename

    def export_run_csv(self, run_id: str) -> Optional[Path]:
        """
        Export test-case results for one run to a CSV file in history/.

        Args:
            run_id: The run to export.

        Returns:
            Path to the written file, or ``None`` if the run was not found.
        """
        self._assert_init()
        run = self._run_repo.get(run_id)           # type: ignore[union-attr]
        if not run:
            logger.warning("export_run_csv: run '%s' not found.", run_id)
            return None

        tc_results = self._tc_repo.get_by_run(run_id)   # type: ignore

        filename = self._history_dir / f"run_{run_id[:8]}_{run.api_name.replace(' ', '_')}.csv"
        filename.parent.mkdir(parents=True, exist_ok=True)

        fields = [
            "result_id", "run_id", "test_id", "operation_id", "endpoint",
            "http_method", "category", "request_url",
            "response_status_code", "response_time_ms",
            "validation_status", "failure_reason", "validation_time_ms",
            "executed_at",
        ]

        with open(filename, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for r in tc_results:
                writer.writerow({f: getattr(r, f, "") for f in fields})

        logger.info("DatabaseManager: exported CSV '%s' — %d rows.", filename.name, len(tc_results))
        return filename

    # ------------------------------------------------------------------ #
    # Persistence summary
    # ------------------------------------------------------------------ #

    def _print_persistence_summary(
        self,
        run_id: str,
        run: DbExecutionRun,
        tc_count: int,
        val_count: int,
        elapsed: float,
    ) -> None:
        """Emit a structured persistence summary through the logger."""
        wide = "=" * 52
        logger.info(wide)
        logger.info("  PERSISTENCE SUMMARY")
        logger.info(wide)
        logger.info("  Run ID            : %s", run_id[:16] + "…")
        logger.info("  API Name          : %s", run.api_name)
        logger.info("  Environment       : %s", run.environment_name)
        logger.info("  Execution Time    : %.1f s", run.total_execution_time_s or 0)
        logger.info("  Test Cases Saved  : %d", tc_count)
        logger.info("  Validation Records: %d", val_count)
        logger.info("  Passed            : %d  (%.1f%%)",
                    run.passed, run.pass_percentage)
        logger.info("  Failed            : %d", run.failed)
        logger.info("  Errors            : %d", run.errors)
        logger.info("  DB Size           : %.1f KB", self.db_size_kb())
        logger.info("  Persist Time      : %.2f s", elapsed)
        logger.info(wide)
        logger.info("  Execution stored successfully.")
        logger.info(wide)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _assert_init(self) -> None:
        if self._db is None:
            raise RuntimeError(
                "DatabaseManager is not initialised. Call init_db() first."
            )
