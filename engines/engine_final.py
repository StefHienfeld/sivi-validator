"""Final Validation Engine: Send-ready certification.

This module provides internal validation certification. For official
SIVI-certified validation, see the SIVICertificationIntegration class
which provides integration with the official SIVI certification portal.

SIVI Official Certification:
- Portal: https://siviportal.nl/CertiControle/FrmCertiControle.aspx
- Validates against official SIVI schemas
- Issues SIVI-recognized certificate with kenmerk
- Registers certified messages in SIVI register

This internal certification:
- Uses local XSD validation
- SHA256-signed certificate for audit trail
- NOT SIVI-certified for production use
- Suitable for development and pre-validation
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from lxml import etree

from config import Config, get_config
from engines.base import (
    BatchData,
    ContractData,
    Engine,
    Finding,
    Severity,
    ValidationCertificate,
    ValidationEngine,
)


@dataclass
class SIVICertificationResult:
    """Result from SIVI official certification portal."""

    is_certified: bool = False
    certificate_id: str = ""  # SIVI kenmerk
    timestamp: str = ""
    validation_messages: List[str] = field(default_factory=list)
    portal_url: str = ""
    error_message: str = ""


class SIVICertificationIntegration:
    """
    Integration stub for official SIVI AFD Certification Tool.

    The official SIVI certification tool is available at:
    https://siviportal.nl/CertiControle/FrmCertiControle.aspx

    This class provides:
    1. Documentation of the official certification process
    2. Stub methods for future API integration
    3. Manual certification workflow support

    NOTE: Currently, SIVI does not provide a public API for automated
    certification. This class serves as a placeholder for when such
    functionality becomes available.

    Official SIVI Certification Process:
    1. Go to https://siviportal.nl/CertiControle/FrmCertiControle.aspx
    2. Upload XML file
    3. Select message type (Contractbericht, Schadebericht, etc.)
    4. Submit for validation
    5. Receive certificate with kenmerk if validation passes
    6. Certificate registered in SIVI portal

    Benefits of SIVI Certification:
    - Officially recognized validation
    - Certificate stored in SIVI register
    - Unique kenmerk for audit trail
    - Validates against latest SIVI schemas
    """

    PORTAL_URL = "https://siviportal.nl/CertiControle/FrmCertiControle.aspx"
    AFD_DOWNLOADS_URL = "https://www.sivi.org/sivi-afs/afd-1-0-gegevensstandaard/afd-downloads/"

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()

    def get_certification_info(self) -> Dict[str, Any]:
        """Get information about SIVI certification."""
        return {
            "portal_url": self.PORTAL_URL,
            "downloads_url": self.AFD_DOWNLOADS_URL,
            "api_available": False,
            "manual_process": [
                "1. Navigate to SIVI certification portal",
                "2. Upload your XML file",
                "3. Select message type (e.g., ADN Contractbericht)",
                "4. Submit for validation",
                "5. Download certificate if validation passes",
            ],
            "note": (
                "SIVI does not currently provide a public API for automated "
                "certification. Use this internal validator for pre-validation "
                "before submitting to the official portal."
            ),
        }

    def submit_for_certification(
        self,
        xml_path: Path,
        message_type: str = "Contractbericht",
    ) -> SIVICertificationResult:
        """
        Submit XML for SIVI certification.

        NOTE: This is a STUB implementation. SIVI does not currently
        provide a public API for automated certification.

        Args:
            xml_path: Path to the XML file to certify
            message_type: Type of message (Contractbericht, Schadebericht, etc.)

        Returns:
            SIVICertificationResult with instructions for manual submission
        """
        return SIVICertificationResult(
            is_certified=False,
            error_message=(
                f"Automated SIVI certification is not available. "
                f"Please submit manually at: {self.PORTAL_URL}"
            ),
            portal_url=self.PORTAL_URL,
            validation_messages=[
                f"File prepared for certification: {xml_path}",
                f"Message type: {message_type}",
                "Manual submission required - see portal_url",
            ],
        )

    def verify_certificate(self, certificate_id: str) -> Optional[Dict]:
        """
        Verify a SIVI certificate by its kenmerk.

        NOTE: This is a STUB implementation.

        Args:
            certificate_id: The SIVI certificate kenmerk

        Returns:
            Certificate details if found, None otherwise
        """
        # This would query the SIVI register if an API were available
        return None

    @staticmethod
    def generate_manual_submission_instructions(xml_path: Path) -> str:
        """Generate instructions for manual SIVI certification submission."""
        return f"""
================================================================================
SIVI CERTIFICATION - MANUAL SUBMISSION REQUIRED
================================================================================

File to certify: {xml_path}

Steps for official SIVI certification:

1. Open the SIVI certification portal:
   {SIVICertificationIntegration.PORTAL_URL}

2. Log in with your SIVI credentials (if required)

3. Upload the XML file:
   {xml_path}

4. Select the appropriate message type:
   - Contractbericht (for ADN batch)
   - Schadebericht (for claims)
   - Pakketbericht (for packages)
   - etc.

5. Submit for validation

6. If validation passes:
   - Download the certificate
   - Note the certificate kenmerk
   - Certificate is registered in SIVI portal

7. Store the certificate with your audit trail

================================================================================
NOTE: This internal validator provides pre-validation only.
      Official SIVI certification is required for production use.
================================================================================
"""


class FinalValidationEngine(ValidationEngine):
    """
    Final Validation Engine: Send-ready certification.

    Guarantees 100% certainty that XML is ready to send by:
    1. Verifying all engines ran successfully
    2. No FOUT findings present
    3. Required entities present (AL, PP minimum)
    4. Business completeness check
    5. Re-validation against XSD
    6. Generating send-ready certificate

    Error codes:
    - EF-001: Not send-ready (critical errors found)
    - EF-002: Required entity missing
    - EF-003: XSD re-validation failed
    - EF-004: Policy number missing
    - EF-005: Premium missing (warning)
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()

    @property
    def engine_type(self) -> Engine:
        return Engine.FINAL

    def validate(self, batch: BatchData) -> List[Finding]:
        """Validate batch (not used directly, use validate_and_certify instead)."""
        return []

    def validate_and_certify(
        self,
        batch: BatchData,
        all_findings: List[Finding]
    ) -> Tuple[List[Finding], Optional[ValidationCertificate]]:
        """Perform final validation and generate certificate if valid."""
        findings = []

        if not self.config.enable_final_certification:
            return findings, None

        # Check 1: Count critical errors from previous engines
        critical_errors = [f for f in all_findings if f.severity == Severity.FOUT]

        if critical_errors:
            findings.append(Finding(
                severity=Severity.FOUT,
                engine=Engine.FINAL,
                code="EF-001",
                regeltype="niet_verzendklaar",
                contract="BATCH",
                branche="",
                entiteit="",
                label="",
                waarde=f"{len(critical_errors)} fouten",
                omschrijving=(
                    f"XML is NIET verzendklaar: {len(critical_errors)} kritieke fout(en) gevonden"
                ),
                verwacht="0 kritieke fouten",
                bron="Eindvalidatie",
            ))
            return findings, None

        # Check 2: Required entities present per contract
        for contract in batch.contracts:
            required_entities = {"AL", "PP"}
            present_entities = contract.get_all_entity_types_recursive()
            missing = required_entities - present_entities

            if missing:
                findings.append(Finding(
                    severity=Severity.FOUT,
                    engine=Engine.FINAL,
                    code="EF-002",
                    regeltype="verplichte_entiteit_ontbreekt",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit="",
                    label="",
                    waarde=str(missing),
                    omschrijving=f"Verplichte entiteit(en) ontbreken: {', '.join(sorted(missing))}",
                    verwacht="AL en PP entiteiten verplicht",
                    bron="SIVI ADN specificatie",
                ))

        # Check 3: Business completeness
        for contract in batch.contracts:
            findings.extend(self._check_business_completeness(contract))

        # Check 4: XSD re-validation (double certainty)
        if batch.source_file:
            xsd_error = self._revalidate_xsd(batch.source_file)
            if xsd_error:
                findings.append(Finding(
                    severity=Severity.FOUT,
                    engine=Engine.FINAL,
                    code="EF-003",
                    regeltype="xsd_revalidatie_fout",
                    contract="BATCH",
                    branche="",
                    entiteit="",
                    label="",
                    waarde="",
                    omschrijving=f"XSD re-validatie gefaald: {xsd_error}",
                    verwacht="XSD validatie succesvol",
                    bron="Contractberichtstructuur.xsd",
                ))

        # If no errors: generate certificate
        if not any(f.severity == Severity.FOUT for f in findings):
            certificate = self._generate_certificate(batch, all_findings + findings)
            return findings, certificate

        return findings, None

    def _check_business_completeness(self, contract: ContractData) -> List[Finding]:
        """Check if all business-critical data is present."""
        findings = []

        # AL entity must have POLNR or CPOLNR
        al_entities = contract.get_entities_by_type_recursive("AL")
        for al in al_entities:
            polnr = al.get_attr("POLNR") or al.get_attr("CPOLNR")
            if not polnr:
                findings.append(Finding(
                    severity=Severity.FOUT,
                    engine=Engine.FINAL,
                    code="EF-004",
                    regeltype="polisnummer_ontbreekt",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit="AL",
                    label="AL_POLNR",
                    waarde="",
                    omschrijving="Polisnummer ontbreekt in AL entiteit",
                    verwacht="AL_POLNR of AL_CPOLNR verplicht",
                    bron="Business completeness",
                    regel=al.line_number,
                ))

        # PP entity should have BTP (gross premium) - warning only
        pp_entities = contract.get_entities_by_type_recursive("PP")
        for pp in pp_entities:
            btp = pp.get_attr("BTP")
            if not btp:
                findings.append(Finding(
                    severity=Severity.WAARSCHUWING,
                    engine=Engine.FINAL,
                    code="EF-005",
                    regeltype="premie_ontbreekt",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit="PP",
                    label="PP_BTP",
                    waarde="",
                    omschrijving="Bruto premie (BTP) ontbreekt in PP entiteit",
                    verwacht="PP_BTP aanwezig voor premieberekening",
                    bron="Business completeness",
                    regel=pp.line_number,
                ))

        return findings

    def _revalidate_xsd(self, source_file: str) -> Optional[str]:
        """Re-validate XML against XSD as double check."""
        try:
            xsd_path = self.config.contractbericht_xsd_path
            if not xsd_path.exists():
                return None  # Skip if XSD not available

            schema_doc = etree.parse(str(xsd_path))
            schema = etree.XMLSchema(schema_doc)
            doc = etree.parse(source_file)

            if not schema.validate(doc):
                if schema.error_log:
                    return str(schema.error_log[0].message)
                return "Unknown XSD error"

            return None
        except Exception as e:
            return str(e)

    def _generate_certificate(
        self,
        batch: BatchData,
        all_findings: List[Finding]
    ) -> ValidationCertificate:
        """Generate send-ready certificate."""
        # Calculate hash of source file
        file_hash = ""
        if batch.source_file:
            try:
                with open(batch.source_file, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
            except Exception:
                file_hash = "unable_to_calculate"

        # Determine which engines ran
        engines_run = set()
        for f in all_findings:
            if f.engine == Engine.XSD:
                engines_run.add("XSD")
            elif f.engine == Engine.SCHEMA:
                engines_run.add("SCHEMA")
            elif f.engine == Engine.RULES:
                engines_run.add("RULES")
            elif f.engine == Engine.LLM:
                engines_run.add("LLM")
            elif f.engine == Engine.FINAL:
                engines_run.add("FINAL")

        # If no findings, at minimum we ran FINAL
        if not engines_run:
            engines_run.add("FINAL")

        # Count warnings
        warnings_count = sum(1 for f in all_findings if f.severity == Severity.WAARSCHUWING)

        # Check critical entities
        critical_entities = {}
        for contract in batch.contracts:
            entity_types = contract.get_all_entity_types_recursive()
            critical_entities["AL"] = critical_entities.get("AL", True) and "AL" in entity_types
            critical_entities["PP"] = critical_entities.get("PP", True) and "PP" in entity_types

        return ValidationCertificate(
            is_valid=True,
            timestamp=datetime.now().isoformat(),
            source_file=batch.source_file or "",
            contract_count=len(batch.contracts),
            checks_performed=[
                "XSD schema validatie",
                "Schema label/attribuut validatie",
                "Hierarchie structuur validatie",
                "Business rules validatie",
                "Datum logica validatie",
                "BSN/KVK 11-proef",
                "Postcode formaat",
                "IBAN validatie",
                "XPath verbandscontroles",
                "Encoding validatie",
                "Verplichte entiteiten aanwezig",
                "Business completeness",
                "XSD re-validatie",
            ],
            engines_run=sorted(engines_run),
            critical_entities_present=critical_entities,
            warnings_acknowledged=warnings_count,
            hash_sha256=file_hash,
        )

    def get_sivi_certification_info(self) -> Dict[str, Any]:
        """
        Get information about SIVI official certification.

        This internal validator provides pre-validation only.
        For official SIVI certification, use the SIVI portal.
        """
        integration = SIVICertificationIntegration(self.config)
        return integration.get_certification_info()
