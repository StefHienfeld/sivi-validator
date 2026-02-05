"""Encoding and Data Quality Validation Module.

Validates XML encoding and data quality aspects:
- UTF-8 encoding validation
- BOM (Byte Order Mark) detection
- Whitespace normalization issues
- Special character validation
- Control character detection
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from engines.base import (
    BatchData,
    ContractData,
    Engine,
    EntityData,
    Finding,
    Severity,
    ValidationEngine,
)
from config import Config, get_config


@dataclass
class EncodingIssue:
    """Represents an encoding or data quality issue."""

    issue_type: str
    severity: Severity
    description: str
    location: Optional[str] = None
    line_number: Optional[int] = None
    char_position: Optional[int] = None
    found_value: Optional[str] = None
    suggested_fix: Optional[str] = None


class EncodingValidator:
    """
    Validates file encoding and character content.

    Checks:
    - UTF-8 encoding compliance
    - BOM presence (warning)
    - Invalid UTF-8 sequences
    - Control characters
    - Special characters that may cause issues
    """

    # UTF-8 BOM bytes
    UTF8_BOM = b"\xef\xbb\xbf"

    # Control characters that shouldn't appear in XML (except tab, CR, LF)
    CONTROL_CHARS = set(range(0x00, 0x09)) | set(range(0x0B, 0x0D)) | set(range(0x0E, 0x20))

    # Characters that might indicate encoding issues
    REPLACEMENT_CHAR = "\ufffd"  # Unicode replacement character
    SUSPICIOUS_CHARS = {
        "\x00": "null byte",
        "\ufffd": "replacement character (encoding error)",
        "\ufffe": "invalid Unicode",
        "\uffff": "invalid Unicode",
    }

    def __init__(self):
        pass

    def validate_file(self, file_path: Path) -> List[EncodingIssue]:
        """Validate a file's encoding."""
        issues = []

        try:
            # Read raw bytes first
            with open(file_path, "rb") as f:
                raw_content = f.read()

            # Check for BOM
            if raw_content.startswith(self.UTF8_BOM):
                issues.append(EncodingIssue(
                    issue_type="bom_detected",
                    severity=Severity.WAARSCHUWING,
                    description="UTF-8 BOM (Byte Order Mark) gevonden aan begin van bestand",
                    location="byte 0-2",
                    suggested_fix="Verwijder BOM voor betere compatibiliteit",
                ))

            # Check for valid UTF-8
            try:
                content = raw_content.decode("utf-8")
            except UnicodeDecodeError as e:
                issues.append(EncodingIssue(
                    issue_type="invalid_utf8",
                    severity=Severity.FOUT,
                    description=f"Ongeldige UTF-8 encoding op positie {e.start}: {e.reason}",
                    char_position=e.start,
                    found_value=raw_content[max(0, e.start - 5):e.end + 5].hex(),
                    suggested_fix="Converteer bestand naar UTF-8 encoding",
                ))
                # Try with error replacement for further checks
                content = raw_content.decode("utf-8", errors="replace")

            # Check for control characters
            for i, char in enumerate(content):
                code = ord(char)
                if code in self.CONTROL_CHARS:
                    line_num = content[:i].count("\n") + 1
                    issues.append(EncodingIssue(
                        issue_type="control_character",
                        severity=Severity.FOUT,
                        description=f"Ongeldig controlekarakter (0x{code:02x}) gevonden",
                        line_number=line_num,
                        char_position=i,
                        found_value=f"0x{code:02x}",
                        suggested_fix="Verwijder controlekarakter",
                    ))
                    # Limit findings
                    if len([i for i in issues if i.issue_type == "control_character"]) >= 10:
                        break

            # Check for suspicious characters
            for char, desc in self.SUSPICIOUS_CHARS.items():
                if char in content:
                    pos = content.find(char)
                    line_num = content[:pos].count("\n") + 1
                    issues.append(EncodingIssue(
                        issue_type="suspicious_character",
                        severity=Severity.WAARSCHUWING,
                        description=f"Verdacht karakter gevonden: {desc}",
                        line_number=line_num,
                        char_position=pos,
                        found_value=f"U+{ord(char):04X}",
                    ))

            # Check XML declaration encoding
            xml_decl_match = re.match(
                r'<\?xml[^>]*encoding=["\']([^"\']+)["\']',
                content[:200]
            )
            if xml_decl_match:
                declared_encoding = xml_decl_match.group(1).upper()
                if declared_encoding not in ("UTF-8", "UTF8"):
                    issues.append(EncodingIssue(
                        issue_type="encoding_mismatch",
                        severity=Severity.WAARSCHUWING,
                        description=f"XML declaratie specificeert '{declared_encoding}', verwacht UTF-8",
                        found_value=declared_encoding,
                        suggested_fix="Wijzig encoding declaratie naar UTF-8",
                    ))

        except OSError as e:
            issues.append(EncodingIssue(
                issue_type="file_error",
                severity=Severity.FOUT,
                description=f"Kan bestand niet lezen: {e}",
            ))

        return issues

    def validate_string(self, value: str, context: str = "") -> List[EncodingIssue]:
        """Validate a string value for encoding issues."""
        issues = []

        # Check for replacement character (indicates encoding error)
        if self.REPLACEMENT_CHAR in value:
            issues.append(EncodingIssue(
                issue_type="encoding_error",
                severity=Severity.FOUT,
                description="Unicode vervangingskarakter gevonden (encoding fout)",
                location=context,
                found_value=value[:50] if len(value) > 50 else value,
            ))

        # Check for control characters
        for i, char in enumerate(value):
            code = ord(char)
            if code in self.CONTROL_CHARS:
                issues.append(EncodingIssue(
                    issue_type="control_character",
                    severity=Severity.FOUT,
                    description=f"Controlekarakter in waarde",
                    location=context,
                    char_position=i,
                    found_value=f"0x{code:02x}",
                ))
                break  # One is enough

        return issues


class DataQualityValidator:
    """
    Validates data quality aspects of values.

    Checks:
    - Whitespace normalization
    - Leading/trailing whitespace
    - Multiple consecutive spaces
    - Non-breaking spaces
    - Placeholder values (TEST, XXX, etc.)
    - Truncation indicators
    """

    # Common placeholder patterns
    PLACEHOLDER_PATTERNS = [
        re.compile(r"^(TEST|TEMP|TODO|XXX|DUMMY|N\.?V\.?T\.?|NVT|ONBEKEND|UNKNOWN)$", re.IGNORECASE),
        re.compile(r"^[X]{3,}$", re.IGNORECASE),
        re.compile(r"^[0]{5,}$"),
        re.compile(r"^\*+$"),
        re.compile(r"^\.{3,}$"),
    ]

    # Truncation indicators
    TRUNCATION_PATTERNS = [
        re.compile(r"\.\.\.$"),  # ends with ...
        re.compile(r"\[TRUNCATED\]", re.IGNORECASE),
        re.compile(r"\.{2,}$"),  # ends with multiple dots
    ]

    # Fields that commonly contain placeholder values
    PLACEHOLDER_FIELDS = {
        "NAAM", "ANAAM", "VNAAM", "ADRES", "STRAAT", "PLAATS",
        "EMAIL", "TELEFOON", "TELNR", "MOBIEL", "WEBSITE",
    }

    def __init__(self):
        self.encoding_validator = EncodingValidator()

    def validate_value(
        self,
        value: str,
        field_name: str,
        entity_type: str = "",
    ) -> List[EncodingIssue]:
        """Validate a single field value for data quality issues."""
        issues = []

        if not value:
            return issues

        # Check for encoding issues first
        issues.extend(self.encoding_validator.validate_string(
            value, f"{entity_type}_{field_name}" if entity_type else field_name
        ))

        # Check for leading/trailing whitespace
        if value != value.strip():
            issues.append(EncodingIssue(
                issue_type="whitespace_padding",
                severity=Severity.WAARSCHUWING,
                description="Waarde bevat voorloop- of naloop-spaties",
                location=f"{entity_type}_{field_name}" if entity_type else field_name,
                found_value=repr(value[:30]),
                suggested_fix="Verwijder overbodige spaties",
            ))

        # Check for multiple consecutive spaces
        if "  " in value:
            issues.append(EncodingIssue(
                issue_type="multiple_spaces",
                severity=Severity.INFO,
                description="Waarde bevat meerdere opeenvolgende spaties",
                location=f"{entity_type}_{field_name}" if entity_type else field_name,
                found_value=value[:50],
            ))

        # Check for non-breaking spaces
        if "\u00a0" in value:  # Non-breaking space
            issues.append(EncodingIssue(
                issue_type="non_breaking_space",
                severity=Severity.WAARSCHUWING,
                description="Waarde bevat non-breaking space (U+00A0)",
                location=f"{entity_type}_{field_name}" if entity_type else field_name,
                found_value=value[:50],
                suggested_fix="Vervang non-breaking spaces door normale spaties",
            ))

        # Check for placeholder values (only in relevant fields)
        field_suffix = field_name.split("_")[-1] if "_" in field_name else field_name
        if field_suffix.upper() in self.PLACEHOLDER_FIELDS:
            for pattern in self.PLACEHOLDER_PATTERNS:
                if pattern.match(value):
                    issues.append(EncodingIssue(
                        issue_type="placeholder_value",
                        severity=Severity.WAARSCHUWING,
                        description="Waarde lijkt een placeholder te zijn",
                        location=f"{entity_type}_{field_name}" if entity_type else field_name,
                        found_value=value,
                        suggested_fix="Vervang placeholder door werkelijke waarde",
                    ))
                    break

        # Check for truncation indicators
        for pattern in self.TRUNCATION_PATTERNS:
            if pattern.search(value):
                issues.append(EncodingIssue(
                    issue_type="truncation_indicator",
                    severity=Severity.WAARSCHUWING,
                    description="Waarde lijkt afgekapt te zijn",
                    location=f"{entity_type}_{field_name}" if entity_type else field_name,
                    found_value=value[-30:] if len(value) > 30 else value,
                ))
                break

        return issues


class EncodingValidationEngine(ValidationEngine):
    """
    Validation engine for encoding and data quality checks.

    Error codes:
    - EE-001: UTF-8 encoding fout
    - EE-002: BOM gedetecteerd
    - EE-003: Controlekarakter gevonden
    - EE-004: Whitespace probleem
    - EE-005: Placeholder waarde
    - EE-006: Afgekapte waarde
    - EE-007: Verdacht karakter
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.encoding_validator = EncodingValidator()
        self.quality_validator = DataQualityValidator()

    @property
    def engine_type(self) -> Engine:
        return Engine.SCHEMA  # Categorize with schema validation

    def validate(self, batch: BatchData) -> List[Finding]:
        """Validate batch for encoding and data quality issues."""
        findings = []

        # Validate file encoding if source file is available
        if batch.source_file:
            file_path = Path(batch.source_file)
            if file_path.exists():
                findings.extend(self._validate_file_encoding(file_path))

        # Validate data quality for each contract
        for contract in batch.contracts:
            findings.extend(self._validate_contract(contract))

        return findings

    def _validate_file_encoding(self, file_path: Path) -> List[Finding]:
        """Validate file-level encoding issues."""
        findings = []
        issues = self.encoding_validator.validate_file(file_path)

        for issue in issues:
            code, regeltype = self._map_issue_to_code(issue.issue_type)
            findings.append(Finding(
                severity=issue.severity,
                engine=Engine.SCHEMA,
                code=code,
                regeltype=regeltype,
                contract="FILE",
                branche="",
                entiteit="",
                label=issue.location or "",
                waarde=issue.found_value or "",
                omschrijving=issue.description,
                verwacht=issue.suggested_fix or "",
                bron="encoding_validation",
                regel=issue.line_number,
            ))

        return findings

    def _validate_contract(self, contract: ContractData) -> List[Finding]:
        """Validate data quality for a contract."""
        findings = []

        for entity in contract.get_all_entities_recursive():
            for attr_name, attr_value in entity.attributes.items():
                issues = self.quality_validator.validate_value(
                    attr_value, attr_name, entity.entity_type
                )

                for issue in issues:
                    code, regeltype = self._map_issue_to_code(issue.issue_type)
                    findings.append(Finding(
                        severity=issue.severity,
                        engine=Engine.SCHEMA,
                        code=code,
                        regeltype=regeltype,
                        contract=contract.contract_nummer,
                        branche=contract.branche,
                        entiteit=entity.entity_type,
                        label=attr_name,
                        waarde=issue.found_value or attr_value[:50],
                        omschrijving=issue.description,
                        verwacht=issue.suggested_fix or "",
                        bron="data_quality_validation",
                        regel=entity.line_number,
                    ))

        return findings

    def _map_issue_to_code(self, issue_type: str) -> Tuple[str, str]:
        """Map issue type to error code and regeltype."""
        mapping = {
            "invalid_utf8": ("EE-001", "encoding_fout"),
            "encoding_error": ("EE-001", "encoding_fout"),
            "bom_detected": ("EE-002", "bom_gedetecteerd"),
            "control_character": ("EE-003", "controlekarakter"),
            "whitespace_padding": ("EE-004", "whitespace_probleem"),
            "multiple_spaces": ("EE-004", "whitespace_probleem"),
            "non_breaking_space": ("EE-004", "whitespace_probleem"),
            "placeholder_value": ("EE-005", "placeholder_waarde"),
            "truncation_indicator": ("EE-006", "afgekapte_waarde"),
            "suspicious_character": ("EE-007", "verdacht_karakter"),
            "encoding_mismatch": ("EE-001", "encoding_fout"),
            "file_error": ("EE-001", "bestand_fout"),
        }
        return mapping.get(issue_type, ("EE-000", "onbekend"))


def validate_file_encoding(file_path: Path) -> List[EncodingIssue]:
    """Convenience function to validate file encoding."""
    validator = EncodingValidator()
    return validator.validate_file(file_path)


def validate_string_quality(value: str, field_name: str = "") -> List[EncodingIssue]:
    """Convenience function to validate string quality."""
    validator = DataQualityValidator()
    return validator.validate_value(value, field_name)
