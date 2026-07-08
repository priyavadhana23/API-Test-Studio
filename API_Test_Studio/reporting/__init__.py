"""
reporting package
==================
Phase 8 — Enterprise Reporting Engine for API Test Studio.

Public API (the only import the rest of the framework needs):

    from reporting import ReportManager

    with DatabaseManager(...) as db:
        analytics = AnalyticsManager(db)
        reporter  = ReportManager(db, analytics)
        paths     = reporter.generate_report(run_id)

Internal modules:

    report_models               — Presentation-layer dataclasses
    chart_generator             — Plotly chart builders
    template_loader             — Jinja2 environment
    html_generator              — Interactive HTML dashboard
    pdf_generator               — Executive PDF (ReportLab)
    csv_generator               — Test results + validation detail CSVs
    json_generator              — Structured JSON export
    comparison_report_generator — Baseline vs current run HTML + PDF
    report_manager              — Public facade (orchestrates all above)

To add a new format (Excel, Word, Email, Slack):
    1. Create reporting/excel_generator.py with a generate(bundle) method.
    2. Import and call it in ReportManager.generate_report().
    3. No other changes required.
"""

from reporting.report_manager import ReportManager
from reporting.report_models import ReportBundle

__all__ = ["ReportManager"]
