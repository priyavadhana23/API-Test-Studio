"""
api_parser/parser_utils.py
==========================
Low-level, format-agnostic utilities shared by all concrete parsers.

Responsibilities:
    - Load a raw spec file (JSON or YAML) from disk into a Python dict
    - Detect the specification format by inspecting content keys
    - Resolve inline $ref pointers within the same document
    - Extract security scheme labels from an operation's security block
    - Normalise parameter location strings to ParameterLocation constants
    - Safely extract nested dict values without raising KeyError

No parser-specific business logic lives here.  These are pure helper
functions that any parser may call.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from constants.app_constants import ParameterLocation
from constants.spec_formats import SpecFormat
from exceptions.parser_exceptions import (
    SpecFileNotFoundError,
    SpecParseError,
    UnsupportedSpecFormatError,
)
from utilities.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def load_spec_file(filepath: str) -> Tuple[Dict[str, Any], str]:
    """
    Load a spec file from disk and return its parsed content plus the
    detected file type (``"json"`` or ``"yaml"``).

    Args:
        filepath: Path to the spec file.

    Returns:
        A tuple ``(parsed_dict, file_type)`` where *file_type* is
        ``"json"`` or ``"yaml"``.

    Raises:
        SpecFileNotFoundError: If the file does not exist.
        SpecParseError:        If the file cannot be parsed as JSON or YAML.
    """
    path = Path(filepath)
    if not path.is_file():
        raise SpecFileNotFoundError(str(filepath))

    logger.debug("Loading spec file: %s", path)
    raw = path.read_text(encoding="utf-8")

    extension = path.suffix.lower()

    # Try JSON first for .json files; YAML for everything else
    if extension == ".json":
        try:
            data = json.loads(raw)
            logger.debug("Parsed as JSON: %s", path.name)
            return data, "json"
        except json.JSONDecodeError as exc:
            raise SpecParseError(str(filepath), f"Invalid JSON — {exc}") from exc

    # .yaml / .yml / unknown extension: try YAML (YAML is a superset of JSON)
    try:
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise SpecParseError(
                str(filepath),
                "Top-level YAML content is not a mapping (expected a dict).",
            )
        logger.debug("Parsed as YAML: %s", path.name)
        return data, "yaml"
    except yaml.YAMLError as exc:
        raise SpecParseError(str(filepath), f"Invalid YAML — {exc}") from exc


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def detect_spec_format(data: Dict[str, Any], filepath: str) -> SpecFormat:
    """
    Inspect the parsed spec document and determine its format.

    Detection rules (applied in order):
        1. ``"openapi"`` key present AND value starts with ``"3"``
           → ``SpecFormat.OPENAPI_3``
        2. ``"swagger"`` key present AND value starts with ``"2"``
           → ``SpecFormat.SWAGGER_2``
        3. ``"info"`` + ``"paths"`` present but no version key
           → best-effort ``SpecFormat.OPENAPI_3``
        4. Anything else → ``UnsupportedSpecFormatError``

    Args:
        data:     Parsed spec document as a Python dict.
        filepath: Original file path (for error messages only).

    Returns:
        The detected ``SpecFormat`` enum member.

    Raises:
        UnsupportedSpecFormatError: If the format cannot be identified.
    """
    openapi_version: Optional[str] = data.get("openapi")
    swagger_version: Optional[str] = data.get("swagger")

    if openapi_version and str(openapi_version).startswith("3"):
        logger.debug("Detected format: OpenAPI 3.x (openapi=%s)", openapi_version)
        return SpecFormat.OPENAPI_3

    if swagger_version and str(swagger_version).startswith("2"):
        logger.debug("Detected format: Swagger 2.0 (swagger=%s)", swagger_version)
        return SpecFormat.SWAGGER_2

    # Edge case: some Swagger 2.0 files have ``"swagger": "2.0"`` as a string
    # but the version check above handles that.  Anything unrecognised is rejected.
    supported = [SpecFormat.OPENAPI_3.value, SpecFormat.SWAGGER_2.value]
    hint = f"openapi={openapi_version!r}" if openapi_version else \
           f"swagger={swagger_version!r}" if swagger_version else "no version key"
    raise UnsupportedSpecFormatError(hint, supported)


# ---------------------------------------------------------------------------
# $ref resolver (single-document, local only)
# ---------------------------------------------------------------------------

def resolve_ref(ref_string: str, root_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve a local JSON ``$ref`` pointer within the same document.

    Only ``#/…`` (same-document) references are supported.  External file
    or URL references are returned as-is (not resolved).

    Args:
        ref_string: The ``$ref`` value, e.g.
                    ``"#/components/schemas/User"``.
        root_doc:   The root parsed spec dictionary to traverse.

    Returns:
        The resolved sub-document at the referenced path, or an empty dict
        if the path cannot be followed.
    """
    if not ref_string.startswith("#/"):
        logger.debug("Skipping external $ref: %s", ref_string)
        return {}

    parts = ref_string.lstrip("#/").split("/")
    node: Any = root_doc
    for part in parts:
        # JSON Pointer encoding: ~1 → /  and  ~0 → ~
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            logger.debug("$ref path not found: %s (failed at '%s')", ref_string, part)
            return {}

    return node if isinstance(node, dict) else {}


def dereference(obj: Any, root_doc: Dict[str, Any]) -> Any:
    """
    Recursively resolve all ``$ref`` entries in *obj*.

    Args:
        obj:      Any Python value (dict, list, or scalar).
        root_doc: The root parsed spec dictionary used for resolution.

    Returns:
        A new object with all ``$ref`` entries replaced by their targets.
    """
    if isinstance(obj, dict):
        if "$ref" in obj:
            return dereference(resolve_ref(obj["$ref"], root_doc), root_doc)
        return {k: dereference(v, root_doc) for k, v in obj.items()}
    if isinstance(obj, list):
        return [dereference(item, root_doc) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Parameter location normalisation
# ---------------------------------------------------------------------------

def normalise_location(location: str) -> str:
    """
    Map an OpenAPI/Swagger parameter location string to the project's
    ``ParameterLocation`` constant.

    OpenAPI uses lowercase ``"query"``, ``"path"``, ``"header"``,
    ``"cookie"``.  Any unrecognised value is passed through unchanged.

    Args:
        location: Raw ``"in"`` value from the spec.

    Returns:
        A ``ParameterLocation`` constant string.
    """
    mapping: Dict[str, str] = {
        "query":  ParameterLocation.QUERY,
        "path":   ParameterLocation.PATH,
        "header": ParameterLocation.HEADER,
        "cookie": ParameterLocation.COOKIE,
        "body":   ParameterLocation.BODY,
        "formdata": ParameterLocation.BODY,
    }
    return mapping.get(location.lower(), location.lower())


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

def extract_security_labels(
    operation_security: Optional[List[Dict[str, Any]]],
    global_security: Optional[List[Dict[str, Any]]],
    security_schemes: Optional[Dict[str, Any]],
) -> List[str]:
    """
    Return a human-readable list of security scheme names that apply to
    an operation.

    The effective security for an operation is:
        - The operation-level ``security`` block if present, otherwise
        - The global ``security`` block.

    An empty list ``[]`` on the operation level means "no auth required"
    (security override to none).

    Args:
        operation_security: The ``security`` list from an individual
                            operation (may be ``None``).
        global_security:    The top-level ``security`` list from the spec.
        security_schemes:   The ``securityDefinitions`` (Swagger 2) or
                            ``components/securitySchemes`` (OpenAPI 3) dict.

    Returns:
        List of security scheme name strings (e.g. ``["BearerAuth"]``).
        Returns ``["none"]`` when the effective security is empty.
    """
    effective = operation_security if operation_security is not None else (global_security or [])

    if not effective:
        return ["none"]

    labels: List[str] = []
    for entry in effective:
        if isinstance(entry, dict):
            labels.extend(entry.keys())

    return labels if labels else ["none"]


# ---------------------------------------------------------------------------
# Safe dict access
# ---------------------------------------------------------------------------

def safe_get(
    data: Dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    """
    Safely retrieve a value from a nested dictionary.

    Example::

        safe_get(spec, "info", "title", default="Untitled")

    Args:
        data:    Root dictionary.
        *keys:   Ordered sequence of keys to traverse.
        default: Value returned when any key is missing.

    Returns:
        The value at the key path, or *default*.
    """
    node: Any = data
    for key in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(key, default)
        if node is default:
            return default
    return node


def build_operation_id(method: str, path: str, declared_id: Optional[str] = None) -> str:
    """
    Return a stable, unique operation identifier for an endpoint.

    Priority:
        1. Use *declared_id* from the spec if it is a non-blank string.
        2. Generate one from ``METHOD_path_segments``, e.g.:
               ``GET /users/{id}``  →  ``GET_users_{id}``
               ``POST /orders``     →  ``POST_orders``

    The generated form is uppercase method + underscore-joined path
    segments.  Leading slashes and empty segments are stripped.
    The result is safe to use as a Python identifier, a filename
    component, and a dictionary key.

    Args:
        method:      HTTP method string (e.g. ``"GET"``).
        path:        URL path template (e.g. ``"/users/{id}"``).
        declared_id: The ``operationId`` value from the spec, if present.

    Returns:
        A non-empty operation ID string.

    Examples::

        build_operation_id("GET",  "/users/{id}", "getUserById")
        # → "getUserById"

        build_operation_id("GET",  "/users/{id}", None)
        # → "GET_users_{id}"

        build_operation_id("POST", "/orders", "")
        # → "POST_orders"
    """
    if declared_id and declared_id.strip():
        return declared_id.strip()

    # Strip leading slash, split on "/", filter empty segments, rejoin
    segments = [seg for seg in path.lstrip("/").split("/") if seg]
    slug = "_".join(segments) if segments else "root"
    return f"{method.upper()}_{slug}"


def coerce_status_code(raw: Any) -> Optional[int]:
    """
    Convert a response status code key to an integer.

    OpenAPI specs often use string keys like ``"200"`` or ``"default"``.
    Non-numeric keys (``"default"``, ``"1XX"``) are returned as ``None``.

    Args:
        raw: Status code value (string or int).

    Returns:
        Integer status code, or ``None`` for non-numeric values.
    """
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
