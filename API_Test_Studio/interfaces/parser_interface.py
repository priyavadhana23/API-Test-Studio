"""
interfaces/parser_interface.py
================================
Abstract base class that every API specification parser must implement.

Why this matters:
    Phase 2 will ship parsers for OpenAPI 3, Swagger 2, Postman Collection,
    and RAML.  Each parser is a different class, but the executor, generator,
    and every other module that consumes a parsed spec should never know or
    care which parser produced it.  They work against this interface only.

Contract:
    Any class that inherits ``ISpecParser`` MUST implement:
        - can_parse()   → decide if this parser handles the given file
        - parse()       → parse the file and return an ApiSpec

Usage (Phase 2):
    from interfaces.parser_interface import ISpecParser
    from models import ApiSpec

    class OpenApi3Parser(ISpecParser):
        def can_parse(self, filepath: str) -> bool:
            ...
        def parse(self, filepath: str) -> ApiSpec:
            ...
"""

from abc import ABC, abstractmethod

from models.api_spec import ApiSpec


class ISpecParser(ABC):
    """
    Interface (abstract base class) for all API specification parsers.

    Concrete implementations:
        - OpenApi3Parser   (Phase 2)
        - Swagger2Parser   (Phase 2)
        - PostmanParser    (Phase 2)
        - RamlParser       (Phase 2)

    All parsers are discovered and delegated to by a ``ParserFactory``
    which calls ``can_parse()`` on each registered parser to find the
    right one for a given file.
    """

    @abstractmethod
    def can_parse(self, filepath: str) -> bool:
        """
        Return ``True`` if this parser is capable of handling the given file.

        This is called by ``ParserFactory`` before ``parse()`` to select
        the correct parser.  Implementations should inspect the file
        extension and/or the file's content (e.g. check for ``"openapi"``
        key in a YAML file) — but must NOT raise exceptions; return
        ``False`` instead.

        Args:
            filepath: Absolute or relative path to the spec file.

        Returns:
            ``True`` if this parser should handle the file, ``False``
            otherwise.
        """

    @abstractmethod
    def parse(self, filepath: str) -> ApiSpec:
        """
        Parse the specification file and return a populated ``ApiSpec``.

        Args:
            filepath: Absolute or relative path to the spec file.

        Returns:
            A fully populated ``ApiSpec`` instance.

        Raises:
            SpecFileNotFoundError:    If the file does not exist.
            SpecParseError:           If the file cannot be parsed.
            InvalidSpecStructureError: If required fields are missing.
        """

    @property
    def parser_name(self) -> str:
        """
        Human-readable name for this parser, used in logs and error messages.

        Override in subclasses to provide a meaningful name, e.g.
        ``"OpenAPI 3.x Parser"``.  Defaults to the class name.
        """
        return self.__class__.__name__
