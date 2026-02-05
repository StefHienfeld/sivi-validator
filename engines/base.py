"""Base classes and data structures for validation engines."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any


class Severity(Enum):
    """Severity levels for validation findings."""

    FOUT = "FOUT"  # Error - must be fixed
    WAARSCHUWING = "WAARSCHUWING"  # Warning - should be reviewed
    INFO = "INFO"  # Informational - for awareness


class Criticality(Enum):
    """Criticality levels for validation findings.

    KRITIEK: XSD/Schema verplicht, kan niet versturen naar systeemhuis
    AANDACHT: Business rule, technisch OK maar review nodig
    INFO: Ter informatie
    """

    KRITIEK = "KRITIEK"      # Cannot send - blocking error
    AANDACHT = "AANDACHT"    # Needs review - non-blocking
    INFO = "INFO"            # Informational


class Engine(Enum):
    """Validation engine types."""

    XSD = 0     # Native XSD validation
    SCHEMA = 1  # Schema-derived validation
    RULES = 2   # Business rules validation
    LLM = 3     # LLM semantic analysis
    FINAL = 4   # Final validation and certification


@dataclass
class Finding:
    """A single validation finding."""

    severity: Severity
    engine: Engine
    code: str                 # e.g., "E1-002"
    regeltype: str            # e.g., "ongeldige_code"
    contract: str             # e.g., "DL252168"
    branche: str              # e.g., "037"
    entiteit: str             # e.g., "AN"
    label: str                # e.g., "AN_CODE"
    waarde: str               # e.g., "3002"
    omschrijving: str         # Human-readable description
    verwacht: str             # Expected values/format
    bron: str                 # Source reference, e.g., "dekkingcodesgroup.xsd"
    regel: Optional[int] = None  # Line number in source XML
    criticality: Optional[Criticality] = None  # Criticality level (set by determine_criticality)

    def __post_init__(self):
        """Set criticality based on engine and code if not explicitly set."""
        if self.criticality is None:
            self.criticality = self._determine_criticality()

    def _determine_criticality(self) -> Criticality:
        """Determine criticality based on engine and rule code.

        KRITIEK: Engine 0 (XSD), Engine 1 (Schema), Engine 2 hard rules
        AANDACHT: Engine 2 soft rules, Engine 3 (LLM)
        INFO: Informational messages
        """
        # Engine 0 (XSD) and Engine 1 (Schema) are always KRITIEK
        if self.engine in (Engine.XSD, Engine.SCHEMA):
            return Criticality.KRITIEK

        # Engine 2: Depends on rule code
        if self.engine == Engine.RULES:
            # Hard rules (KRITIEK): E2-001, E2-002, E2-003, E2-004, E2-005, E2-006,
            # E2-008 (BSN), E2-010, E2-011, E2-013
            kritiek_rules = {
                "E2-001",  # VOLGNUM niet sequentieel
                "E2-002",  # PP_BTP som onjuist
                "E2-003",  # Meerdere prolongatiemaanden
                "E2-004",  # XD-entiteit verboden
                "E2-005",  # BO_BRPRM afwijkend
                "E2-006",  # Datum logica fout
                "E2-008",  # BSN/KVK ongeldig (when FOUT severity)
                "E2-010",  # PP_TTOT som onjuist
                "E2-011",  # IBAN ongeldig
                "E2-013",  # Branche-dekking mismatch
            }
            if self.code in kritiek_rules:
                # E2-008 can be WAARSCHUWING for KVK, only KRITIEK for FOUT severity
                if self.code == "E2-008" and self.severity != Severity.FOUT:
                    return Criticality.AANDACHT
                return Criticality.KRITIEK

            # Soft rules (AANDACHT): E2-007, E2-009, E2-012, E2-014, E2-015, E2-016, E2-017
            return Criticality.AANDACHT

        # Engine 3 (LLM) is always AANDACHT
        if self.engine == Engine.LLM:
            return Criticality.AANDACHT

        # Default to INFO for other cases (Engine.FINAL)
        if self.severity == Severity.INFO:
            return Criticality.INFO

        return Criticality.AANDACHT

    def to_dict(self) -> Dict[str, Any]:
        """Convert finding to dictionary."""
        result = {
            "severity": self.severity.value,
            "engine": self.engine.value,
            "code": self.code,
            "regeltype": self.regeltype,
            "contract": self.contract,
            "branche": self.branche,
            "entiteit": self.entiteit,
            "label": self.label,
            "waarde": self.waarde,
            "omschrijving": self.omschrijving,
            "verwacht": self.verwacht,
            "bron": self.bron,
            "criticality": self.criticality.value if self.criticality else Criticality.AANDACHT.value,
        }
        # Include line number if available
        if self.regel is not None:
            result["regel"] = self.regel
        return result


@dataclass
class EntityData:
    """Data for a single entity instance in a contract."""

    entity_type: str  # e.g., "AN", "PP", "VP"
    volgnum: Optional[int] = None
    attributes: Dict[str, str] = field(default_factory=dict)
    # Hierarchy support
    children: List["EntityData"] = field(default_factory=list)
    parent: Optional["EntityData"] = field(default=None, repr=False)
    xml_path: str = ""  # e.g., "Contract/PP/VP"
    line_number: Optional[int] = None

    def get_attr(self, attr_suffix: str) -> Optional[str]:
        """Get attribute value by suffix (without entity prefix)."""
        full_name = f"{self.entity_type}_{attr_suffix}"
        return self.attributes.get(full_name)

    def get_all_descendants(self) -> List["EntityData"]:
        """Get all descendant entities recursively."""
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.get_all_descendants())
        return descendants


@dataclass
class ContractData:
    """Data for a single contract in a batch."""

    contract_nummer: str  # e.g., "DL252168"
    branche: str  # e.g., "037"
    entities: List[EntityData] = field(default_factory=list)
    raw_xml: Optional[str] = None  # Original XML for LLM analysis

    def get_entities_by_type(self, entity_type: str) -> List[EntityData]:
        """Get all entities of a specific type (top-level only)."""
        return [e for e in self.entities if e.entity_type == entity_type]

    def get_all_entities_recursive(self) -> List[EntityData]:
        """Get all entities including nested children."""
        all_entities = []
        for entity in self.entities:
            all_entities.append(entity)
            all_entities.extend(entity.get_all_descendants())
        return all_entities

    def get_entities_by_type_recursive(self, entity_type: str) -> List[EntityData]:
        """Get all entities of a specific type including nested."""
        return [e for e in self.get_all_entities_recursive() if e.entity_type == entity_type]

    def get_all_entity_types(self) -> Set[str]:
        """Get set of all entity types in this contract."""
        return {e.entity_type for e in self.entities}

    def get_all_entity_types_recursive(self) -> Set[str]:
        """Get set of all entity types including nested."""
        return {e.entity_type for e in self.get_all_entities_recursive()}

    def get_premium_entities(self) -> List[EntityData]:
        """Get all coverage/premium entities (dekkingen)."""
        coverage_types = {
            "AN", "DA", "DR", "CA", "WA", "KA", "VO", "BH", "AO",
            "CY", "DC", "AU", "AZ", "BI", "BK", "BQ", "BR", "BW",
            "BZ", "CD", "CG", "DD", "DF", "DG", "DH", "DI", "DJ",
            "DK", "DL", "DM", "DN", "DP", "DQ", "DS", "DT", "DU",
            "DV", "DX", "EA", "EB", "EC", "ED", "EE", "EF", "EG",
            "EH", "EI", "EJ", "EK", "EM", "EN", "EO", "EP", "EQ",
        }
        return [e for e in self.get_all_entities_recursive() if e.entity_type in coverage_types]


@dataclass
class BatchData:
    """Data for an entire batch of contracts."""

    contracts: List[ContractData] = field(default_factory=list)
    source_file: Optional[str] = None

    def get_all_branches(self) -> Set[str]:
        """Get set of all branches in this batch."""
        return {c.branche for c in self.contracts}

    def get_prolongation_months(self) -> Set[str]:
        """Get set of all prolongation months (from PP_PROLMND)."""
        months = set()
        for contract in self.contracts:
            for entity in contract.get_entities_by_type("PP"):
                prolmnd = entity.get_attr("PROLMND")
                if prolmnd:
                    months.add(prolmnd)
        return months


class ValidationEngine(ABC):
    """Abstract base class for validation engines."""

    @property
    @abstractmethod
    def engine_type(self) -> Engine:
        """Return the engine type."""
        pass

    @abstractmethod
    def validate(self, batch: BatchData) -> List[Finding]:
        """Validate a batch and return findings."""
        pass

    def validate_contract(self, contract: ContractData) -> List[Finding]:
        """Validate a single contract. Override if needed."""
        batch = BatchData(contracts=[contract])
        return self.validate(batch)


@dataclass
class ValidationCertificate:
    """Certificate confirming XML is ready to send."""

    is_valid: bool
    timestamp: str
    source_file: str
    contract_count: int
    checks_performed: List[str]
    engines_run: List[str]
    critical_entities_present: Dict[str, bool]
    warnings_acknowledged: int
    hash_sha256: str  # Hash of original XML for audit trail

    def to_dict(self) -> Dict[str, Any]:
        """Convert certificate to dictionary."""
        return {
            "is_valid": self.is_valid,
            "timestamp": self.timestamp,
            "source_file": self.source_file,
            "contract_count": self.contract_count,
            "checks_performed": self.checks_performed,
            "engines_run": self.engines_run,
            "critical_entities_present": self.critical_entities_present,
            "warnings_acknowledged": self.warnings_acknowledged,
            "hash_sha256": self.hash_sha256,
        }


@dataclass
class ValidationResult:
    """Result of validation including findings and optional certificate."""

    findings: List[Finding] = field(default_factory=list)
    certificate: Optional[ValidationCertificate] = None

    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no FOUT findings)."""
        return not any(f.severity == Severity.FOUT for f in self.findings)

    @property
    def is_ready_to_send(self) -> bool:
        """Check if XML is certified ready to send."""
        return self.certificate is not None and self.certificate.is_valid

    def get_summary(self) -> str:
        """Get human-readable summary."""
        if self.is_ready_to_send:
            return (
                f"✅ XML VERZENDKLAAR\n"
                f"Certificaat gegenereerd: {self.certificate.timestamp}\n"
                f"Contracten: {self.certificate.contract_count}\n"
                f"Checks uitgevoerd: {len(self.certificate.checks_performed)}\n"
                f"Waarschuwingen: {self.certificate.warnings_acknowledged}\n"
                f"SHA256: {self.certificate.hash_sha256[:16]}..."
            )
        else:
            errors = sum(1 for f in self.findings if f.severity == Severity.FOUT)
            warnings = sum(1 for f in self.findings if f.severity == Severity.WAARSCHUWING)
            return (
                f"❌ XML NIET VERZENDKLAAR\n"
                f"Fouten: {errors}\n"
                f"Waarschuwingen: {warnings}\n"
                f"Corrigeer alle fouten voordat u verzendt."
            )

    def get_error_count(self) -> int:
        """Get count of FOUT findings."""
        return sum(1 for f in self.findings if f.severity == Severity.FOUT)

    def get_warning_count(self) -> int:
        """Get count of WAARSCHUWING findings."""
        return sum(1 for f in self.findings if f.severity == Severity.WAARSCHUWING)

    def get_info_count(self) -> int:
        """Get count of INFO findings."""
        return sum(1 for f in self.findings if f.severity == Severity.INFO)
