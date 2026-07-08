"""
web_dashboard/backend/schemas/specs.py
=======================================
Pydantic response models for the /api/specifications endpoints.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Returned after a successful spec file upload."""
    status: str = Field(..., examples=["uploaded"])
    filename: str = Field(..., examples=["petstore.yaml"])
    detected_format: str = Field(..., examples=["OpenAPI 3.x"])
    file_size_bytes: int = Field(..., examples=[12480])
    upload_path: str = Field(..., examples=["uploaded_specs/petstore.yaml"])

    model_config = {"json_schema_extra": {"example": {
        "status": "uploaded",
        "filename": "petstore.yaml",
        "detected_format": "OpenAPI 3.x",
        "file_size_bytes": 12480,
        "upload_path": "uploaded_specs/petstore.yaml",
    }}}


class SpecSummary(BaseModel):
    """One row in the specification list."""
    filename: str
    detected_format: str
    file_size_bytes: int
    upload_timestamp: str   # ISO-8601 mtime
    supported: bool = True


class SpecListResponse(BaseModel):
    """Response for GET /api/specifications."""
    total: int
    specifications: List[SpecSummary]


class SpecDetailResponse(BaseModel):
    """Full metadata for one parsed specification."""
    filename: str
    detected_format: str
    file_size_bytes: int
    api_name: str
    api_version: str
    base_url: Optional[str]
    description: Optional[str]
    endpoint_count: int
    tags: List[str]
    parsed_at: Optional[str]
