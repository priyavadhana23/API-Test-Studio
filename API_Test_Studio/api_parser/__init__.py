"""
api_parser package
==================
Phase 2 — Generic API Specification Parser for API Test Studio.

Public API (the only import the rest of the framework needs):

    from api_parser import ParserManager

    manager = ParserManager()
    spec    = manager.parse("uploaded_specs/petstore.yaml")

Internal modules (not for direct use outside this package):

    parser_utils    — Low-level file loading, format detection, $ref resolution
    swagger_parser  — Swagger 2.0 concrete parser
    openapi_parser  — OpenAPI 3.x concrete parser
    parser_factory  — Registry and auto-selection of parsers
    parser_manager  — Public facade / orchestrator

To add support for a new format (Postman, RAML, …) in a future phase:
    1. Create ``api_parser/postman_parser.py`` implementing ``ISpecParser``.
    2. Register it: ``ParserFactory.register(PostmanParser())``.
    3. No other files need to change.
"""

from api_parser.parser_manager import ParserManager
from api_parser.parser_factory import ParserFactory

__all__ = ["ParserManager", "ParserFactory"]
