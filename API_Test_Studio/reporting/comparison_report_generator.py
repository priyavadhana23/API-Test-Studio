"""
reporting/comparison_report_generator.py
==========================================
Generates HTML and PDF comparison reports between two execution runs.

Data source: Two ``AnalyticsSummary`` objects (baseline + current) from
``AnalyticsManager``, plus their ``DbExecutionRun`` records.

The generator assembles a ``ComparisonSummary`` from the pre-computed
``RegressionSummary`` already present in the current run's analytics —
no recalculation occurs here.

Outputs:
    Comparison_Report.html
    Comparison_Report.pdf
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

from reporting.chart_generator import generate_grouped_bar_chart, generate_gauge_chart
from reporting.pdf_generator import PDFGenerator
from reporting.report_models import ChartData, ComparisonSummary, ReportBundle, ReportMetadata
from reporting.template_loader import TemplateLoader
from utilities.common_helpers import generate_id
from utilities.logger import get_logger

logger = get_logger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


class ComparisonReportGenerator:
    """
    Builds HTML and PDF comparison reports from two analytics summaries.

    Args:
        output_dir:    Directory where reports are written.
        templates_dir: Override the default templates directory.
    """

    def __init__(
        self,
        output_dir: Path,
        templates_dir: Optional[Path] = None,
    ) -> None:
        self._output_dir  = output_dir
        self._loader      = TemplateLoader(templates_dir)
        self._pdf_gen     = PDFGenerator(output_dir)
        logger.debug("ComparisonReportGenerator: output_dir='%s'", output_dir)

    def generate(
        self,
        baseline_analytics: Any,
        current_analytics:  Any,
        baseline_run: Any,
        current_run:  Any,
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Produce HTML and PDF comparison reports.

        Args:
            baseline_analytics: ``AnalyticsSummary`` for the older run.
            current_analytics:  ``AnalyticsSummary`` for the newer run.
            baseline_run:       ``DbExecutionRun`` for the baseline.
            current_run:        ``DbExecutionRun`` for the current run.

        Returns:
            Tuple of ``(html_path, pdf_path)``.  Either may be ``None``
            if generation failed.
        """
        logger.info(
            "ComparisonReportGenerator: comparing runs %s vs %s.",
            getattr(baseline_run, "run_id", "?")[:8],
            getattr(current_run, "run_id", "?")[:8],
        )

        comparison = self._build_comparison_summary(
            baseline_analytics, current_analytics,
            baseline_run, current_run,
        )
        bundle = self._build_bundle(comparison, current_analytics, current_run)
        html_path = self._generate_html(bundle)
        pdf_path  = self._generate_pdf(bundle)
        return html_path, pdf_path

    # ------------------------------------------------------------------ #
    # Private builders
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_comparison_summary(
        baseline_an: Any,
        current_an:  Any,
        baseline_run: Any,
        current_run:  Any,
    ) -> ComparisonSummary:
        """Assemble a ComparisonSummary from pre-computed analytics data."""
        reg = getattr(current_an, "regression", None)

        b_health = getattr(getattr(baseline_an, "health", None), "score", 0.0) or 0.0
        c_health = getattr(getattr(current_an,  "health", None), "score", 0.0) or 0.0

        avg_rt_b = getattr(baseline_run, "avg_response_time_ms", None)
        avg_rt_c = getattr(current_run,  "avg_response_time_ms", None)
        avg_rt_delta = (
            round(avg_rt_c - avg_rt_b, 2)
            if avg_rt_b is not None and avg_rt_c is not None else None
        )

        return ComparisonSummary(
            api_name           = getattr(current_run, "api_name", "—"),
            run_id_baseline    = getattr(baseline_run, "run_id", ""),
            run_id_current     = getattr(current_run,  "run_id", ""),
            timestamp_baseline = getattr(baseline_run, "execution_timestamp", "")[:19],
            timestamp_current  = getattr(current_run,  "execution_timestamp", "")[:19],
            passed_baseline    = getattr(baseline_run, "passed", 0),
            passed_current     = getattr(current_run,  "passed", 0),
            passed_delta       = getattr(current_run, "passed", 0) - getattr(baseline_run, "passed", 0),
            failed_baseline    = getattr(baseline_run, "failed", 0),
            failed_current     = getattr(current_run,  "failed", 0),
            failed_delta       = getattr(current_run, "failed", 0) - getattr(baseline_run, "failed", 0),
            pass_pct_baseline  = getattr(baseline_run, "pass_percentage", 0.0) or 0.0,
            pass_pct_current   = getattr(current_run,  "pass_percentage", 0.0) or 0.0,
            pass_pct_delta     = round(
                (getattr(current_run,  "pass_percentage", 0.0) or 0.0)
                - (getattr(baseline_run, "pass_percentage", 0.0) or 0.0), 2
            ),
            health_baseline    = b_health,
            health_current     = c_health,
            health_delta       = round(c_health - b_health, 2),
            avg_rt_baseline    = avg_rt_b,
            avg_rt_current     = avg_rt_c,
            avg_rt_delta       = avg_rt_delta,
            new_failures       = getattr(reg, "new_failures", []),
            fixed_failures     = getattr(reg, "fixed_failures", []),
            unchanged_failures = getattr(reg, "unchanged_failures", []),
            verdict            = getattr(reg, "verdict", ""),
            has_regression     = getattr(reg, "has_regression", False),
        )

    def _build_bundle(
        self,
        comparison: ComparisonSummary,
        current_an: Any,
        current_run: Any,
    ) -> ReportBundle:
        """Build a ReportBundle carrying only comparison data."""
        now = datetime.now(tz=timezone.utc).isoformat()
        meta = ReportMetadata(
            report_id         = generate_id("rpt_"),
            generated_at      = now,
            framework_name    = "API Test Studio",
            framework_version = "1.0.0",
            run_id            = comparison.run_id_current,
            api_name          = comparison.api_name,
            report_formats    = ["html", "pdf"],
        )

        charts: dict = {}
        # Side-by-side grouped bar chart
        chart_html = generate_grouped_bar_chart(
            categories=["Passed", "Failed", "Errors"],
            series=[
                ("Baseline",
                 [float(getattr(current_run, "passed", 0)),
                  float(getattr(current_run, "failed", 0)),
                  float(getattr(current_run, "errors", 0))],
                 "#2980B9"),
                ("Current",
                 [float(comparison.passed_current),
                  float(comparison.failed_current),
                  float(getattr(current_run, "errors", 0))],
                 "#27AE60"),
            ],
            title="Baseline vs Current — Test Outcomes",
            include_js=True,
        )
        charts["comparison_bar"] = ChartData(
            chart_id="comparison_bar",
            title="Baseline vs Current",
            html=chart_html,
            chart_type="bar",
        )

        css_content = ""
        css_path = _ASSETS_DIR / "style.css"
        try:
            css_content = css_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            pass

        bundle = ReportBundle(
            metadata    = meta,
            comparison  = comparison,
            analytics   = current_an,
            run         = current_run,
            charts      = charts,
        )
        bundle._css_content = css_content  # type: ignore[attr-defined]
        return bundle

    def _generate_html(self, bundle: ReportBundle) -> Optional[Path]:
        """Render the comparison HTML report."""
        try:
            css = getattr(bundle, "_css_content", "")
            html = self._loader.render(
                "base.html",
                page_title=f"Comparison Report — {bundle.metadata.api_name if bundle.metadata else ''}",
                metadata=bundle.metadata,
                exec_summary=None,
                val_summary=None,
                detailed=None,
                comparison=bundle.comparison,
                analytics=bundle.analytics,
                charts=bundle.charts,
                css_content=css,
                show_comparison=True,
            )
            # Inject comparison section into base template directly
            from reporting.template_loader import TemplateLoader as TL
            # Use dashboard template which includes comparison.html
            loader2 = TL()
            html = loader2.render(
                "dashboard.html",
                page_title=f"Comparison — {bundle.comparison.api_name if bundle.comparison else ''}",
                metadata=bundle.metadata,
                exec_summary=None,
                val_summary=None,
                detailed=None,
                comparison=bundle.comparison,
                analytics=bundle.analytics,
                charts=bundle.charts,
                css_content=css,
                show_comparison=True,
            )
            out_path = self._output_dir / "Comparison_Report.html"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(html, encoding="utf-8")
            logger.info("ComparisonReportGenerator: HTML → '%s'", out_path.name)
            return out_path
        except Exception as exc:
            logger.error("ComparisonReportGenerator: HTML failed — %s", exc, exc_info=True)
            return None

    def _generate_pdf(self, bundle: ReportBundle) -> Optional[Path]:
        """Render the comparison PDF report."""
        try:
            return self._pdf_gen.generate(bundle, filename="Comparison_Report.pdf")
        except Exception as exc:
            logger.error("ComparisonReportGenerator: PDF failed — %s", exc, exc_info=True)
            return None
