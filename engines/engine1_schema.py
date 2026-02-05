"""Engine 1: Schema-derived validation."""

import re
from typing import List, Optional, Set

from config import Config, get_config
from engines.base import (
    BatchData,
    ContractData,
    Engine,
    EntityData,
    Finding,
    Severity,
    ValidationEngine,
)
from parser.xsd_parser import SchemaLookup, get_schema_lookup
from parser.xsd_structure_parser import StructureLookup, get_structure_lookup


class SchemaValidationEngine(ValidationEngine):
    """
    Engine 1: Schema-derived validation.

    Validates:
    - E1-001: Label niet in entiteit
    - E1-002: Ongeldige dekkingscode
    - E1-003: Veldlengte overschreden
    - E1-004: Formaatfout
    - E1-005: Label van andere entiteit
    - E1-006: Hierarchie fout (entiteit onder verkeerde parent)
    - E1-007: Verplicht attribuut ontbreekt
    - E1-008: Element volgorde incorrect
    - E1-009: Ongeldige codelijst waarde
    - E1-010: Decimale precisie fout (Bn/Pn/An formats)
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self._lookup: Optional[SchemaLookup] = None
        self._structure_lookup: Optional[StructureLookup] = None

    @property
    def engine_type(self) -> Engine:
        return Engine.SCHEMA

    @property
    def lookup(self) -> SchemaLookup:
        if self._lookup is None:
            self._lookup = get_schema_lookup(self.config)
        return self._lookup

    @property
    def structure_lookup(self) -> StructureLookup:
        if self._structure_lookup is None:
            self._structure_lookup = get_structure_lookup(self.config)
        return self._structure_lookup

    def validate(self, batch: BatchData) -> List[Finding]:
        """Validate a batch and return findings."""
        findings = []
        for contract in batch.contracts:
            findings.extend(self._validate_contract(contract))
        return findings

    def _validate_contract(self, contract: ContractData) -> List[Finding]:
        """Validate a single contract."""
        findings = []

        # Validate all entities (including nested)
        for entity in contract.get_all_entities_recursive():
            findings.extend(self._validate_entity(entity, contract))

            # E1-006: Hierarchy validation
            if self.config.enable_hierarchy_validation:
                findings.extend(self._check_hierarchy(entity, contract))

        return findings

    def _validate_entity(
        self, entity: EntityData, contract: ContractData
    ) -> List[Finding]:
        """Validate a single entity."""
        findings = []

        # E1-007: Check required attributes
        findings.extend(self._check_required_attributes(entity, contract))

        for attr_name, attr_value in entity.attributes.items():
            # E1-001 & E1-005: Check if attribute belongs to entity
            finding = self._check_attribute_entity(
                attr_name, entity, contract, attr_value
            )
            if finding:
                findings.append(finding)
                continue  # Skip further checks for invalid attribute

            # E1-002: Check coverage codes
            if attr_name.endswith("_CODE"):
                finding = self._check_coverage_code(
                    attr_name, attr_value, entity, contract
                )
                if finding:
                    findings.append(finding)

            # E1-009: Check codelist values for ALL codelist attributes
            codelist_finding = self._check_codelist_value(
                attr_name, attr_value, entity, contract
            )
            if codelist_finding:
                findings.append(codelist_finding)

            # E1-003 & E1-004: Check format
            format_findings = self._check_format(attr_name, attr_value, entity, contract)
            findings.extend(format_findings)

            # E1-010: Check decimal precision (Bn/Pn/An formats)
            decimal_finding = self._check_decimal_precision(
                attr_name, attr_value, entity, contract
            )
            if decimal_finding:
                findings.append(decimal_finding)

        return findings

    def _check_attribute_entity(
        self,
        attr_name: str,
        entity: EntityData,
        contract: ContractData,
        attr_value: str,
    ) -> Optional[Finding]:
        """Check if attribute belongs to the entity (E1-001, E1-005)."""
        entity_type = entity.entity_type
        valid_attrs = self.lookup.entities.get(entity_type, set())

        if not valid_attrs:
            # Entity not found in schema - skip check
            return None

        # Check if attribute starts with correct entity prefix
        if not attr_name.startswith(f"{entity_type}_"):
            # Wrong entity prefix
            attr_prefix = attr_name.split("_")[0] if "_" in attr_name else ""
            if attr_prefix and attr_prefix in self.lookup.entities:
                return Finding(
                    severity=Severity.FOUT,
                    engine=Engine.SCHEMA,
                    code="E1-005",
                    regeltype="label_verkeerde_entiteit",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit=entity_type,
                    label=attr_name,
                    waarde=attr_value,
                    omschrijving=f"Label {attr_name} hoort bij entiteit {attr_prefix}, niet bij {entity_type}",
                    verwacht=f"Label beginnend met {entity_type}_",
                    bron="entiteiten.xsd",
                    regel=entity.line_number,
                )
            return None  # Unknown prefix, skip

        if attr_name not in valid_attrs:
            # Determine if it's from another entity (E1-005) or completely invalid (E1-001)
            attr_prefix = attr_name.split("_")[0] if "_" in attr_name else ""

            if attr_prefix != entity_type and attr_prefix in self.lookup.entities:
                # Attribute belongs to different entity
                return Finding(
                    severity=Severity.FOUT,
                    engine=Engine.SCHEMA,
                    code="E1-005",
                    regeltype="label_verkeerde_entiteit",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit=entity_type,
                    label=attr_name,
                    waarde=attr_value,
                    omschrijving=f"Label {attr_name} hoort bij entiteit {attr_prefix}, niet bij {entity_type}",
                    verwacht=f"Label beginnend met {entity_type}_",
                    bron="entiteiten.xsd",
                    regel=entity.line_number,
                )
            else:
                # Attribute not valid for this entity
                return Finding(
                    severity=Severity.FOUT,
                    engine=Engine.SCHEMA,
                    code="E1-001",
                    regeltype="ongeldig_label",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit=entity_type,
                    label=attr_name,
                    waarde=attr_value,
                    omschrijving=f"Label {attr_name} bestaat niet voor entiteit {entity_type}",
                    verwacht=f"Geldig label voor {entity_type}",
                    bron="entiteiten.xsd",
                    regel=entity.line_number,
                )

        return None

    def _check_coverage_code(
        self,
        attr_name: str,
        attr_value: str,
        entity: EntityData,
        contract: ContractData,
    ) -> Optional[Finding]:
        """Check if coverage code is valid for entity (E1-002)."""
        entity_type = entity.entity_type

        # Get valid codes for this entity
        valid_codes = self.lookup.get_valid_coverage_codes(entity_type)

        if not valid_codes:
            # No specific codes defined for this entity - skip check
            return None

        if attr_value and attr_value not in valid_codes:
            # Format valid codes for display (show first few)
            codes_display = ", ".join(sorted(valid_codes)[:10])
            if len(valid_codes) > 10:
                codes_display += f", ... ({len(valid_codes)} totaal)"

            return Finding(
                severity=Severity.FOUT,
                engine=Engine.SCHEMA,
                code="E1-002",
                regeltype="ongeldige_code",
                contract=contract.contract_nummer,
                branche=contract.branche,
                entiteit=entity_type,
                label=attr_name,
                waarde=attr_value,
                omschrijving=f"Dekkingscode {attr_value} is niet geldig voor entiteit {entity_type}",
                verwacht=codes_display,
                bron="dekkingcodesgroup.xsd",
                regel=entity.line_number,
            )

        return None

    def _check_codelist_value(
        self,
        attr_name: str,
        attr_value: str,
        entity: EntityData,
        contract: ContractData,
    ) -> Optional[Finding]:
        """Check if codelist value is valid (E1-009)."""
        # Skip empty values
        if not attr_value:
            return None

        # Skip _CODE attributes (already handled by _check_coverage_code)
        if attr_name.endswith("_CODE"):
            return None

        # Check if this attribute uses a codelist
        if not self.lookup.is_codelist_attribute(attr_name):
            return None

        # Get valid values for this codelist
        valid_values = self.lookup.get_codelist_for_attribute(attr_name)
        if not valid_values:
            return None

        # Check if value is valid
        if attr_value not in valid_values:
            codelist_name = self.lookup.get_codelist_name_for_attribute(attr_name)

            # Format valid values for display (show first few)
            values_display = ", ".join(sorted(valid_values)[:10])
            if len(valid_values) > 10:
                values_display += f", ... ({len(valid_values)} totaal)"

            return Finding(
                severity=Severity.FOUT,
                engine=Engine.SCHEMA,
                code="E1-009",
                regeltype="ongeldige_codelijst_waarde",
                contract=contract.contract_nummer,
                branche=contract.branche,
                entiteit=entity.entity_type,
                label=attr_name,
                waarde=attr_value,
                omschrijving=f"Waarde '{attr_value}' is niet geldig voor codelijst {codelist_name or 'onbekend'}",
                verwacht=values_display,
                bron="codelist.xsd",
                regel=entity.line_number,
            )

        return None

    def _check_format(
        self,
        attr_name: str,
        attr_value: str,
        entity: EntityData,
        contract: ContractData,
    ) -> List[Finding]:
        """Check format constraints (E1-003, E1-004)."""
        findings = []

        if not attr_value:
            return findings

        format_spec = self.lookup.get_format_for_attribute(attr_name)
        if not format_spec:
            return findings

        # E1-003: Check length
        if format_spec.max_length is not None:
            if len(attr_value) > format_spec.max_length:
                findings.append(
                    Finding(
                        severity=Severity.FOUT,
                        engine=Engine.SCHEMA,
                        code="E1-003",
                        regeltype="veldlengte_overschreden",
                        contract=contract.contract_nummer,
                        branche=contract.branche,
                        entiteit=entity.entity_type,
                        label=attr_name,
                        waarde=attr_value[:50] + "..." if len(attr_value) > 50 else attr_value,
                        omschrijving=f"Waarde heeft {len(attr_value)} tekens, maximaal {format_spec.max_length} toegestaan",
                        verwacht=f"Maximaal {format_spec.max_length} tekens",
                        bron="formaten.xsd",
                        regel=entity.line_number,
                    )
                )

        # E1-004: Check format/pattern
        format_finding = self._check_format_pattern(
            attr_name, attr_value, format_spec, entity, contract
        )
        if format_finding:
            findings.append(format_finding)

        return findings

    def _check_format_pattern(
        self,
        attr_name: str,
        attr_value: str,
        format_spec,
        entity: EntityData,
        contract: ContractData,
    ) -> Optional[Finding]:
        """Check if value matches format pattern."""
        base_type = format_spec.base_type

        # Check numeric format
        if base_type == "Numeric" or format_spec.name.startswith("N"):
            if not re.match(r"^[0-9]*$", attr_value):
                return Finding(
                    severity=Severity.FOUT,
                    engine=Engine.SCHEMA,
                    code="E1-004",
                    regeltype="formaatfout",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit=entity.entity_type,
                    label=attr_name,
                    waarde=attr_value,
                    omschrijving=f"Waarde is niet numeriek",
                    verwacht="Numerieke waarde (alleen cijfers)",
                    bron="formaten.xsd",
                    regel=entity.line_number,
                )

        # Check date formats
        if format_spec.name == "codeD1":
            # EEJJMMDD format
            if not self._is_valid_date_d1(attr_value):
                return Finding(
                    severity=Severity.FOUT,
                    engine=Engine.SCHEMA,
                    code="E1-004",
                    regeltype="formaatfout",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit=entity.entity_type,
                    label=attr_name,
                    waarde=attr_value,
                    omschrijving=f"Ongeldige datum",
                    verwacht="Datum in formaat EEJJMMDD (bijv. 20240101)",
                    bron="formaten.xsd",
                    regel=entity.line_number,
                )

        # Check J/N format
        if format_spec.name == "codeJN":
            if attr_value not in ("J", "N", ""):
                return Finding(
                    severity=Severity.FOUT,
                    engine=Engine.SCHEMA,
                    code="E1-004",
                    regeltype="formaatfout",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit=entity.entity_type,
                    label=attr_name,
                    waarde=attr_value,
                    omschrijving=f"Ongeldige Ja/Nee waarde",
                    verwacht="J of N",
                    bron="formaten.xsd",
                    regel=entity.line_number,
                )

        # Check custom pattern
        if format_spec.pattern:
            try:
                if not re.match(format_spec.pattern, attr_value):
                    return Finding(
                        severity=Severity.FOUT,
                        engine=Engine.SCHEMA,
                        code="E1-004",
                        regeltype="formaatfout",
                        contract=contract.contract_nummer,
                        branche=contract.branche,
                        entiteit=entity.entity_type,
                        label=attr_name,
                        waarde=attr_value,
                        omschrijving=f"Waarde voldoet niet aan formaat",
                        verwacht=f"Patroon: {format_spec.pattern}",
                        bron="formaten.xsd",
                        regel=entity.line_number,
                    )
            except re.error:
                pass  # Invalid regex, skip check

        return None

    def _is_valid_date_d1(self, value: str) -> bool:
        """Check if value is a valid EEJJMMDD date."""
        if not value:
            return True  # Empty is OK

        if len(value) != 8:
            return False

        if not value.isdigit():
            return False

        try:
            year = int(value[:4])
            month = int(value[4:6])
            day = int(value[6:8])

            if month < 1 or month > 12:
                return False
            if day < 1 or day > 31:
                return False

            # Basic day validation per month
            if month in (4, 6, 9, 11) and day > 30:
                return False
            if month == 2:
                # Leap year check
                is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
                if day > (29 if is_leap else 28):
                    return False

            return True
        except ValueError:
            return False

    def _check_hierarchy(self, entity: EntityData, contract: ContractData) -> List[Finding]:
        """Check if entity is at correct position in hierarchy (E1-006)."""
        findings = []

        # Skip if no hierarchy data
        if not self.structure_lookup.elements:
            return findings

        # Determine actual parent
        if entity.parent:
            actual_parent = entity.parent.entity_type
        else:
            # Top-level entity - parent is "Contract"
            actual_parent = "Contract"

        # Get allowed parents for this entity type
        allowed_parents = self.structure_lookup.get_allowed_parents(entity.entity_type)

        # If no allowed_parents found, the entity might not be in the structure
        # This could mean it's a valid top-level entity or unknown
        if not allowed_parents:
            # Check if it should be at root level
            if actual_parent == "Contract":
                if not self.structure_lookup.is_valid_at_root(entity.entity_type):
                    # This entity is not allowed at root and has no known parents
                    findings.append(Finding(
                        severity=Severity.FOUT,
                        engine=Engine.SCHEMA,
                        code="E1-006",
                        regeltype="hierarchie_fout",
                        contract=contract.contract_nummer,
                        branche=contract.branche,
                        entiteit=entity.entity_type,
                        label="",
                        waarde=f"parent={actual_parent}",
                        omschrijving=(
                            f"Entiteit {entity.entity_type} staat direct onder Contract, "
                            f"maar is niet toegestaan op root niveau"
                        ),
                        verwacht="Entiteit moet onder een parent-entiteit staan",
                        bron="Contractberichtstructuur.xsd",
                        regel=entity.line_number,
                    ))
            return findings

        # Check if actual parent is in allowed parents
        if actual_parent not in allowed_parents:
            allowed_str = ", ".join(sorted(allowed_parents))

            findings.append(Finding(
                severity=Severity.FOUT,
                engine=Engine.SCHEMA,
                code="E1-006",
                regeltype="hierarchie_fout",
                contract=contract.contract_nummer,
                branche=contract.branche,
                entiteit=entity.entity_type,
                label="",
                waarde=f"parent={actual_parent}",
                omschrijving=(
                    f"Entiteit {entity.entity_type} staat onder {actual_parent}, "
                    f"maar mag alleen onder: {allowed_str}"
                ),
                verwacht=f"Parent: {allowed_str}",
                bron="Contractberichtstructuur.xsd",
                regel=entity.line_number,
            ))

        return findings

    def _check_required_attributes(self, entity: EntityData, contract: ContractData) -> List[Finding]:
        """Check if required attributes are present (E1-007)."""
        findings = []

        # Get business-required attributes for this entity type
        required_suffixes = self.lookup.get_required_attributes(entity.entity_type)

        for attr_suffix in required_suffixes:
            full_attr_name = f"{entity.entity_type}_{attr_suffix}"

            # Check if attribute is present and has a non-empty value
            attr_value = entity.attributes.get(full_attr_name)

            # Special handling for VOLGNUM which is stored separately
            if attr_suffix == "VOLGNUM":
                if entity.volgnum is None:
                    findings.append(Finding(
                        severity=Severity.FOUT,
                        engine=Engine.SCHEMA,
                        code="E1-007",
                        regeltype="verplicht_attribuut_ontbreekt",
                        contract=contract.contract_nummer,
                        branche=contract.branche,
                        entiteit=entity.entity_type,
                        label=full_attr_name,
                        waarde="",
                        omschrijving=f"Verplicht attribuut {full_attr_name} ontbreekt",
                        verwacht=f"Attribuut {full_attr_name} is verplicht voor {entity.entity_type}",
                        bron="ADN business rules",
                        regel=entity.line_number,
                    ))
            elif attr_value is None or attr_value.strip() == "":
                findings.append(Finding(
                    severity=Severity.FOUT,
                    engine=Engine.SCHEMA,
                    code="E1-007",
                    regeltype="verplicht_attribuut_ontbreekt",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit=entity.entity_type,
                    label=full_attr_name,
                    waarde="",
                    omschrijving=f"Verplicht attribuut {full_attr_name} ontbreekt of is leeg",
                    verwacht=f"Attribuut {full_attr_name} is verplicht voor {entity.entity_type}",
                    bron="ADN business rules",
                    regel=entity.line_number,
                ))

        return findings

    def _check_decimal_precision(
        self,
        attr_name: str,
        attr_value: str,
        entity: EntityData,
        contract: ContractData,
    ) -> Optional[Finding]:
        """Check decimal precision for Bn/Pn/An formats (E1-010)."""
        if not attr_value:
            return None

        # Use the lookup's decimal validation
        is_valid, error_msg = self.lookup.validate_decimal_precision(attr_name, attr_value)

        if not is_valid:
            format_spec = self.lookup.get_format_for_attribute(attr_name)
            format_info = ""
            if format_spec:
                total = format_spec.get_effective_total_digits()
                frac = format_spec.get_effective_fraction_digits()
                if total is not None:
                    format_info = f"max {total} cijfers"
                if frac is not None:
                    format_info += f", {frac} decimalen"

            return Finding(
                severity=Severity.FOUT,
                engine=Engine.SCHEMA,
                code="E1-010",
                regeltype="decimale_precisie_fout",
                contract=contract.contract_nummer,
                branche=contract.branche,
                entiteit=entity.entity_type,
                label=attr_name,
                waarde=attr_value[:50] if len(attr_value) > 50 else attr_value,
                omschrijving=f"Decimale precisie fout: {error_msg}",
                verwacht=f"Geldig decimaal getal ({format_info})" if format_info else "Geldig decimaal getal",
                bron="formaten.xsd",
                regel=entity.line_number,
            )

        return None
