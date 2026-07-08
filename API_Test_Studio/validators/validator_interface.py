"""
validators/validator_interface.py
====================================
Re-exports the canonical ``IValidator`` ABC from the project-wide interfaces
package so that all validators in this package use a single local import path.

Also exports ``ValidationResult`` from ``validation_utils`` so callers
need only one import:

    from validators.validator_interface import IValidator, ValidationResult

The authoritative ABC definition lives in:
    interfaces/validator_interface.py

The ValidationResult dataclass lives in:
    validators/validation_utils.py
"""

from interfaces.validator_interface import IValidator       # noqa: F401
from validators.validation_utils import ValidationResult   # noqa: F401

__all__ = ["IValidator", "ValidationResult"]
