"""
web_dashboard/backend/schemas/reports.py
=========================================
Pydantic response models for GET /api/reports/{run_id}.
"""

from typing import List, Optional
from pydantic import BaseModel


class ReportFile(BaseModel):
    """Metadata for one generated report file."""
    filename: str
    format: str           # html | pdf | csv | json
    size_bytes: int
    download_url: str     # e.g. /api/reports/{run_id}/download/{filename}


class ReportsResponse(BaseModel):
    """Response for GET /api/reports/{run_id}."""
    run_id: str
    api_name: Optional[str]
    report_count: int
    reports: List[ReportFile]
