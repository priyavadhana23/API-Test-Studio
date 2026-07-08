"""
reporting/pdf_generator.py
============================
Generates an executive-summary PDF report using ReportLab.

Target audience: managers and stakeholders who want a concise printed
summary — NOT the full 300-row test table.

Sections included:
    1. Cover page (API name, date, health score)
    2. Executive Summary table
    3. Analytics Insights (health components, response-time stats)
    4. Endpoint Overview table (top 15 by execution count)
    5. Failure Analysis summary
    6. Regression Status
    7. Recommendations

No calculations. No SQL. Reads from ReportBundle only.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    # Colour palette — defined inside the guard so they only exist when
    # ReportLab is available.  Module-level references outside the try
    # block would raise NameError when reportlab is not installed.
    _C_DARK   = colors.HexColor("#2C3E50")
    _C_BLUE   = colors.HexColor("#2980B9")
    _C_PASS   = colors.HexColor("#27AE60")
    _C_FAIL   = colors.HexColor("#E74C3C")
    _C_WARN   = colors.HexColor("#E67E22")
    _C_LIGHT  = colors.HexColor("#ECF0F1")
    _C_WHITE  = colors.white
    _C_HEADER = colors.HexColor("#1A252F")
    _REPORTLAB_OK = True
except ImportError:
    _REPORTLAB_OK = False
    # Stub colour objects so module-level class bodies that reference
    # _C_* don't raise NameError — they are only used inside generate()
    # which is guarded by ``if not _REPORTLAB_OK: return None``.
    class _ColorStub:
        def __getattr__(self, _): return self
        def __call__(self, *a, **k): return self
    _stub = _ColorStub()
    _C_DARK = _C_BLUE = _C_PASS = _C_FAIL = _C_WARN = _C_LIGHT = _C_WHITE = _C_HEADER = _stub

from reporting.report_models import ReportBundle
from utilities.logger import get_logger

logger = get_logger(__name__)


class PDFGenerator:
    """
    Generates an executive PDF using ReportLab's Platypus layout engine.

    Args:
        output_dir: Directory where the PDF file is written.
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        logger.debug("PDFGenerator: output_dir='%s'", output_dir)

    def generate(
        self,
        bundle: ReportBundle,
        filename: str = "Execution_Report.pdf",
    ) -> Optional[Path]:
        """
        Build and write the executive PDF.

        Args:
            bundle:   Fully assembled ``ReportBundle``.
            filename: Output filename.

        Returns:
            Path to the written PDF, or ``None`` if ReportLab is unavailable.
        """
        if not _REPORTLAB_OK:
            logger.error(
                "PDFGenerator: reportlab is not installed. "
                "Install with: pip install reportlab"
            )
            return None

        self._output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._output_dir / filename

        styles = getSampleStyleSheet()
        story: List[Any] = []

        self._add_cover(story, bundle, styles)
        self._add_exec_summary(story, bundle, styles)
        self._add_analytics(story, bundle, styles)
        self._add_endpoint_table(story, bundle, styles)
        self._add_failure_summary(story, bundle, styles)
        self._add_regression(story, bundle, styles)
        self._add_recommendations(story, bundle, styles)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        doc.build(story)

        size_kb = round(output_path.stat().st_size / 1024, 1)
        logger.info("PDFGenerator: PDF written → '%s'  (%.1f KB)", filename, size_kb)
        return output_path

    # ------------------------------------------------------------------ #
    # Section builders
    # ------------------------------------------------------------------ #

    def _add_cover(self, story: List, bundle: ReportBundle, styles: Any) -> None:
        es = bundle.executive_summary
        meta = bundle.metadata

        story.append(Spacer(1, 3 * cm))
        story.append(Paragraph(
            "🧪 API Test Studio",
            ParagraphStyle("Cover1", fontSize=28, textColor=_C_DARK, spaceAfter=6),
        ))
        story.append(Paragraph(
            "Execution Report",
            ParagraphStyle("Cover2", fontSize=20, textColor=_C_BLUE, spaceAfter=20),
        ))
        story.append(HRFlowable(width="100%", thickness=2, color=_C_BLUE))
        story.append(Spacer(1, 0.5 * cm))

        api_name  = es.api_name if es else (meta.api_name if meta else "—")
        exec_date = es.execution_date if es else "—"
        env       = es.environment if es else "—"
        score     = f"{es.health_score:.1f} / 100  [{es.health_rating}]" if es else "—"
        run_id    = (meta.run_id[:20] + "…") if meta else "—"

        for label, value in [
            ("API",         api_name),
            ("Date",        exec_date),
            ("Environment", env),
            ("Health Score", score),
            ("Run ID",       run_id),
        ]:
            story.append(Paragraph(
                f"<b>{label}:</b>  {value}",
                ParagraphStyle("CoverInfo", fontSize=13, spaceAfter=8),
            ))

        story.append(Spacer(1, 1.5 * cm))
        story.append(Paragraph(
            f"Generated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
            ParagraphStyle("CoverFooter", fontSize=10, textColor=_C_BLUE),
        ))
        story.append(PageBreak())

    def _add_exec_summary(self, story: List, bundle: ReportBundle, styles: Any) -> None:
        es = bundle.executive_summary
        if not es:
            return
        story.append(Paragraph("Executive Summary", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=_C_LIGHT))
        story.append(Spacer(1, 0.3 * cm))

        rows = [
            ["Metric", "Value"],
            ["API Name",          es.api_name],
            ["Version",           es.api_version or "—"],
            ["Environment",       es.environment],
            ["Total Endpoints",   str(es.total_endpoints)],
            ["Total Test Cases",  str(es.total_test_cases)],
            ["Executed",          str(es.total_executed)],
            ["Passed",            str(es.passed)],
            ["Failed",            str(es.failed)],
            ["Errors",            str(es.errors)],
            ["Pass Rate",         f"{es.pass_percentage:.1f}%"],
            ["Avg Response Time", f"{es.avg_response_time_ms:.1f} ms" if es.avg_response_time_ms else "—"],
            ["Total Exec Time",   f"{es.total_execution_time_s:.2f} s" if es.total_execution_time_s else "—"],
            ["Health Score",      f"{es.health_score:.1f} / 100  [{es.health_rating}]"],
        ]
        t = Table(rows, colWidths=[9 * cm, 9 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), _C_HEADER),
            ("TEXTCOLOR",    (0, 0), (-1, 0), _C_WHITE),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, 0), 11),
            ("FONTNAME",     (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 1), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_C_WHITE, _C_LIGHT]),
            ("GRID",         (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING",      (0, 0), (-1, -1), 8),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.8 * cm))

    def _add_analytics(self, story: List, bundle: ReportBundle, styles: Any) -> None:
        analytics = bundle.analytics
        if not analytics:
            return
        story.append(Paragraph("Analytics Insights", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=_C_LIGHT))
        story.append(Spacer(1, 0.3 * cm))

        rows = [["Metric", "Value"]]
        h = analytics.health
        if h:
            rows += [
                ["Health Score",      f"{h.score:.1f} / 100"],
                ["Rating",            h.rating],
                ["Pass Rate Score",   f"{h.pass_rate_score:.1f} / 40"],
                ["Response Time Score", f"{h.response_time_score:.1f} / 30"],
                ["Stability Score",   f"{h.stability_score:.1f} / 20"],
                ["Availability Score",f"{h.availability_score:.1f} / 10"],
            ]
        rt = analytics.response_time
        if rt and rt.sample_count > 0:
            rows += [
                ["RT Samples",        str(rt.sample_count)],
                ["Mean RT",           f"{rt.mean_ms:.1f} ms" if rt.mean_ms else "—"],
                ["Median RT",         f"{rt.median_ms:.1f} ms" if rt.median_ms else "—"],
                ["P95 RT",            f"{rt.p95_ms:.1f} ms" if rt.p95_ms else "—"],
                ["P99 RT",            f"{rt.p99_ms:.1f} ms" if rt.p99_ms else "—"],
                ["SLA Compliance",    f"{rt.sla_compliance_pct:.1f}%"],
            ]
        ep = analytics.endpoint_analysis
        if ep:
            rows += [
                ["Most Executed",     ep.most_executed or "—"],
                ["Most Failed",       ep.most_failed or "—"],
                ["Slowest",           ep.slowest or "—"],
                ["Fastest",           ep.fastest or "—"],
            ]

        t = Table(rows, colWidths=[9 * cm, 9 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), _C_HEADER),
            ("TEXTCOLOR",    (0, 0), (-1, 0), _C_WHITE),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME",     (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_C_WHITE, _C_LIGHT]),
            ("GRID",         (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING",      (0, 0), (-1, -1), 7),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.8 * cm))

    def _add_endpoint_table(self, story: List, bundle: ReportBundle, styles: Any) -> None:
        analytics = bundle.analytics
        if not analytics or not analytics.endpoint_analysis:
            return
        ep_stats = sorted(
            analytics.endpoint_analysis.all_stats,
            key=lambda s: s.total_executions, reverse=True
        )[:15]
        if not ep_stats:
            return

        story.append(Paragraph("Top Endpoints", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=_C_LIGHT))
        story.append(Spacer(1, 0.3 * cm))

        header = [["Method", "Endpoint", "Runs", "Pass%", "Avg RT (ms)"]]
        data_rows = [
            [s.method,
             s.endpoint[:32],
             str(s.total_executions),
             f"{s.pass_rate:.1f}%",
             f"{s.avg_response_time_ms:.0f}" if s.avg_response_time_ms else "—"]
            for s in ep_stats
        ]
        t = Table(header + data_rows, colWidths=[2.5*cm, 8*cm, 2*cm, 2.5*cm, 3*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), _C_HEADER),
            ("TEXTCOLOR",    (0, 0), (-1, 0), _C_WHITE),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_C_WHITE, _C_LIGHT]),
            ("GRID",         (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("PADDING",      (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.8 * cm))

    def _add_failure_summary(self, story: List, bundle: ReportBundle, styles: Any) -> None:
        analytics = bundle.analytics
        if not analytics or not analytics.failure_analysis:
            return
        fa = analytics.failure_analysis
        if fa.total_failures == 0:
            return

        story.append(Paragraph("Failure Analysis", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=_C_LIGHT))
        story.append(Spacer(1, 0.3 * cm))

        rows = [["Category", "Count"], ]
        for label, val in [
            ("Total Failures",       fa.total_failures),
            ("Validation Failures",  fa.validation_failures),
            ("Execution Errors",     fa.execution_errors),
            ("Auth Failures",        fa.auth_failures),
            ("Schema Failures",      fa.schema_failures),
            ("Timeout Failures",     fa.timeout_failures),
        ]:
            if val:
                rows.append([label, str(val)])

        t = Table(rows, colWidths=[12 * cm, 6 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), _C_HEADER),
            ("TEXTCOLOR",    (0, 0), (-1, 0), _C_WHITE),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_C_WHITE, _C_LIGHT]),
            ("GRID",         (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING",      (0, 0), (-1, -1), 7),
        ]))
        story.append(t)

        if fa.top_failures:
            story.append(Spacer(1, 0.4 * cm))
            story.append(Paragraph("Top Failure Messages", styles["Heading2"]))
            for i, f in enumerate(fa.top_failures[:5], 1):
                story.append(Paragraph(
                    f"{i}. [{f.count}×] {f.category[:100]}",
                    ParagraphStyle("FailItem", fontSize=9, spaceAfter=4, leftIndent=10),
                ))
        story.append(Spacer(1, 0.8 * cm))

    def _add_regression(self, story: List, bundle: ReportBundle, styles: Any) -> None:
        analytics = bundle.analytics
        if not analytics or not analytics.regression:
            return
        reg = analytics.regression

        story.append(Paragraph("Regression Status", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=_C_LIGHT))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(reg.verdict, styles["Normal"]))

        if reg.new_failures:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph(
                f"New Failures ({len(reg.new_failures)}):",
                ParagraphStyle("RegHead", fontSize=11, textColor=_C_FAIL),
            ))
            for op in reg.new_failures[:10]:
                story.append(Paragraph(
                    f"• {op}",
                    ParagraphStyle("RegItem", fontSize=9, leftIndent=12, spaceAfter=3),
                ))
        if reg.fixed_failures:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Paragraph(
                f"Fixed Failures ({len(reg.fixed_failures)}):",
                ParagraphStyle("RegHeadPass", fontSize=11, textColor=_C_PASS),
            ))
            for op in reg.fixed_failures[:10]:
                story.append(Paragraph(
                    f"• {op}",
                    ParagraphStyle("RegItemF", fontSize=9, leftIndent=12, spaceAfter=3),
                ))
        story.append(Spacer(1, 0.8 * cm))

    def _add_recommendations(self, story: List, bundle: ReportBundle, styles: Any) -> None:
        analytics = bundle.analytics
        if not analytics or not analytics.health:
            return
        recs = analytics.health.recommendations
        if not recs:
            return

        story.append(Paragraph("Recommendations", styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=_C_LIGHT))
        story.append(Spacer(1, 0.3 * cm))
        for rec in recs:
            story.append(Paragraph(
                f"⚠  {rec}",
                ParagraphStyle("RecItem", fontSize=10, spaceAfter=6, leftIndent=8),
            ))
