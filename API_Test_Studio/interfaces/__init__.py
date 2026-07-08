"""
interfaces package
==================
Abstract base classes (interfaces) that define the contracts every
pluggable component in API Test Studio must honour.

By programming against these interfaces, the rest of the codebase
is completely decoupled from any specific implementation.  Swapping
parsers, validators, or generators requires only registering a new
concrete class — no changes to calling code.

Available interfaces:
    ISpecParser          - Contract for all API spec parsers
    IValidator           - Contract for all response validators
    ITestCaseGenerator   - Contract for all test case generators

Usage:
    from interfaces import ISpecParser, IValidator, ITestCaseGenerator
"""

from interfaces.parser_interface import ISpecParser
from interfaces.validator_interface import IValidator
from interfaces.generator_interface import ITestCaseGenerator

__all__ = [
    "ISpecParser",
    "IValidator",
    "ITestCaseGenerator",
]
