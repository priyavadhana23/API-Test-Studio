"""
api_parser/parser_factory.py
=============================
Registry and auto-selection engine for all concrete spec parsers.

Design — Strategy Pattern with self-registration:
    ParserFactory maintains an ordered list of ISpecParser instances.
    To add a new format (Postman, RAML, …), create the parser class and
    call ``ParserFactory.register(MyParser())``.  Nothing else changes.

Responsibilities:
    - Hold the list of registered parsers
    - Expose ``get_parser(filepath)`` which calls ``can_parse()`` on each
      registered parser in registration order and returns the first match
    - Raise ``UnsupportedSpecFormatError`` when no parser claims the file

Usage:
    from api_parser.parser_factory import ParserFactory

    parser = ParserFactory.get_parser("uploaded_specs/petstore.yaml")
    spec   = parser.parse("uploaded_specs/petstore.yaml")
"""

from typing import List

from exceptions.parser_exceptions import UnsupportedSpecFormatError
from interfaces.parser_interface import ISpecParser
from utilities.logger import get_logger

logger = get_logger(__name__)


class ParserFactory:
    """
    Registry of all available ``ISpecParser`` implementations.

    All methods are class-level so no instantiation is required.

    The factory is pre-populated with the built-in parsers at import time
    (see bottom of this module).  External code may call
    ``ParserFactory.register()`` to add more parsers at runtime.

    Class attributes:
        _parsers: Ordered list of registered ``ISpecParser`` instances.
                  Parsers are tried in registration order; the first one
                  whose ``can_parse()`` returns ``True`` is selected.
    """

    _parsers: List[ISpecParser] = []

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    @classmethod
    def register(cls, parser: ISpecParser) -> None:
        """
        Add a parser implementation to the registry.

        Parsers are tried in the order they are registered.  Register
        more-specific parsers before more-general ones.

        Args:
            parser: An instance of a class that implements ``ISpecParser``.

        Raises:
            TypeError: If *parser* does not implement ``ISpecParser``.
        """
        if not isinstance(parser, ISpecParser):
            raise TypeError(
                f"Expected an ISpecParser instance, got {type(parser).__name__}."
            )
        cls._parsers.append(parser)
        logger.debug("Parser registered: %s", parser.parser_name)

    @classmethod
    def unregister_all(cls) -> None:
        """
        Remove all registered parsers.

        Intended for use in tests only.
        """
        cls._parsers.clear()
        logger.debug("All parsers unregistered.")

    @classmethod
    def registered_parsers(cls) -> List[str]:
        """Return the names of all currently registered parsers."""
        return [p.parser_name for p in cls._parsers]

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #

    @classmethod
    def get_parser(cls, filepath: str) -> ISpecParser:
        """
        Select and return the first parser capable of handling *filepath*.

        Iterates over registered parsers in order, calling ``can_parse()``
        on each.  Returns the first match.

        Args:
            filepath: Path to the spec file to be parsed.

        Returns:
            An ``ISpecParser`` instance ready to parse the file.

        Raises:
            UnsupportedSpecFormatError: If no registered parser claims
                                         the file.
        """
        logger.debug(
            "Selecting parser for '%s' from %d registered parsers.",
            filepath,
            len(cls._parsers),
        )

        for parser in cls._parsers:
            try:
                if parser.can_parse(filepath):
                    logger.info(
                        "Parser selected: %s for file '%s'.",
                        parser.parser_name,
                        filepath,
                    )
                    return parser
            except Exception as exc:
                # A parser's can_parse() must never raise — but be defensive
                logger.warning(
                    "Parser '%s' raised an unexpected error during can_parse(): %s",
                    parser.parser_name,
                    exc,
                )

        supported = [p.parser_name for p in cls._parsers]
        raise UnsupportedSpecFormatError(
            format_hint=filepath,
            supported=supported,
        )


# ---------------------------------------------------------------------------
# Default parser registrations
# ---------------------------------------------------------------------------
# Import here (bottom of module) to avoid circular imports.
# Registration order matters: OpenAPI 3 is checked before Swagger 2 because
# some tools write both "openapi" and "swagger" keys; we prefer the newer spec.

from api_parser.openapi_parser import OpenApiParser   # noqa: E402
from api_parser.swagger_parser import SwaggerParser   # noqa: E402

ParserFactory.register(OpenApiParser())
ParserFactory.register(SwaggerParser())
