"""
api_parser/swagger_parser.py
=============================
Concrete parser for Swagger 2.0 specifications (JSON or YAML).

Swagger 2.0 reference: https://swagger.io/specification/v2/

Responsibilities:
    - Implement the ISpecParser interface
    - Accept a Swagger 2.0 file and convert it into ApiSpec + Endpoint models
    - Extract every field listed in the Phase 2 spec:
        title, version, base_url, paths, methods, summaries, descriptions,
        tags, parameters (path/query/header/cookie/body), required flags,
        data types, defaults, enums, request bodies, content types,
        security requirements, responses (status codes, schemas, examples)
    - Validate required Swagger 2.0 structural fields before parsing
    - Raise custom parser exceptions — never generic exceptions

Swagger 2.0 document structure reminder:
    {
      "swagger": "2.0",
      "info": { "title": ..., "version": ... },
      "host": "...",
      "basePath": "/",
      "schemes": ["https"],
      "paths": {
        "/users": {
          "get": { "parameters": [...], "responses": {...}, ... }
        }
      },
      "definitions": { ... },
      "securityDefinitions": { ... },
      "security": [...]
    }
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from constants.app_constants import ParameterLocation
from constants.http_methods import HttpMethod
from constants.spec_formats import SpecFormat
from exceptions.parser_exceptions import InvalidSpecStructureError, SpecParseError
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

# HTTP methods that Swagger 2.0 / OpenAPI support at path-item level
_HTTP_METHODS = {m.value.lower() for m in HttpMethod}


class SwaggerParser(ISpecParser):
    """
    Parses Swagger 2.0 specification files into the internal ``ApiSpec`` model.

    This class is registered with ``ParserFactory`` and selected automatically
    when ``detect_spec_format`` returns ``SpecFormat.SWAGGER_2``.

    It should never be instantiated directly by application code —
    use ``ParserManager`` instead.
    """

    # ------------------------------------------------------------------ #
    # ISpecParser interface
    # ------------------------------------------------------------------ #

    @property
    def parser_name(self) -> str:
        return "Swagger 2.0 Parser"

    def can_parse(self, filepath: str) -> bool:
        """
        Return ``True`` if the file looks like a Swagger 2.0 document.

        Performs a lightweight content inspection — loads the file and
        checks for the ``"swagger": "2.x"`` key.  Returns ``False`` on
        any read or parse error so the factory can try another parser.

        Args:
            filepath: Path to the candidate spec file.

        Returns:
            ``True`` if this parser should handle the file.
        """
        try:
            data, _ = load_spec_file(filepath)
            version = str(data.get("swagger", ""))
            return version.startswith("2")
        except Exception:
            return False

    def parse(self, filepath: str) -> ApiSpec:
        """
        Parse a Swagger 2.0 file and return a populated ``ApiSpec``.

        Args:
            filepath: Absolute or relative path to the ``.json`` / ``.yaml``
                      Swagger 2.0 file.

        Returns:
            A fully populated ``ApiSpec`` instance.

        Raises:
            SpecFileNotFoundError:     If the file does not exist.
            SpecParseError:            If the file is not valid JSON/YAML.
            InvalidSpecStructureError: If required Swagger fields are absent.
        """
        logger.info("Parsing Swagger 2.0 spec: %s", Path(filepath).name)

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

        host: str = data.get("host", "")
        base_path: str = data.get("basePath", "/").rstrip("/")
        schemes: List[str] = data.get("schemes", ["https"])
        scheme = schemes[0] if schemes else "https"
        base_url: Optional[str] = f"{scheme}://{host}{base_path}" if host else None

        global_tags: List[str] = [
            t.get("name", "") for t in data.get("tags", [])
            if isinstance(t, dict)
        ]

        # ── 5. Global security definitions & requirements ─────────────
        security_definitions: Dict[str, Any] = data.get("securityDefinitions", {})
        global_security: List[Dict[str, Any]] = data.get("security", [])

        # ── 6. Parse paths → endpoints ────────────────────────────────
        paths: Dict[str, Any] = data.get("paths", {})
        endpoints: List[Endpoint] = []
        total_params = 0

        for path_str, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Path-level shared parameters (inherited by all operations)
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
                    security_definitions=security_definitions,
                    global_security=global_security,
                )
                endpoints.append(endpoint)
                total_params += len(endpoint.parameters)

        logger.info(
            "Swagger 2.0 parse complete: %d endpoints, %d parameters extracted from '%s'.",
            len(endpoints),
            total_params,
            Path(filepath).name,
        )

        return ApiSpec(
            spec_id=generate_id("spec_"),
            title=title,
            version=version,
            description=description,
            spec_format=SpecFormat.SWAGGER_2,
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
        Assert that the document has the minimum required Swagger 2.0 fields.

        Args:
            data:     Parsed spec document.
            filepath: Original file path (for error messages).

        Raises:
            InvalidSpecStructureError: On any structural problem.
        """
        if "swagger" not in data:
            raise InvalidSpecStructureError(filepath, "swagger", "Missing 'swagger' version key.")

        swagger_version = str(data.get("swagger", ""))
        if not swagger_version.startswith("2"):
            raise InvalidSpecStructureError(
                filepath, "swagger",
                f"Expected Swagger version '2.x', found '{swagger_version}'.",
            )

        if "info" not in data:
            raise InvalidSpecStructureError(filepath, "info", "Missing required 'info' object.")

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

        logger.debug("Swagger 2.0 structure validation passed for: %s", filepath)

    # ------------------------------------------------------------------ #
    # Operation parsing
    # ------------------------------------------------------------------ #

    def _parse_operation(
        self,
        path: str,
        method: str,
        operation: Dict[str, Any],
        path_level_params: List[Dict[str, Any]],
        security_definitions: Dict[str, Any],
        global_security: List[Dict[str, Any]],
    ) -> Endpoint:
        """
        Convert a single Swagger 2.0 operation object into an ``Endpoint``.

        Args:
            path:               URL path string (e.g. ``"/users/{id}"``).
            method:             HTTP method in uppercase (e.g. ``"GET"``).
            operation:          The operation dict from the spec.
            path_level_params:  Parameters declared at the path-item level.
            security_definitions: Full ``securityDefinitions`` dict.
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
        # Merge path-level params with operation-level params;
        # operation-level takes precedence (overrides by name+location).
        merged_params = self._merge_parameters(
            path_level_params, operation.get("parameters", [])
        )
        parameters: List[Parameter] = []
        request_body: Optional[RequestBody] = None

        for param_dict in merged_params:
            in_location = param_dict.get("in", "").lower()

            if in_location == "body":
                request_body = self._parse_body_parameter(param_dict)
            elif in_location == "formdata":
                request_body = self._parse_formdata_parameter(param_dict, merged_params)
            else:
                param = self._parse_parameter(param_dict)
                if param:
                    parameters.append(param)

        # ── Responses ─────────────────────────────────────────────────
        responses: Dict[int, ExpectedResponse] = self._parse_responses(
            operation.get("responses", {})
        )

        # ── Security ──────────────────────────────────────────────────
        op_security = operation.get("security")  # None means "use global"
        security_labels = extract_security_labels(
            op_security, global_security, security_definitions
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
            Merged list with duplicates resolved.
        """
        result: Dict[tuple, Dict[str, Any]] = {}
        for p in path_params:
            key = (p.get("name", ""), p.get("in", ""))
            result[key] = p
        for p in op_params:
            key = (p.get("name", ""), p.get("in", ""))
            result[key] = p  # operation-level wins
        return list(result.values())

    @staticmethod
    def _parse_parameter(param: Dict[str, Any]) -> Optional[Parameter]:
        """
        Convert a Swagger 2.0 parameter object (non-body) to a ``Parameter``.

        Args:
            param: Raw parameter dict from the spec.

        Returns:
            A ``Parameter`` instance, or ``None`` if the param is malformed.
        """
        name: Optional[str] = param.get("name")
        if not name:
            return None

        in_location = normalise_location(param.get("in", "query"))

        # Swagger 2.0 puts type directly on the parameter for simple types
        schema: Dict[str, Any] = param.get("schema", {})
        data_type: str = (
            param.get("type")
            or schema.get("type", "string")
        )
        enum_values: List[Any] = param.get("enum") or schema.get("enum", [])
        default: Any = param.get("default", schema.get("default"))
        example: Any = param.get("example")

        return Parameter(
            name=name,
            location=in_location,
            data_type=data_type,
            required=bool(param.get("required", in_location == ParameterLocation.PATH)),
            description=param.get("description"),
            default=default,
            example=example,
            enum_values=enum_values if isinstance(enum_values, list) else [],
            schema=schema,
        )

    @staticmethod
    def _parse_body_parameter(param: Dict[str, Any]) -> RequestBody:
        """
        Convert a Swagger 2.0 ``in: body`` parameter to a ``RequestBody``.

        Args:
            param: Raw body parameter dict.

        Returns:
            Populated ``RequestBody`` instance.
        """
        schema: Dict[str, Any] = param.get("schema", {})
        # Swagger 2.0 body params don't declare content-type here;
        # the spec-level ``consumes`` list does.  We default to JSON.
        content_types: Dict[str, Dict[str, Any]] = {
            "application/json": schema,
        }
        return RequestBody(
            required=bool(param.get("required", False)),
            content_types=content_types,
            description=param.get("description"),
        )

    @staticmethod
    def _parse_formdata_parameter(
        param: Dict[str, Any],
        all_params: List[Dict[str, Any]],
    ) -> RequestBody:
        """
        Synthesise a ``RequestBody`` from one or more ``in: formData`` params.

        Args:
            param:      The current formData parameter (used for description).
            all_params: Full parameter list (to gather all formData fields).

        Returns:
            Populated ``RequestBody`` instance.
        """
        form_fields: Dict[str, Any] = {}
        required_fields: List[str] = []

        for p in all_params:
            if p.get("in", "").lower() == "formdata" and p.get("name"):
                fname = p["name"]
                form_fields[fname] = {
                    "type": p.get("type", "string"),
                    "description": p.get("description", ""),
                }
                if p.get("required", False):
                    required_fields.append(fname)

        schema: Dict[str, Any] = {
            "type": "object",
            "properties": form_fields,
        }
        if required_fields:
            schema["required"] = required_fields

        content_type = "multipart/form-data"
        return RequestBody(
            required=bool(required_fields),
            content_types={content_type: schema},
            description=param.get("description"),
        )

    # ------------------------------------------------------------------ #
    # Response helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_responses(
        responses_dict: Dict[str, Any]
    ) -> Dict[int, ExpectedResponse]:
        """
        Convert the Swagger 2.0 ``responses`` object into ``ExpectedResponse`` instances.

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

            schema: Dict[str, Any] = response_obj.get("schema", {})
            content_types: Dict[str, Dict[str, Any]] = {}
            if schema:
                content_types["application/json"] = schema

            headers: Dict[str, Any] = response_obj.get("headers", {})

            result[status_code] = ExpectedResponse(
                status_code=status_code,
                description=response_obj.get("description"),
                content_types=content_types,
                headers=headers,
            )

        return result
