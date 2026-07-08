"""
web_dashboard/backend/routers/specs.py
========================================
Specification file endpoints.

    POST /api/specifications/upload       — upload a spec file
    GET  /api/specifications              — list all uploaded specs
    GET  /api/specifications/{filename}   — parse and return spec metadata
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from web_dashboard.backend.config.settings import Settings, get_settings
from web_dashboard.backend.schemas.specs import (
    SpecDetailResponse,
    SpecListResponse,
    SpecSummary,
    UploadResponse,
)

router = APIRouter(prefix="/api/specifications", tags=["Specifications"])

# Accepted MIME types and extensions
_ALLOWED_EXTENSIONS = {".json", ".yaml", ".yml"}
_ALLOWED_MIME = {
    "application/json",
    "application/x-yaml",
    "application/yaml",
    "text/yaml",
    "text/x-yaml",
    "text/plain",          # many clients send YAML as text/plain
    "application/octet-stream",  # fallback when client omits content-type
}

import sys as _sys
from pathlib import Path as _Path
_root = str(_Path(__file__).resolve().parent.parent.parent.parent)
if _root not in _sys.path:
    _sys.path.insert(0, _root)

from utilities.logger import get_logger
logger = get_logger("web_dashboard.backend.specs")


def _specs_dir(settings: Settings) -> Path:
    p = settings.project_root / "uploaded_specs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _detect_format(filename: str) -> str:
    """Return a human-readable format label based on file extension only."""
    from constants.spec_formats import SpecFormatMeta
    ext = Path(filename).suffix.lower()
    fmts = SpecFormatMeta.from_extension(ext)
    if not fmts:
        return "Unknown"
    # Will be resolved precisely after parsing; return first candidate label
    from constants.spec_formats import SpecFormatMeta as M
    return M.display_name(fmts[0])


# ---------------------------------------------------------------------------
# POST /api/specifications/upload
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a specification file",
    description=(
        "Upload a Swagger 2.0 or OpenAPI 3.x specification in JSON or YAML "
        "format.  The file is stored in `uploaded_specs/` and can then be "
        "referenced by filename when triggering a test run."
    ),
)
async def upload_specification(
    file: UploadFile = File(..., description="Swagger/OpenAPI JSON or YAML file"),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    # ── Extension check ───────────────────────────────────────────────
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{suffix}'. "
                f"Accepted: {sorted(_ALLOWED_EXTENSIONS)}"
            ),
        )

    # ── Read & size guard (16 MB max) ─────────────────────────────────
    content = await file.read()
    if len(content) > 16 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Specification file must be ≤ 16 MB.",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # ── Safe filename (no path traversal) ────────────────────────────
    safe_name = Path(file.filename or "spec").name
    dest = _specs_dir(settings) / safe_name

    dest.write_bytes(content)
    logger.info(
        "Spec uploaded: '%s'  (%d bytes)", safe_name, len(content)
    )

    return UploadResponse(
        status="uploaded",
        filename=safe_name,
        detected_format=_detect_format(safe_name),
        file_size_bytes=len(content),
        upload_path=f"uploaded_specs/{safe_name}",
    )


# ---------------------------------------------------------------------------
# GET /api/specifications
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=SpecListResponse,
    summary="List all uploaded specifications",
)
def list_specifications(
    settings: Settings = Depends(get_settings),
) -> SpecListResponse:
    specs_dir = _specs_dir(settings)
    items: List[SpecSummary] = []

    for f in sorted(specs_dir.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in _ALLOWED_EXTENSIONS:
            continue
        if f.name.startswith("."):
            continue

        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()
        items.append(SpecSummary(
            filename=f.name,
            detected_format=_detect_format(f.name),
            file_size_bytes=f.stat().st_size,
            upload_timestamp=mtime,
            supported=True,
        ))

    return SpecListResponse(total=len(items), specifications=items)


# ---------------------------------------------------------------------------
# GET /api/specifications/{filename}
# ---------------------------------------------------------------------------

@router.get(
    "/{filename}",
    response_model=SpecDetailResponse,
    summary="Parse and return specification metadata",
    description="Runs ParserManager on the file and returns full API metadata.",
)
def get_specification(
    filename: str,
    settings: Settings = Depends(get_settings),
) -> SpecDetailResponse:
    # Guard against path traversal
    safe_name = Path(filename).name
    spec_path = _specs_dir(settings) / safe_name

    if not spec_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Specification file '{safe_name}' not found.",
        )
    if spec_path.suffix.lower() not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File '{safe_name}' is not a supported spec format.",
        )

    try:
        from api_parser import ParserManager
        manager = ParserManager()
        spec = manager.parse(str(spec_path))
    except Exception as exc:
        logger.error("Spec parse error for '%s': %s", safe_name, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse specification: {exc}",
        )

    from constants.spec_formats import SpecFormatMeta
    fmt_label = SpecFormatMeta.display_name(spec.spec_format)

    return SpecDetailResponse(
        filename=safe_name,
        detected_format=fmt_label,
        file_size_bytes=spec_path.stat().st_size,
        api_name=spec.title,
        api_version=spec.version,
        base_url=spec.base_url,
        description=spec.description,
        endpoint_count=spec.endpoint_count,
        tags=spec.tags,
        parsed_at=spec.parsed_at.isoformat() if spec.parsed_at else None,
    )
