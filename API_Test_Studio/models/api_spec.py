"""
models/api_spec.py
==================
Dataclass representing a parsed API specification document.

This model is the top-level container produced by the api_parser module
(Phase 2+).  It holds metadata about the specification file itself plus a
collection of discovered endpoints.

No business logic lives here — this is a pure data carrier.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from constants.spec_formats import SpecFormat


@dataclass
class ApiSpec:
    """
    Top-level model for a parsed API specification.

    Attributes:
        spec_id:         Unique identifier generated at parse time.
        title:           API title extracted from the spec (e.g. "Pet Store API").
        version:         API version string extracted from the spec (e.g. "1.0.0").
        description:     Optional long-form description from the spec.
        spec_format:     Format of the source file (OpenAPI 3, Swagger 2, …).
        source_file:     Absolute path to the uploaded spec file.
        base_url:        Default server / base URL declared in the spec.
        endpoints:       Ordered list of discovered endpoint models.
        tags:            Tag names declared in the spec (used for grouping).
        extra_metadata:  Any additional top-level fields not mapped above.
        parsed_at:       UTC timestamp of when parsing was completed.
    """

    spec_id: str
    title: str
    version: str
    spec_format: SpecFormat
    source_file: str

    description: Optional[str] = None
    base_url: Optional[str] = None
    endpoints: List["Endpoint"] = field(default_factory=list)  # type: ignore[name-defined]
    tags: List[str] = field(default_factory=list)
    extra_metadata: Dict[str, object] = field(default_factory=dict)
    parsed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.parsed_at is None:
            from datetime import timezone
            self.parsed_at = datetime.now(tz=timezone.utc)

    @property
    def endpoint_count(self) -> int:
        """Return the number of endpoints in this specification."""
        return len(self.endpoints)

    def __repr__(self) -> str:
        return (
            f"ApiSpec(id={self.spec_id!r}, title={self.title!r}, "
            f"format={self.spec_format.value!r}, endpoints={self.endpoint_count})"
        )
