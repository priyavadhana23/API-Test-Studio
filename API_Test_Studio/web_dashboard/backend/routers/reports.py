"""
web_dashboard/backend/routers/reports.py
==========================================
Report file endpoints.

    GET  /api/reports/{run_id}                       — list available reports
    GET  /api/reports/{run_id}/download/{filename}   — download a report file
"""

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from web_dashboard.backend.config.settings import Settings, get_settings
from web_dashboard.backend.schemas.reports import ReportFile, ReportsResponse

router = APIRouter(prefix="/api/reports", tags=["Reports"])

import sys as _sys
_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _root not in _sys.path:
    _sys.path.insert(0, _root)

from utilities.logger import get_logger
logger = get_logger("web_dashboard.backend.reports")

_FORMAT_MAP = {
    ".html": "html",
    ".pdf":  "pdf",
    ".csv":  "csv",
    ".json": "json",
}


def _open_db(settings: Settings):
    from database.database_manager import DatabaseManager
    db = DatabaseManager(db_path=settings.db_path, history_dir=settings.history_dir)
    db.init_db()
    return db


# ---------------------------------------------------------------------------
# GET /api/reports/{run_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{run_id}",
    response_model=ReportsResponse,
    summary="List generated reports for a run",
    description=(
        "Returns metadata and download URLs for every report file that was "
        "generated for the given run.  Does NOT regenerate reports."
    ),
)
def list_reports(
    run_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportsResponse:
    # Verify run exists
    db = _open_db(settings)
    try:
        run_row = db.get_run(run_id)
    finally:
        db.close()

    if run_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )

    # Scan reports directory for files whose name contains the short run_id
    reports_dir = Path(settings.reports_dir)
    short_id = run_id[:8]
    files: List[ReportFile] = []

    if reports_dir.exists():
        for f in sorted(reports_dir.iterdir()):
            if not f.is_file():
                continue
            fmt = _FORMAT_MAP.get(f.suffix.lower())
            if fmt is None:
                continue
            # Include all reports in the directory — for a single-run workspace
            # there is only one set.  When multiple runs exist, future work can
            # filter by run_id embedded in the filename.
            files.append(ReportFile(
                filename=f.name,
                format=fmt,
                size_bytes=f.stat().st_size,
                download_url=f"/api/reports/{run_id}/download/{f.name}",
            ))

    logger.info(
        "Reports listed for run '%s' — %d file(s).", run_id[:16], len(files)
    )

    return ReportsResponse(
        run_id=run_id,
        api_name=run_row.api_name,
        report_count=len(files),
        reports=files,
    )


# ---------------------------------------------------------------------------
# GET /api/reports/{run_id}/download/{filename}
# ---------------------------------------------------------------------------

@router.get(
    "/{run_id}/download/{filename}",
    summary="Download a report file",
    description="Streams a generated report file to the client.",
    response_class=FileResponse,
)
def download_report(
    run_id: str,
    filename: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    # Verify run
    db = _open_db(settings)
    try:
        if db.get_run(run_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run '{run_id}' not found.",
            )
    finally:
        db.close()

    # Guard against path traversal
    safe_name = Path(filename).name
    file_path = Path(settings.reports_dir) / safe_name

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report file '{safe_name}' not found.",
        )

    ext = file_path.suffix.lower()
    media_types = {
        ".html": "text/html",
        ".pdf":  "application/pdf",
        ".csv":  "text/csv",
        ".json": "application/json",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    logger.info(
        "Report download: '%s' for run '%s'", safe_name, run_id[:16]
    )

    return FileResponse(
        path=str(file_path),
        filename=safe_name,
        media_type=media_type,
    )
