"""
api_parser/openapi_parser.py
=============================
Concrete parser for OpenAPI 3.x specifications (JSON or YAML).

OpenAPI 3.x reference: https://spec.openapis.org/oas/v3.0.3

Responsibilities:
    - Implement the ISpecParser interface
    - Accept an OpenAPI 3.x file and convert it into ApiSpec + Endpoint models
    - Extract every field listed in the Phase 2 spec:
        title, version, servers (base_url), paths, methods, summaries,
        descriptions, tags, parameters (path/query/header/cookie), required
        flags, data types, defaults, enums, requestBody (with content-type
        schemas), security requirements, responses (status codes, schemas,
        examples, headers)
    - Validate required OpenAPI 3.x structural fields before parsing
    - Raise custom parser exceptions — never generic exceptions

Key structural differences from Swagger 2.0:
    - ``openapi: "3.x.x"``  (not ``swagger``)
    - ``servers``  instead of  ``host`` + ``basePath`` + ``schemes``
    - ``requestBody``  instead of  ``in: body``  parameter
    - ``components/schemas``  instead of  ``definitions``
    - ``components/securitySchemes``  instead of  ``securityDefinitions``
    - responses have a ``content`` dict mapping MIME → media-type object
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from constants.app_constants import ParameterLocation
from constants.http_methods import HttpMethod
from constants.spec_formats import SpecFormat
from exceptions.parser_exceptions import InvalidSpecStructureError
from interfaces.parser_interface import ISpecParser
from models.api_spec import ApiSpec
from models.endpoint import Endpoint, ExpectedResponse, Parameter, RequestBody
from utilities.common_helpers import generate_id
from utilities.logger import get_logger

from api_parser.parser_utils import (
    build_operation_id,
    coerce_status_code,
    dereference,
    extract_security_labels,
    load_spec_file,
    normalise_location,
    safe_get,
)

logger = get_logger(__name__)

# HTTP methods valid at path-item level in OpenAPI 3.x
_HTTP_METHODS = {m.value.lower() for m in HttpMethod}


class OpenApiParser(ISpecParser):
    """
    Parses OpenAPI 3.x specification files (JSON or YAML) into the internal
    ``ApiSpec`` model.

    This class is registered with ``ParserFactory`` and selected automatically
    when ``detect_spec_format`` returns ``SpecFormat.OPENAPI_3``.

    It should never be instantiated directly by application code —
    use ``ParserManager`` instead.
    """

    # ------------------------------------------------------------------ #
    # ISpecParser interface
    # ------------------------------------------------------------------ #

    @property
    def parser_name(self) -> str:
        return "OpenAPI 3.x Parser"

    def can_parse(self, filepath: str) -> bool:
        """
        Return ``True`` if the file looks like an OpenAPI 3.x document.

        Performs a lightweight content inspection — loads the file and
        checks for the ``"openapi": "3.x"`` key.  Returns ``False`` on
        any read or parse error so the factory can try the next parser.

        Args:
            filepath: Path to the candidate spec file.

        Returns:
            ``True`` if this parser should handle the file.
        """
        try:
            data, _ = load_spec_file(filepath)
            version = str(data.get("openapi", ""))
            return version.startswith("3")
        except Exception:
            return False

    def parse(self, filepath: str) -> ApiSpec:
        """
        Parse an OpenAPI 3.x file and return a populated ``ApiSpec``.

        Args:
            filepath: Absolute or relative path to the ``.json`` / ``.yaml``
                      OpenAPI 3.x file.

        Returns:
            A fully populated ``ApiSpec`` instance.

        Raises:
            SpecFileNotFoundError:     If the file does not exist.
            SpecParseError:            If the file is not valid JSON/YAML.
            InvalidSpecStructureError: If required OpenAPI 3.x fields are absent.
        """
        logger.info("Parsing OpenAPI 3.x spec: %s", Path(filepath).name)

        # ── 1. Load raw document ──────────────────────────────────────
        data, _ = load_spec_file(filepath)

        # ── 2. Validate structure ─────────────────────────────────────
        self._validate(data, filepath)

        # ── 3. Dereference $refs (single-document) ────────────────────
        data = dereference(data, data)

        # ── 4. Extract top-level metadata ─────────────────────────────
        info: Dict[str, Any] = data.get("info", {})
        title: str = info.get("title", "Untitled API")
        version: str = str(info.get("version", "0.0.0"))
        description: Optional[str] = info.get("description")

        # OpenAPI 3 allows multiple servers; use the first as the base URL
        servers: List[Dict[str, Any]] = data.get("servers", [])
        base_url: Optional[str] = None
        if servers and isinstance(servers[0], dict):
            base_url = servers[0].get("url")

        global_tags: List[str] = [
            t.get("name", "") for t in data.get("tags", [])
            if isinstance(t, dict)
        ]

        # ── 5. Security schemes & global requirements ──────────────────
        security_schemes: Dict[str, Any] = safe_get(
            data, "components", "securitySchemes", default={}
        )
        global_security: List[Dict[str, Any]] = data.get("security", [])

        # ── 6. Parse paths → endpoints ────────────────────────────────
        paths: Dict[str, Any] = data.get("paths", {})
        endpoints: List[Endpoint] = []
        total_params = 0

        for path_str, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Path-level shared parameters
            path_level_params: List[Dict[str, Any]] = path_item.get("parameters", [])

            for method_str, operation in path_item.items():
                if method_str.lower() not in _HTTP_METHODS:
                    continue
                if not isinstance(operation, dict):
                    continue

                endpoint = self._parse_operation(
                    path=path_str,
                    method=method_str.upper(),
                    operation=operation,
                    path_level_params=path_level_params,
                    security_schemes=security_schemes,
                    global_security=global_security,
                )
                endpoints.append(endpoint)
                total_params += len(endpoint.parameters)

        logger.info(
            "OpenAPI 3.x parse complete: %d endpoints, %d parameters extracted from '%s'.",
            len(endpoints),
            total_params,
            Path(filepath).name,
        )

        return ApiSpec(
            spec_id=generate_id("spec_"),
            title=title,
            version=version,
            description=description,
            spec_format=SpecFormat.OPENAPI_3,
            source_file=str(Path(filepath).resolve()),
            base_url=base_url,
            endpoints=endpoints,
            tags=global_tags,
        )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def _validate(self, data: Dict[str, Any], filepath: str) -> None:
        """
        Assert that the document has the minimum required OpenAPI 3.x fields.

        Args:
            data:     Parsed spec document.
            filepath: Original file path (for error messages).

        Raises:
            InvalidSpecStructureError: On any structural problem.
        """
        if "openapi" not in data:
            raise InvalidSpecStructureError(
                filepath, "openapi", "Missing 'openapi' version key."
            )

        oa_version = str(data.get("openapi", ""))
        if not oa_version.startswith("3"):
            raise InvalidSpecStructureError(
                filepath, "openapi",
                f"Expected OpenAPI version '3.x', found '{oa_version}'.",
            )

        if "info" not in data:
            raise InvalidSpecStructureError(
                filepath, "info", "Missing required 'info' object."
            )

        if "title" not in data.get("info", {}):
            raise InvalidSpecStructureError(
                filepath, "info.title", "Missing required 'info.title' field."
            )

        if "paths" not in data:
            raise InvalidSpecStructureError(
                filepath, "paths",
                "Missing required 'paths' object.  The spec has no endpoints to parse.",
            )

        if not isinstance(data["paths"], dict):
            raise InvalidSpecStructureError(
                filepath, "paths", "'paths' must be an object (mapping)."
            )

        logger.debug("OpenAPI 3.x structure validation passed for: %s", filepath)

    # ------------------------------------------------------------------ #
    # Operation parsing
    # ------------------------------------------------------------------ #

    def _parse_operation(
        self,
        path: str,
        method: str,
        operation: Dict[str, Any],
        path_level_params: List[Dict[str, Any]],
        security_schemes: Dict[str, Any],
        global_security: List[Dict[str, Any]],
    ) -> Endpoint:
        """
        Convert a single OpenAPI 3.x operation object into an ``Endpoint``.

        Args:
            path:               URL path string (e.g. ``"/users/{id}"``).
            method:             HTTP method in uppercase (e.g. ``"GET"``).
            operation:          The operation dict from the spec.
            path_level_params:  Parameters declared at the path-item level.
            security_schemes:   Full ``components/securitySchemes`` dict.
            global_security:    Top-level ``security`` list.

        Returns:
            Populated ``Endpoint`` instance.
        """
        endpoint_id = generate_id("ep_")
        summary: Optional[str] = operation.get("summary")
        description: Optional[str] = operation.get("description")
        operation_id: str = build_operation_id(
            method, path, operation.get("operationId")
        )
        tags: List[str] = operation.get("tags", [])
        deprecated: bool = bool(operation.get("deprecated", False))

        # ── Parameters ───────────────────────────────────────────────
        merged_params = self._merge_parameters(
            path_level_params, operation.get("parameters", [])
        )
        parameters: List[Parameter] = [
            p for p in (self._parse_parameter(pd) for pd in merged_params)
            if p is not None
        ]

        # ── Request body ─────────────────────────────────────────────
        request_body: Optional[RequestBody] = None
        if "requestBody" in operation:
            request_body = self._parse_request_body(operation["requestBody"])

        # ── Responses ─────────────────────────────────────────────────
        responses: Dict[int, ExpectedResponse] = self._parse_responses(
            operation.get("responses", {})
        )

        # ── Security ──────────────────────────────────────────────────
        op_security = operation.get("security")  # None means "use global"
        security_labels = extract_security_labels(
            op_security, global_security, security_schemes
        )

        return Endpoint(
            endpoint_id=endpoint_id,
            path=path,
            method=method,
            summary=summary,
            description=description,
            operation_id=operation_id,
            tags=tags,
            parameters=parameters,
            request_body=request_body,
            responses=responses,
            deprecated=deprecated,
            security=[{"schemes": security_labels}],
        )

    # ------------------------------------------------------------------ #
    # Parameter helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _merge_parameters(
        path_params: List[Dict[str, Any]],
        op_params: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Merge path-level and operation-level parameter lists.

        Operation-level entries override path-level entries that share
        the same ``(name, in)`` pair.

        Args:
            path_params: Parameters from the path-item level.
            op_params:   Parameters from the individual operation.

        Returns:
            Merged list with duplicates resolved in favour of op_params.
        """
        result: Dict[tuple, Dict[str, Any]] = {}
        for p in path_params:
            key = (p.get("name", ""), p.get("in", ""))
            result[key] = p
        for p in op_params:
            key = (p.get("name", ""), p.get("in", ""))
            result[key] = p
        return list(result.values())

    @staticmethod
    def _parse_parameter(param: Dict[str, Any]) -> Optional[Parameter]:
        """
        Convert an OpenAPI 3.x parameter object into a ``Parameter``.

        OpenAPI 3.x parameters have a ``schema`` sub-object for type
        information, unlike Swagger 2.0 where type is on the param itself.

        Args:
            param: Raw parameter dict from the spec.

        Returns:
            A ``Parameter`` instance, or ``None`` if the param is malformed.
        """
        name: Optional[str] = param.get("name")
        if not name:
            return None

        in_location = normalise_location(param.get("in", "query"))
        schema: Dict[str, Any] = param.get("schema", {})

        data_type: str = schema.get("type", "string")
        enum_values: List[Any] = schema.get("enum", [])
        default: Any = schema.get("default")

        # OpenAPI 3.x: example can be on param or inside schema
        example: Any = param.get("example", schema.get("example"))

        # Path parameters are always required
        required: bool = bool(
            param.get("required", in_location == ParameterLocation.PATH)
        )

        return Parameter(
            name=name,
            location=in_location,
            data_type=data_type,
            required=required,
            description=param.get("description"),
            default=default,
            example=example,
            enum_values=enum_values if isinstance(enum_values, list) else [],
            schema=schema,
        )

    @staticmethod
    def _parse_request_body(request_body_obj: Dict[str, Any]) -> RequestBody:
        """
        Convert an OpenAPI 3.x ``requestBody`` object into a ``RequestBody``.

        Args:
            request_body_obj: The ``requestBody`` dict from the operation.

        Returns:
            Populated ``RequestBody`` instance.
        """
        required: bool = bool(request_body_obj.get("required", False))
        description: Optional[str] = request_body_obj.get("description")

        content: Dict[str, Any] = request_body_obj.get("content", {})
        content_types: Dict[str, Dict[str, Any]] = {}

        # Pick up the first available example from any content-type
        example: Any = None
        for mime_type, media_obj in content.items():
            if not isinstance(media_obj, dict):
                continue
            schema = media_obj.get("schema", {})
            content_types[mime_type] = schema

            if example is None:
                example = media_obj.get("example") or (
                    next(iter(media_obj.get("examples", {}).values()), {}).get("value")
                    if media_obj.get("examples")
                    else None
                )

        return RequestBody(
            required=required,
            content_types=content_types,
            description=description,
            example=example,
        )

    # ------------------------------------------------------------------ #
    # Response helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_responses(
        responses_dict: Dict[str, Any]
    ) -> Dict[int, ExpectedResponse]:
        """
        Convert the OpenAPI 3.x ``responses`` object into ``ExpectedResponse``
        instances.

        OpenAPI 3.x response content is nested under a ``content`` dict
        (keyed by MIME type) rather than a flat ``schema`` field.

        Args:
            responses_dict: Raw responses dict keyed by status code string.

        Returns:
            Dict mapping integer status code → ``ExpectedResponse``.
        """
        result: Dict[int, ExpectedResponse] = {}

        for code_str, response_obj in responses_dict.items():
            status_code = coerce_status_code(code_str)
            if status_code is None:
                continue
            if not isinstance(response_obj, dict):
                continue

            content: Dict[str, Any] = response_obj.get("content", {})
            content_types: Dict[str, Dict[str, Any]] = {}

            for mime_type, media_obj in content.items():
                if isinstance(media_obj, dict):
                    content_types[mime_type] = media_obj.get("schema", {})

            headers: Dict[str, Any] = response_obj.get("headers", {})

            result[status_code] = ExpectedResponse(
                status_code=status_code,
                description=response_obj.get("description"),
                content_types=content_types,
                headers=headers,
            )

        return result
