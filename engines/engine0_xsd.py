"""Engine 0: Native XSD validation."""

from pathlib import Path
from typing import List, Optional
from lxml import etree

from config import Config, get_config
from engines.base import (
    BatchData,
    Engine,
    Finding,
    Severity,
    ValidationEngine,
)


class XSDValidationEngine(ValidationEngine):
    """
    Engine 0: Native XSD validation.

    Validates XML against Contractberichtstructuur.xsd using lxml.

    Error codes:
    - E0-001: XSD schema validation error
    - E0-002: Structure/hierarchy error (element not expected at position)
    - E0-003: Required element missing
    - E0-004: Invalid element (unknown element)
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self._schema: Optional[etree.XMLSchema] = None

    @property
    def engine_type(self) -> Engine:
        return Engine.XSD

    def _load_schema(self) -> Optional[etree.XMLSchema]:
        """Load and cache the XSD schema."""
        if self._schema is not None:
            return self._schema

        xsd_path = self.config.contractbericht_xsd_path
        if not xsd_path.exists():
            return None

        try:
            schema_doc = etree.parse(str(xsd_path))
            self._schema = etree.XMLSchema(schema_doc)
            return self._schema
        except Exception:
            return None

    def validate(self, batch: BatchData) -> List[Finding]:
        """Validate batch against XSD schema."""
        findings = []

        if not self.config.enable_xsd_validation:
            return findings

        schema = self._load_schema()
        if schema is None:
            # Schema not available, skip validation
            return findings

        # Validate source XML if available
        if batch.source_file:
            findings.extend(self._validate_file(batch.source_file, schema))

        return findings

    def _validate_file(self, file_path: str, schema: etree.XMLSchema) -> List[Finding]:
        """Validate a single XML file against the schema."""
        findings = []

        try:
            doc = etree.parse(file_path)

            if not schema.validate(doc):
                for error in schema.error_log:
                    finding = self._create_finding_from_xsd_error(error)
                    if finding:
                        findings.append(finding)

        except etree.XMLSyntaxError as e:
            # XML parsing error
            findings.append(Finding(
                severity=Severity.FOUT,
                engine=Engine.XSD,
                code="E0-001",
                regeltype="xml_syntax_fout",
                contract="",
                branche="",
                entiteit="",
                label="",
                waarde="",
                omschrijving=f"XML syntax fout: {str(e)}",
                verwacht="Geldige XML syntax",
                bron="XML parser",
                regel=getattr(e, 'lineno', None),
            ))
        except Exception as e:
            # Other errors
            findings.append(Finding(
                severity=Severity.FOUT,
                engine=Engine.XSD,
                code="E0-001",
                regeltype="xsd_validatie_fout",
                contract="",
                branche="",
                entiteit="",
                label="",
                waarde="",
                omschrijving=f"XSD validatie fout: {str(e)}",
                verwacht="Conform XSD schema",
                bron="Contractberichtstructuur.xsd",
            ))

        return findings

    def _create_finding_from_xsd_error(self, error) -> Optional[Finding]:
        """Convert XSD validation error to Finding."""
        message = str(error.message) if error.message else ""

        # Determine error code based on message content
        if "element is not expected" in message.lower():
            code = "E0-002"
            regeltype = "hierarchie_fout"
            omschrijving = self._parse_hierarchy_error(message)
        elif "missing child element" in message.lower():
            code = "E0-003"
            regeltype = "verplicht_element_ontbreekt"
            omschrijving = self._parse_missing_element_error(message)
        elif "not valid" in message.lower() or "invalid" in message.lower():
            code = "E0-004"
            regeltype = "ongeldig_element"
            omschrijving = message
        else:
            code = "E0-001"
            regeltype = "xsd_validatie_fout"
            omschrijving = message

        # Extract entity from error context
        entiteit = self._extract_entity_from_error(error)

        return Finding(
            severity=Severity.FOUT,
            engine=Engine.XSD,
            code=code,
            regeltype=regeltype,
            contract="",  # Will be determined from context if possible
            branche="",
            entiteit=entiteit,
            label="",
            waarde="",
            omschrijving=omschrijving,
            verwacht="Conform XSD schema",
            bron="Contractberichtstructuur.xsd",
            regel=error.line if hasattr(error, 'line') else None,
        )

    def _parse_hierarchy_error(self, message: str) -> str:
        """Parse hierarchy error message into Dutch description."""
        # Example: "Element 'VP': This element is not expected."
        # -> "Entiteit VP staat op verkeerde positie in de hierarchie"

        import re
        match = re.search(r"Element '(\w+)'", message)
        if match:
            element = match.group(1)
            if len(element) == 2:
                return (
                    f"Entiteit {element} staat op verkeerde positie in de hierarchie. "
                    f"Controleer of de entiteit onder de juiste parent staat."
                )

        return f"Hierarchie fout: {message}"

    def _parse_missing_element_error(self, message: str) -> str:
        """Parse missing element error into Dutch description."""
        import re
        match = re.search(r"Missing child element\(s\)\. Expected.+?'(\w+)'", message)
        if match:
            element = match.group(1)
            return f"Verplicht element '{element}' ontbreekt"

        return f"Verplicht element ontbreekt: {message}"

    def _extract_entity_from_error(self, error) -> str:
        """Extract entity type from error message or path."""
        message = str(error.message) if error.message else ""

        import re
        # Try to find 2-char entity name in message
        match = re.search(r"Element '([A-Z]{2})'", message)
        if match:
            return match.group(1)

        # Try to extract from path if available
        if hasattr(error, 'path') and error.path:
            parts = str(error.path).split('/')
            for part in reversed(parts):
                # Remove array notation like [1]
                clean = re.sub(r'\[\d+\]', '', part)
                if len(clean) == 2 and clean.isupper():
                    return clean

        return ""
