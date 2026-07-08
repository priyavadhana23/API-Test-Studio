"""
reporting/csv_generator.py
============================
Exports test-case results and validation details to CSV files.

Two files are produced per run:
    Execution_Report_results.csv    — one row per test-case result
    Execution_Report_validation.csv — one row per validator check

These files open directly in Excel / LibreOffice with no import wizard needed
(UTF-8 with BOM so Excel auto-detects the encoding).

No calculations. No SQL. Reads from ReportBundle only.
"""

import csv
from pathlib import Path
from typing import Any, List, Optional

from reporting.report_models import ReportBundle
from utilities.logger import get_logger

logger = get_logger(__name__)

_RESULT_FIELDS = [
    "result_id", "run_id", "test_id", "operation_id",
    "endpoint", "http_method", "category",
    "request_url", "response_status_code",
    "response_time_ms", "validation_status",
    "failure_reason", "validation_time_ms", "executed_at",
]

_VALIDATION_FIELDS = [
    "validation_detail_id", "result_id", "run_id",
    "validator_name", "status", "message",
    "severity", "execution_time_ms", "recorded_at",
]


class CSVGenerator:
    """
    Exports test-case and validation detail records to CSV.

    Args:
        output_dir: Directory where CSV files are written.
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        logger.debug("CSVGenerator: output_dir='%s'", output_dir)

    def generate(
        self,
        bundle: ReportBundle,
        base_filename: str = "Execution_Report",
    ) -> List[Path]:
        """
        Write two CSV files: test results and validation details.

        Args:
            bundle:        Fully assembled ``ReportBundle``.
            base_filename: Prefix for output filenames.

        Returns:
            List of paths to the written CSV files.
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)
        paths: List[Path] = []

        # ── Results CSV ───────────────────────────────────────────────
        results_path = self._output_dir / f"{base_filename}_results.csv"
        tc_results   = getattr(bundle.run, "_tc_results_cache", None)

        # tc_results comes from ReportManager which caches them on the bundle
        # via bundle.run._tc_results_cache; fall back to detailed_results rows
        rows: List[Any] = []
        if bundle.detailed_results:
            for row in bundle.detailed_results.rows:
                rows.append({
                    "result_id":           row.result_id,
                    "run_id":              bundle.metadata.run_id if bundle.metadata else "",
                    "test_id":             row.result_id,  # best we have in DetailedResults
                    "operation_id":        row.operation_id,
                    "endpoint":            row.endpoint,
                    "http_method":         row.method,
                    "category":            row.category,
                    "request_url":         row.result_id,  # not in DetailedResults
                    "response_status_code": row.response_status_code,
                    "response_time_ms":    row.response_time_ms,
                    "validation_status":   row.validation_status,
                    "failure_reason":      row.failure_reason,
                    "validation_time_ms":  "",
                    "executed_at":         row.executed_at,
                })

        if bundle.raw_tc_results:
            rows = [{f: getattr(r, f, "") for f in _RESULT_FIELDS}
                    for r in bundle.raw_tc_results]

        self._write_csv(results_path, _RESULT_FIELDS, rows)
        logger.info("CSVGenerator: results CSV → '%s'  (%d rows).",
                    results_path.name, len(rows))
        paths.append(results_path)

        # ── Validation Details CSV ────────────────────────────────────
        val_path = self._output_dir / f"{base_filename}_validation.csv"
        val_rows: List[Any] = []
        if bundle.raw_val_details:
            val_rows = [{f: getattr(d, f, "") for f in _VALIDATION_FIELDS}
                        for d in bundle.raw_val_details]

        self._write_csv(val_path, _VALIDATION_FIELDS, val_rows)
        logger.info("CSVGenerator: validation CSV → '%s'  (%d rows).",
                    val_path.name, len(val_rows))
        paths.append(val_path)

        return paths

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _write_csv(path: Path, fieldnames: List[str], rows: List[Any]) -> None:
        """Write *rows* to a UTF-8-BOM CSV file at *path*."""
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
