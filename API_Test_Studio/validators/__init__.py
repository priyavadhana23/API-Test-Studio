"""
validators package
==================
Phase 5 — Universal Response Validation Engine for API Test Studio.

Public API (the only import the rest of the framework needs):

    from validators import ValidationManager

    manager = ValidationManager()
    validation_results = manager.validate_all(test_cases, execution_results)

Internal modules (not for direct use outside this package):

    validation_utils          — ValidationResult dataclass, response_data builder,
                                operator evaluator, assertion result factories
    validator_interface       — Re-export of IValidator + ValidationResult
    status_code_validator     — HTTP status code assertion evaluation
    header_validator          — Content-Type and response header checks
    response_time_validator   — Response time threshold checks
    json_validator            — JSON structure, not-empty, field extraction
    schema_validator          — JSON Schema validation via jsonschema (Level 2)
    exact_response_validator  — Exact field value / template matching (Level 3)
    business_rule_validator   — Pluggable named rule engine
    validation_manager        — Orchestrator and public facade

To add a new validator (e.g. XMLValidator, GraphQLValidator) without
modifying existing code:
    1. Create the class implementing IValidator in this package.
    2. manager.register_validator(MyNewValidator())
    3. No other code changes required.
"""

from validators.validation_manager import ValidationManager
from validators.validator_interface import IValidator, ValidationResult

__all__ = ["ValidationManager", "IValidator", "ValidationResult"]
