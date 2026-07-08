"""
reporting/html_generator.py
=============================
Generates an interactive HTML dashboard report from a ``ReportBundle``.

Responsibilities:
    - Load CSS from assets/style.css
    - Call ChartGenerator to produce all Plotly chart divs
    - Pass the assembled context to the Jinja2 dashboard template
    - Write the resulting HTML to the reports/ directory

No calculations.  No SQL.  Only presentation.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from reporting.chart_generator import (
    generate_bar_chart,
    generate_gauge_chart,
    generate_grouped_bar_chart,
    generate_line_chart,
    generate_pie_chart,
    generate_response_time_chart,
)
from reporting.report_models import ChartData, ReportBundle
from reporting.template_loader import TemplateLoader
from utilities.logger import get_logger

logger = get_logger(__name__)

# CSS file location
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


class HTMLGenerator:
    """
    Builds a self-contained interactive HTML report.

    The HTML file embeds Plotly.js and the stylesheet so it can be opened
    directly in any browser without any server or external CDN dependency.

    Args:
        output_dir: Directory where the HTML file is written.
        templates_dir: Override the default templates directory.
    """

    def __init__(
        self,
        output_dir: Path,
        templates_dir: Optional[Path] = None,
    ) -> None:
        self._output_dir = output_dir
        self._loader = TemplateLoader(templates_dir)
        logger.debug("HTMLGenerator: output_dir='%s'", output_dir)

    def generate(self, bundle: ReportBundle, filename: str = "Execution_Report.html") -> Path:
        """
        Render and write the HTML report.

        Args:
            bundle:   Fully assembled ``ReportBundle``.
            filename: Output filename.

        Returns:
            Path to the written HTML file.
        """
        logger.info("HTMLGenerator: building HTML report '%s'.", filename)

        # Load CSS for inline embedding
        css_content = self._load_css()

        # Build all charts (first chart includes Plotly.js; rest reference it)
        charts = self._build_charts(bundle)

        # Assemble Jinja2 context
        context: Dict[str, Any] = {
            "page_title":   f"API Test Studio — {bundle.metadata.api_name if bundle.metadata else 'Report'}",
            "metadata":     bundle.metadata,
            "exec_summary": bundle.executive_summary,
            "val_summary":  bundle.validation_summary,
            "detailed":     bundle.detailed_results,
            "comparison":   bundle.comparison,
            "analytics":    bundle.analytics,
            "charts":       charts,
            "css_content":  css_content,
            "show_comparison": bundle.comparison is not None,
        }

        html = self._loader.render("dashboard.html", **context)

        output_path = self._output_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

        size_kb = round(output_path.stat().st_size / 1024, 1)
        logger.info(
            "HTMLGenerator: report written → '%s'  (%.1f KB)", output_path.name, size_kb
        )
        return output_path

    # ------------------------------------------------------------------ #
    # Chart assembly
    # ------------------------------------------------------------------ #

    def _build_charts(self, bundle: ReportBundle) -> Dict[str, ChartData]:
        """Build all Plotly charts and return a dict keyed by chart_id."""
        charts: Dict[str, ChartData] = {}
        first = True   # first chart embeds Plotly.js

        def add(chart_id: str, title: str, html: str, ctype: str) -> None:
            charts[chart_id] = ChartData(
                chart_id=chart_id, title=title, html=html, chart_type=ctype
            )

        run = bundle.run
        analytics = bundle.analytics

        # ── Pass / Fail Pie ───────────────────────────────────────────
        if run:
            add("pass_fail_pie", "Pass vs Fail Distribution",
                generate_pie_chart(
                    labels=["Passed", "Failed", "Errors", "Skipped"],
                    values=[run.passed, run.failed, run.errors, run.skipped],
                    title="Pass vs Fail Distribution",
                    include_js=first,
                ), "pie")
            first = False

        # ── Health Score Gauge ────────────────────────────────────────
        if analytics and analytics.health:
            add("health_gauge", "API Health Score",
                generate_gauge_chart(
                    value=analytics.health.score,
                    title="API Health Score",
                    include_js=first,
                ), "gauge")
            first = False

        # ── Endpoint Pass Rate Bar ────────────────────────────────────
        if analytics and analytics.endpoint_analysis and analytics.endpoint_analysis.all_stats:
            stats = sorted(
                analytics.endpoint_analysis.all_stats,
                key=lambda s: s.total_executions, reverse=True
            )[:12]
            add("endpoint_pass_rate", "Endpoint Pass Rate (%)",
                generate_bar_chart(
                    categories=[f"{s.method} {s.endpoint}"[:30] for s in stats],
                    values=[s.pass_rate for s in stats],
                    title="Endpoint Pass Rate (%)",
                    y_label="Pass Rate (%)",
                    include_js=first,
                ), "bar")
            first = False

        # ── Response Time Bar ─────────────────────────────────────────
        if analytics and analytics.endpoint_analysis and analytics.endpoint_analysis.all_stats:
            timed = [s for s in analytics.endpoint_analysis.all_stats
                     if s.avg_response_time_ms is not None]
            timed_sorted = sorted(timed, key=lambda s: s.avg_response_time_ms or 0, reverse=True)[:10]
            if timed_sorted:
                add("response_time_bar", "Avg Response Time by Endpoint",
                    generate_response_time_chart(
                        endpoints=[f"{s.method} {s.endpoint}"[:30] for s in timed_sorted],
                        avg_times=[s.avg_response_time_ms or 0 for s in timed_sorted],
                        include_js=first,
                    ), "bar")
                first = False

        # ── Pass Rate Trend Line ──────────────────────────────────────
        if analytics and analytics.trend and analytics.trend.points:
            pts = analytics.trend.points
            add("trend_line", "Pass Rate Trend",
                generate_line_chart(
                    x_values=[p.label for p in pts],
                    y_values=[p.value for p in pts],
                    title="Pass Rate Trend (%)",
                    y_label="Pass Rate (%)",
                    moving_avg=analytics.trend.moving_avg or None,
                    include_js=first,
                ), "line")
            first = False

        # ── Failure Distribution Pie ──────────────────────────────────
        if analytics and analytics.failure_analysis:
            fa = analytics.failure_analysis
            dist_labels, dist_values = [], []
            mapping = [
                ("Validation", fa.validation_failures),
                ("Exec Errors", fa.execution_errors),
                ("Auth",        fa.auth_failures),
                ("Schema",      fa.schema_failures),
                ("Timeout",     fa.timeout_failures),
                ("Business Rule", fa.business_rule_failures),
            ]
            for label, val in mapping:
                if val > 0:
                    dist_labels.append(label)
                    dist_values.append(val)
            if dist_labels:
                add("failure_dist_pie", "Failure Distribution",
                    generate_pie_chart(
                        labels=dist_labels,
                        values=dist_values,
                        title="Failure Distribution",
                        include_js=first,
                    ), "pie")
                first = False

        # ── Execution Count Bar ───────────────────────────────────────
        if analytics and analytics.endpoint_analysis and analytics.endpoint_analysis.all_stats:
            stats_sorted = sorted(
                analytics.endpoint_analysis.all_stats,
                key=lambda s: s.total_executions, reverse=True
            )[:10]
            add("exec_count_bar", "Endpoint Execution Count",
                generate_bar_chart(
                    categories=[f"{s.method} {s.endpoint}"[:30] for s in stats_sorted],
                    values=[float(s.total_executions) for s in stats_sorted],
                    title="Endpoint Execution Count",
                    y_label="Executions",
                    include_js=first,
                ), "bar")

        return charts

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _load_css(self) -> str:
        """Load the report stylesheet, returning empty string on failure."""
        css_path = _ASSETS_DIR / "style.css"
        try:
            return css_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning("HTMLGenerator: style.css not found at '%s'.", css_path)
            return ""
