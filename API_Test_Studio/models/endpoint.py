"""
models/endpoint.py
==================
Dataclasses representing a single API endpoint and its sub-components:
Parameter, RequestBody, and ExpectedResponse.

These models are populated by the api_parser module (Phase 2+).
No business logic — pure data structures only.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from constants.http_methods import HttpMethod
from constants.app_constants import ParameterLocation


@dataclass
class Parameter:
    """
    A single input parameter for an API endpoint.

    Attributes:
        name:         Parameter name as declared in the spec.
        location:     Where the parameter appears (query, path, header, cookie).
        data_type:    JSON Schema data type (string, integer, boolean, …).
        required:     Whether this parameter must be present in the request.
        description:  Human-readable description from the spec.
        default:      Default value if the parameter is omitted.
        example:      Example value from the spec.
        enum_values:  List of allowed values (for enum parameters).
        schema:       Full raw schema object for complex types.
    """

    name: str
    location: str  # Use ParameterLocation constants

    data_type: str = "string"
    required: bool = False
    description: Optional[str] = None
    default: Optional[Any] = None
    example: Optional[Any] = None
    enum_values: List[Any] = field(default_factory=list)
    schema: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"Parameter(name={self.name!r}, in={self.location!r}, "
            f"type={self.data_type!r}, required={self.required})"
        )


@dataclass
class RequestBody:
    """
    The request body definition for an endpoint.

    Attributes:
        required:      Whether a body must be supplied.
        content_types: Mapping of MIME type → JSON Schema (e.g. ``{"application/json": {...}}``).
        description:   Human-readable description from the spec.
        example:       Example request body from the spec.
    """

    required: bool = False
    content_types: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    description: Optional[str] = None
    example: Optional[Any] = None

    def __repr__(self) -> str:
        return (
            f"RequestBody(required={self.required}, "
            f"content_types={list(self.content_types.keys())})"
        )


@dataclass
class ExpectedResponse:
    """
    A declared response for a given HTTP status code.

    Attributes:
        status_code:   HTTP status code integer (e.g. 200, 404).
        description:   Description from the spec (e.g. "Successful response").
        content_types: Mapping of MIME type → JSON Schema for the response body.
        headers:       Declared response headers mapping (name → schema).
    """

    status_code: int
    description: Optional[str] = None
    content_types: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    headers: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"ExpectedResponse(status_code={self.status_code}, description={self.description!r})"


@dataclass
class Endpoint:
    """
    A single API endpoint, combining its path, method, and all parameter
    and response metadata.

    Attributes:
        endpoint_id:      Unique identifier (generated at parse time).
        path:             URL path template (e.g. ``"/users/{id}"``).
        method:           HTTP method (use ``HttpMethod`` enum values).
        summary:          Short summary from the spec.
        description:      Long description from the spec.
        tags:             Tags used to group endpoints.
        operation_id:     Unique operation identifier from the spec.
        parameters:       List of ``Parameter`` instances.
        request_body:     Optional ``RequestBody`` instance.
        responses:        Mapping of status code → ``ExpectedResponse``.
        deprecated:       Whether the endpoint is marked as deprecated.
        security:         Raw security requirements from the spec.
        extra_metadata:   Any additional fields not mapped above.
    """

    endpoint_id: str
    path: str
    method: str  # Use HttpMethod enum values

    summary: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    operation_id: str = ""       # always set; generated as METHOD_path if not in spec
    parameters: List[Parameter] = field(default_factory=list)
    request_body: Optional[RequestBody] = None
    responses: Dict[int, ExpectedResponse] = field(default_factory=dict)
    deprecated: bool = False
    security: List[Dict[str, Any]] = field(default_factory=list)
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        """Return a display-friendly identifier, e.g. ``"GET /users/{id}"``."""
        return f"{self.method.upper()} {self.path}"

    @property
    def required_parameters(self) -> List[Parameter]:
        """Return only the parameters marked as required."""
        return [p for p in self.parameters if p.required]

    @property
    def path_parameters(self) -> List[Parameter]:
        """Return parameters located in the URL path."""
        return [p for p in self.parameters if p.location == ParameterLocation.PATH]

    @property
    def query_parameters(self) -> List[Parameter]:
        """Return parameters located in the query string."""
        return [p for p in self.parameters if p.location == ParameterLocation.QUERY]

    def __repr__(self) -> str:
        return (
            f"Endpoint(id={self.endpoint_id!r}, method={self.method!r}, "
            f"path={self.path!r}, params={len(self.parameters)})"
        )
