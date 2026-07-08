"""
reporting/report_manager.py
=============================
Public facade for the entire Phase 8 Reporting Engine.

``ReportManager`` is the ONLY class the rest of the framework calls.
No external code should directly instantiate HTMLGenerator, PDFGenerator,
CSVGenerator, JSONGenerator, or ComparisonReportGenerator.

Pipeline per run
----------------
    DatabaseManager  →  raw Db* rows
    AnalyticsManager →  AnalyticsSummary
         │
         ▼
    ReportManager.generate_report(run_id)
         │
         ├─ _build_bundle()        — assemble ReportBundle from DB + analytics
         │   ├─ ExecutiveSummary
         │   ├─ ValidationSummary  (from DbValidationDetail)
         │   ├─ DetailedResults    (from DbTestCaseResult)
         │   └─ raw lists cached on bundle for CSV/JSON generators
         │
         ├─ HTMLGenerator.generate()  → Execution_Report.html
         ├─ PDFGenerator.generate()   → Execution_Report.pdf
         ├─ CSVGenerator.generate()   → Execution_Report_results.csv
         │                            → Execution_Report_validation.csv
         └─ JSONGenerator.generate()  → Execution_Report.json

    If ≥ 2 runs exist:
         └─ ComparisonReportGenerator.generate()
                              → Comparison_Report.html
                              → Comparison_Report.pdf
"""

import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from constants.app_constants import AppMeta
from reporting.chart_generator import (
    generate_bar_chart, generate_gauge_chart,
    generate_line_chart, generate_pie_chart,
    generate_response_time_chart,
)
from reporting.comparison_report_generator import ComparisonReportGenerator
from reporting.csv_generator import CSVGenerator
from reporting.html_generator import HTMLGenerator
from reporting.json_generator import JSONGenerator
from reporting.pdf_generator import PDFGenerator
from reporting.report_models import (
    ChartData, DetailedResults, ExecutiveSummary, ReportBundle,
    ReportMetadata, TestResultRow, ValidatorRow, ValidationSummary,
)
from utilities.common_helpers import generate_id
from utilities.logger import get_logger

logger = get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ReportManager:
    """
    Orchestrates all report generators for one execution run.

    Args:
        db_manager:      Initialised ``DatabaseManager`` instance.
        analytics_manager: Initialised ``AnalyticsManager`` instance.
        output_dir:      Directory where reports are written.
                         Defaults to ``<project_root>/reports/``.

    Usage::

        with DatabaseManager(...) as db:
            analytics = AnalyticsManager(db)
            reporter  = ReportManager(db, analytics)
            paths     = reporter.generate_report(run_id)
    """

    def __init__(
        self,
        db_manager:        Any,
        analytics_manager: Any,
        output_dir:        Optional[Path] = None,
    ) -> None:
        self._db        = db_manager
        self._analytics = analytics_manager
        self._out_dir   = output_dir or (_PROJECT_ROOT / "reports")
        self._out_dir.mkdir(parents=True, exist_ok=True)

        self._html_gen   = HTMLGenerator(self._out_dir)
        self._pdf_gen    = PDFGenerator(self._out_dir)
        self._csv_gen    = CSVGenerator(self._out_dir)
        self._json_gen   = JSONGenerator(self._out_dir)
        self._cmp_gen    = ComparisonReportGenerator(self._out_dir)

        logger.info("ReportManager: output_dir='%s'", self._out_dir)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate_report(self, run_id: str) -> List[Path]:
        """
        Generate all reports for *run_id*.

        Args:
            run_id: Execution run to report on.

        Returns:
            List of paths to every file written.
        """
        t_start = time.monotonic()
        logger.info("ReportManager: generating reports for run '%s'.", run_id[:16])

        # ── Fetch data ─────────────────────────────────────────────────
        run        = self._db.get_run(run_id)
        tc_results = self._db.get_test_results(run_id)
        val_details= self._db.get_validation_details(run_id)
        analytics  = self._analytics.run_analysis(run_id)

        if run is None:
            logger.error("ReportManager: run '%s' not found.", run_id)
            return []

        # ── Build bundle ───────────────────────────────────────────────
        bundle = self._build_bundle(run, tc_results, val_details, analytics)

        # ── Generate reports ───────────────────────────────────────────
        generated: List[Path] = []

        try:
            html_path = self._html_gen.generate(bundle)
            generated.append(html_path)
            logger.info("ReportManager: HTML ✓  %s", html_path.name)
        except Exception as exc:
            logger.error("ReportManager: HTML failed — %s", exc, exc_info=True)

        try:
            pdf_path = self._pdf_gen.generate(bundle)
            if pdf_path:
                generated.append(pdf_path)
                logger.info("ReportManager: PDF  ✓  %s", pdf_path.name)
        except Exception as exc:
            logger.error("ReportManager: PDF failed — %s", exc, exc_info=True)

        try:
            csv_paths = self._csv_gen.generate(bundle)
            generated.extend(csv_paths)
            for p in csv_paths:
                logger.info("ReportManager: CSV  ✓  %s", p.name)
        except Exception as exc:
            logger.error("ReportManager: CSV failed — %s", exc, exc_info=True)

        try:
            json_path = self._json_gen.generate(bundle)
            generated.append(json_path)
            logger.info("ReportManager: JSON ✓  %s", json_path.name)
        except Exception as exc:
            logger.error("ReportManager: JSON failed — %s", exc, exc_info=True)

        # ── Comparison report (needs ≥ 2 runs) ─────────────────────────
        all_runs = self._db.search_runs(api_name=run.api_name, limit=500)
        sorted_runs = sorted(all_runs, key=lambda r: r.execution_timestamp or "")
        current_idx = next(
            (i for i, r in enumerate(sorted_runs) if r.run_id == run_id), -1
        )
        if current_idx > 0:
            prev_run  = sorted_runs[current_idx - 1]
            try:
                prev_analytics = self._analytics.run_analysis(prev_run.run_id)
                html_cmp, pdf_cmp = self._cmp_gen.generate(
                    baseline_analytics=prev_analytics,
                    current_analytics=analytics,
                    baseline_run=prev_run,
                    current_run=run,
                )
                if html_cmp:
                    generated.append(html_cmp)
                    logger.info("ReportManager: CMP HTML ✓  %s", html_cmp.name)
                if pdf_cmp:
                    generated.append(pdf_cmp)
                    logger.info("ReportManager: CMP PDF  ✓  %s", pdf_cmp.name)
            except Exception as exc:
                logger.error("ReportManager: comparison report failed — %s", exc, exc_info=True)
        else:
            logger.info(
                "ReportManager: skipping comparison report "
                "(only one run in database for '%s').", run.api_name,
            )

        elapsed = time.monotonic() - t_start
        self._print_summary(generated, elapsed, run.api_name)
        return generated

    # ------------------------------------------------------------------ #
    # Bundle assembly
    # ------------------------------------------------------------------ #

    def _build_bundle(
        self,
        run:        Any,
        tc_results: List[Any],
        val_details:List[Any],
        analytics:  Any,
    ) -> ReportBundle:
        """Assemble a fully-populated ReportBundle."""

        now_iso = datetime.now(tz=timezone.utc).isoformat()

        # ── Metadata ───────────────────────────────────────────────────
        metadata = ReportMetadata(
            report_id         = generate_id("rpt_"),
            generated_at      = now_iso,
            framework_name    = AppMeta.NAME,
            framework_version = AppMeta.VERSION,
            run_id            = run.run_id,
            api_name          = run.api_name,
            environment       = run.environment_name or "—",
            report_formats    = ["html", "pdf", "csv", "json"],
        )

        # ── Executive Summary ──────────────────────────────────────────
        health       = getattr(analytics, "health", None)
        exec_summary = ExecutiveSummary(
            api_name              = run.api_name,
            api_version           = run.api_version or "—",
            execution_date        = (run.execution_timestamp or "")[:19] + " UTC",
            environment           = run.environment_name or "—",
            total_endpoints       = run.total_endpoints,
            total_test_cases      = run.total_test_cases,
            total_executed        = run.total_executed,
            passed                = run.passed,
            failed                = run.failed,
            skipped               = run.skipped,
            errors                = run.errors,
            pass_percentage       = run.pass_percentage,
            avg_response_time_ms  = run.avg_response_time_ms,
            total_execution_time_s= run.total_execution_time_s,
            health_score          = health.score if health else 0.0,
            health_rating         = health.rating if health else "—",
            specification_file    = run.specification_file or "—",
            framework_version     = run.framework_version or AppMeta.VERSION,
        )

        # ── Validation Summary ─────────────────────────────────────────
        val_summary = self._build_validation_summary(val_details)

        # ── Detailed Results ───────────────────────────────────────────
        detailed = self._build_detailed_results(tc_results)

        # ── Bundle ────────────────────────────────────────────────────
        bundle = ReportBundle(
            metadata          = metadata,
            executive_summary = exec_summary,
            validation_summary= val_summary,
            detailed_results  = detailed,
            analytics         = analytics,
            run               = run,
        )
        # Cache raw lists so CSV / JSON generators can use full field sets
        bundle.raw_tc_results  = tc_results   # type: ignore[attr-defined]
        bundle.raw_val_details = val_details  # type: ignore[attr-defined]

        return bundle

    @staticmethod
    def _build_validation_summary(val_details: List[Any]) -> ValidationSummary:
        """Aggregate validation detail rows into a ValidationSummary."""
        vname_passed:  Dict[str, int] = defaultdict(int)
        vname_failed:  Dict[str, int] = defaultdict(int)

        for d in val_details:
            if d.status == "passed":
                vname_passed[d.validator_name] += 1
            else:
                vname_failed[d.validator_name] += 1

        all_names = sorted(set(list(vname_passed) + list(vname_failed)))
        rows = []
        for name in all_names:
            p = vname_passed.get(name, 0)
            f = vname_failed.get(name, 0)
            total = p + f
            rows.append(ValidatorRow(
                validator_name = name,
                passed  = p,
                failed  = f,
                total   = total,
                pass_rate = round((p / total * 100) if total else 0.0, 1),
            ))

        total_p = sum(vname_passed.values())
        total_f = sum(vname_failed.values())
        return ValidationSummary(
            validators        = rows,
            total_assertions  = total_p + total_f,
            total_passed      = total_p,
            total_failed      = total_f,
        )

    @staticmethod
    def _build_detailed_results(tc_results: List[Any]) -> DetailedResults:
        """Convert DbTestCaseResult rows into DetailedResults."""
        rows = [
            TestResultRow(
                result_id            = r.result_id,
                operation_id         = r.operation_id or "—",
                endpoint             = r.endpoint,
                method               = r.http_method,
                category             = r.category or "—",
                status               = r.validation_status or "—",
                response_status_code = r.response_status_code,
                response_time_ms     = r.response_time_ms,
                validation_status    = r.validation_status or "—",
                failure_reason       = r.failure_reason or "",
                executed_at          = (r.executed_at or "")[:19],
            )
            for r in tc_results
        ]
        return DetailedResults(
            rows          = rows,
            total         = len(rows),
            passed_count  = sum(1 for r in rows if r.validation_status == "passed"),
            failed_count  = sum(1 for r in rows if r.validation_status == "failed"),
            error_count   = sum(1 for r in rows if r.validation_status == "error"),
        )

    # ------------------------------------------------------------------ #
    # Summary printer
    # ------------------------------------------------------------------ #

    def _print_summary(
        self, generated: List[Path], elapsed: float, api_name: str
    ) -> None:
        wide = "=" * 52
        sep  = "─" * 52
        logger.info(wide)
        logger.info("  REPORT GENERATION SUMMARY")
        logger.info(wide)
        logger.info("  API        : %s", api_name)
        logger.info("  Output Dir : %s", self._out_dir)
        logger.info(sep)
        for path in generated:
            ext = path.suffix.upper().lstrip(".")
            size_kb = round(path.stat().st_size / 1024, 1)
            logger.info("  %-4s Report  : %-36s  %6.1f KB", ext, path.name, size_kb)
        logger.info(sep)
        logger.info("  Generation Time : %.2f s", elapsed)
        logger.info(wide)
        logger.info("  Report generation complete.")
        logger.info(wide)
