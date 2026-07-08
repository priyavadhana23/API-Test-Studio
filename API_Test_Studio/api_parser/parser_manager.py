"""
api_parser/parser_manager.py
=============================
Public facade for the entire parsing subsystem.

ParserManager is the only class the rest of the framework ever calls.
It hides the factory, the concrete parsers, the validation, and the
summary printer behind a single clean method: ``parse()``.

Responsibilities:
    - Accept a spec file path
    - Delegate format detection and parser selection to ParserFactory
    - Call the selected parser's ``parse()`` method
    - Log every important step
    - Print a structured console summary after a successful parse
    - Re-raise parser exceptions for callers to handle

Usage:
    from api_parser.parser_manager import ParserManager

    manager = ParserManager()
    spec    = manager.parse("uploaded_specs/petstore.yaml")
    # spec is a fully populated ApiSpec instance
"""

from pathlib import Path
from typing import Optional

from constants.app_constants import LogMessages
from exceptions.parser_exceptions import ParserError
from models.api_spec import ApiSpec
from models.endpoint import Endpoint
from utilities.logger import get_logger

from api_parser.parser_factory import ParserFactory

logger = get_logger(__name__)


class ParserManager:
    """
    Orchestrator for the API specification parsing pipeline.

    The rest of the framework interacts with this class only — it never
    directly instantiates ``SwaggerParser``, ``OpenApiParser``, or any
    other concrete parser.

    Example::

        manager = ParserManager()
        spec = manager.parse("uploaded_specs/petstore.yaml")
        print(spec.title, spec.endpoint_count)
    """

    def __init__(self) -> None:
        self._factory = ParserFactory

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def parse(self, filepath: str) -> ApiSpec:
        """
        Parse a specification file and return a populated ``ApiSpec``.

        Steps:
            1. Verify the file exists (delegates to the selected parser).
            2. Select the correct parser via ``ParserFactory``.
            3. Parse the file into an ``ApiSpec`` model.
            4. Log and print a structured summary.

        Args:
            filepath: Absolute or relative path to the spec file.

        Returns:
            A fully populated ``ApiSpec`` instance.

        Raises:
            SpecFileNotFoundError:     If the file does not exist.
            UnsupportedSpecFormatError: If no parser handles the format.
            SpecParseError:            If the file content is invalid.
            InvalidSpecStructureError: If required spec fields are missing.
        """
        filepath = str(Path(filepath).resolve())

        logger.info(LogMessages.SPEC_PARSE_START, filepath)
        logger.debug(
            "Registered parsers: %s", self._factory.registered_parsers()
        )

        try:
            # ── 1. Select parser ──────────────────────────────────────
            parser = self._factory.get_parser(filepath)
            logger.info(
                "Format detected. Using parser: %s", parser.parser_name
            )

            # ── 2. Parse ──────────────────────────────────────────────
            spec: ApiSpec = parser.parse(filepath)

            # ── 3. Log success ────────────────────────────────────────
            logger.info(
                LogMessages.SPEC_PARSE_SUCCESS, spec.endpoint_count
            )
            logger.debug("ApiSpec produced: %r", spec)

            # ── 4. Print summary to console ───────────────────────────
            self._print_summary(spec)

            return spec

        except ParserError:
            # Re-raise parser exceptions unchanged so the caller can handle them
            raise
        except Exception as exc:
            logger.error(LogMessages.SPEC_PARSE_ERROR, exc, exc_info=True)
            raise

    # ------------------------------------------------------------------ #
    # Console summary
    # ------------------------------------------------------------------ #

    @staticmethod
    def _print_summary(spec: ApiSpec) -> None:
        """
        Emit a structured parsing summary through the logger.

        This is the human-readable output required by Phase 2.  It goes
        through the logger (not print) so it respects the configured level
        and appears in both console and file handlers.

        Args:
            spec: The fully parsed ``ApiSpec`` to summarise.
        """
        sep = "-" * 52
        wide_sep = "=" * 52

        logger.info(wide_sep)
        logger.info("  PARSING SUMMARY")
        logger.info(wide_sep)
        logger.info("  API Name    : %s", spec.title)
        logger.info("  Version     : %s", spec.version)
        logger.info("  Format      : %s", spec.spec_format.value)
        logger.info("  Base URL    : %s", spec.base_url or "Not specified")
        if spec.description:
            # Truncate long descriptions for console readability
            desc = spec.description[:120] + "…" if len(spec.description) > 120 else spec.description
            logger.info("  Description : %s", desc)
        logger.info("  Source File : %s", Path(spec.source_file).name)
        logger.info("  Parsed At   : %s", spec.parsed_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                    if spec.parsed_at else "—")
        logger.info(wide_sep)
        logger.info("  Total Endpoints : %d", spec.endpoint_count)
        if spec.tags:
            logger.info("  Tags            : %s", ", ".join(spec.tags))
        logger.info(wide_sep)

        for endpoint in spec.endpoints:
            ParserManager._print_endpoint_summary(endpoint, sep)

        logger.info(wide_sep)
        logger.info("  END OF SUMMARY — %s", spec.title)
        logger.info(wide_sep)

    @staticmethod
    def _print_endpoint_summary(endpoint: Endpoint, sep: str) -> None:
        """
        Emit one endpoint block of the parsing summary.

        Args:
            endpoint: The ``Endpoint`` to summarise.
            sep:      Separator line string.
        """
        # ── Endpoint header ───────────────────────────────────────────
        deprecated_flag = "  [DEPRECATED]" if endpoint.deprecated else ""
        logger.info(sep)
        logger.info(
            "  %s %s%s",
            endpoint.method,
            endpoint.path,
            deprecated_flag,
        )

        if endpoint.summary:
            logger.info("  Summary    : %s", endpoint.summary)
        if endpoint.tags:
            logger.info("  Tags       : %s", ", ".join(endpoint.tags))
        if endpoint.operation_id:
            logger.info("  OperationId: %s", endpoint.operation_id)

        # ── Parameters ───────────────────────────────────────────────
        logger.info("  Parameters : %d", len(endpoint.parameters))
        for param in endpoint.parameters:
            required_label = " (required)" if param.required else ""
            enum_label = f"  enum={param.enum_values}" if param.enum_values else ""
            default_label = f"  default={param.default!r}" if param.default is not None else ""
            logger.info(
                "    • %-20s  in=%-8s  type=%-10s%s%s%s",
                param.name,
                param.location,
                param.data_type,
                required_label,
                enum_label,
                default_label,
            )

        # ── Request body ──────────────────────────────────────────────
        if endpoint.request_body:
            body = endpoint.request_body
            content_label = ", ".join(body.content_types.keys()) or "unspecified"
            required_label = " (required)" if body.required else ""
            logger.info(
                "  Request Body: content-types=[%s]%s",
                content_label,
                required_label,
            )

        # ── Authentication ────────────────────────────────────────────
        security_labels: list = []
        for sec_entry in endpoint.security:
            security_labels.extend(sec_entry.get("schemes", []))
        auth_display = ", ".join(security_labels) if security_labels else "none"
        logger.info("  Auth       : %s", auth_display)

        # ── Responses ─────────────────────────────────────────────────
        if endpoint.responses:
            codes = sorted(endpoint.responses.keys())
            logger.info("  Responses  : %s", ", ".join(str(c) for c in codes))
            for code in codes:
                resp = endpoint.responses[code]
                content_label = (
                    "  [" + ", ".join(resp.content_types.keys()) + "]"
                    if resp.content_types else ""
                )
                desc_label = f"  {resp.description}" if resp.description else ""
                logger.info(
                    "    • %d%s%s",
                    code,
                    content_label,
                    desc_label,
                )
        else:
            logger.info("  Responses  : none declared")
