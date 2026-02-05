"""Validation engines for SIVI AFD XML Validator."""

from .base import (
    Severity,
    Engine,
    Finding,
    ContractData,
    EntityData,
    BatchData,
    ValidationEngine,
    ValidationCertificate,
    ValidationResult,
)

# Import new engines for gap analysis implementation
from .engine_xpath import (
    XPathRule,
    XPathRuleLibrary,
    XPathEvaluator,
    XPathBusinessRulesEngine,
    get_xpath_engine,
)

from .engine_encoding import (
    EncodingValidator,
    DataQualityValidator,
    EncodingValidationEngine,
    validate_file_encoding,
    validate_string_quality,
)

from .engine_final import (
    FinalValidationEngine,
    SIVICertificationIntegration,
    SIVICertificationResult,
)

__all__ = [
    # Base classes
    "Severity",
    "Engine",
    "Finding",
    "ContractData",
    "EntityData",
    "BatchData",
    "ValidationEngine",
    "ValidationCertificate",
    "ValidationResult",
    # XPath engine
    "XPathRule",
    "XPathRuleLibrary",
    "XPathEvaluator",
    "XPathBusinessRulesEngine",
    "get_xpath_engine",
    # Encoding engine
    "EncodingValidator",
    "DataQualityValidator",
    "EncodingValidationEngine",
    "validate_file_encoding",
    "validate_string_quality",
    # Final engine
    "FinalValidationEngine",
    "SIVICertificationIntegration",
    "SIVICertificationResult",
]
