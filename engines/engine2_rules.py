"""Engine 2: Business rules validation."""

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Set, Tuple

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


class BusinessRulesEngine(ValidationEngine):
    """
    Engine 2: Business rules validation.

    Validates:
    - E2-001: VOLGNUM niet sequentieel per entiteitstype
    - E2-002: PP_BTP ≠ som dekkings-BTPs
    - E2-003: Meerdere prolongatiemaanden in batch
    - E2-004: XD-entiteit aanwezig
    - E2-005: BO_BRPRM ≠ PP_BTP (>1 cent verschil)
    - E2-006: Datum logica fout (ingangsdatum > einddatum)
    - E2-007: Postcode formaat ongeldig
    - E2-008: BSN/KVK 11-proef fout
    - E2-009: Duplicaat entiteit detectie
    - E2-010: PP_TTOT ≠ PP_BTP + PP_TASS + PP_TKST + PP_TKRT + PP_TTSL
    - E2-011: Ongeldig IBAN formaat/checksum
    - E2-012: Betaaltermijn/prolongatie inconsistent
    - E2-013: Branche-dekking mismatch (dekking niet toegestaan voor branche)
    - E2-014: Ingangsdatum in verleden bij nieuwe polis
    - E2-015: Verzekerde som overschrijdt maximum
    - E2-016: Ongeldige dekkingscombinatie
    - E2-017: Objecttype niet passend bij branche
    """

    # Dutch postcode pattern: 1234AB or 1234 AB
    POSTCODE_PATTERN = re.compile(r"^[1-9][0-9]{3}\s?[A-Z]{2}$")

    # Branch to coverage entity mapping
    # Based on SIVI AFD documentation
    BRANCH_COVERAGE_MAPPING = {
        # Motorrijtuig branches (20-25)
        "020": {"expected": {"CA", "WA", "AH"}, "forbidden": {"DR"}, "description": "Motorrijtuig personenauto"},
        "021": {"expected": {"CA", "WA", "AH"}, "forbidden": {"DR"}, "description": "Motorrijtuig bestel/vracht"},
        "022": {"expected": {"CA", "WA", "AH"}, "forbidden": {"DR"}, "description": "Motorrijtuig bromfiets"},
        "023": {"expected": {"CA", "WA", "AH"}, "forbidden": {"DR"}, "description": "Motorrijtuig caravan"},
        "024": {"expected": {"CA", "WA", "AH"}, "forbidden": set(), "description": "Motorrijtuig aanhangwagen"},
        "025": {"expected": {"CA", "WA"}, "forbidden": set(), "description": "Motorrijtuig overig"},

        # Brand/Inboedel branches (30-35)
        "030": {"expected": {"DA"}, "forbidden": {"CA", "WA", "PV"}, "description": "Inboedel"},
        "031": {"expected": {"DA"}, "forbidden": {"CA", "WA", "PV"}, "description": "Opstal woonhuis"},
        "032": {"expected": {"DA"}, "forbidden": {"CA", "WA", "PV"}, "description": "Glasverzekering"},
        "035": {"expected": {"DA"}, "forbidden": {"CA", "WA"}, "description": "Brand bedrijf"},

        # Aansprakelijkheid branches (40-45)
        "040": {"expected": {"AN"}, "forbidden": {"CA", "DA"}, "description": "Aansprakelijkheid particulier"},
        "041": {"expected": {"AN"}, "forbidden": {"CA", "DA"}, "description": "Aansprakelijkheid bedrijf"},

        # Rechtsbijstand (60)
        "060": {"expected": {"DR"}, "forbidden": {"CA", "WA", "DA", "AN"}, "description": "Rechtsbijstand"},
        "061": {"expected": {"DR"}, "forbidden": {"CA", "WA", "DA"}, "description": "Rechtsbijstand verkeer"},

        # Reis (70)
        "070": {"expected": {"DA"}, "forbidden": {"CA", "WA"}, "description": "Reisverzekering"},
        "071": {"expected": {"DA"}, "forbidden": {"CA", "WA"}, "description": "Doorlopende reis"},
    }

    # Coverage combinations that cannot coexist
    FORBIDDEN_COVERAGE_COMBINATIONS = [
        # (entity1, code1, entity2, code2, description)
        ("CA", "3001", "WA", "2001", "Casco allrisk en WA basic beide actief"),
        # Add more as needed based on SIVI documentation
    ]

    # Maximum verzekerde som per type
    MAX_VERZEKERDE_SOM = {
        "DA_VRZSOMJ": Decimal("10000000"),  # Inboedel max 10M
        "CA_NIEUWWRD": Decimal("500000"),   # Auto nieuwwaarde max 500K
        "AN_VERZSOM": Decimal("5000000"),   # Aansprakelijkheid max 5M
    }

    # Branch to required object entity mapping
    BRANCH_OBJECT_MAPPING = {
        # Motor branches require PV (voertuig)
        "020": "PV", "021": "PV", "022": "PV", "023": "PV", "024": "PV", "025": "PV",
        # Brand branches may require DA-related objects
        # Reis branches may have specific requirements
    }

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()

    @property
    def engine_type(self) -> Engine:
        return Engine.RULES

    def validate(self, batch: BatchData) -> List[Finding]:
        """Validate a batch and return findings."""
        findings = []

        # E2-003: Check for multiple prolongation months in batch
        findings.extend(self._check_multiple_prolmonths(batch))

        # Validate each contract
        for contract in batch.contracts:
            findings.extend(self._validate_contract(contract))

        return findings

    def _validate_contract(self, contract: ContractData) -> List[Finding]:
        """Validate a single contract."""
        findings = []

        # E2-001: Check VOLGNUM sequence per entity type
        findings.extend(self._check_volgnum_sequence(contract))

        # E2-002: Check premium sum
        findings.extend(self._check_premium_sum(contract))

        # E2-004: Check for XD entity
        findings.extend(self._check_xd_entity(contract))

        # E2-005: Check BO_BRPRM vs PP_BTP
        findings.extend(self._check_bo_brprm(contract))

        # E2-006: Check date logic
        findings.extend(self._check_date_logic(contract))

        # E2-007: Check postcode format
        findings.extend(self._check_postcode(contract))

        # E2-008: Check BSN/KVK 11-proef
        findings.extend(self._check_bsn_kvk(contract))

        # E2-009: Check for duplicate entities
        findings.extend(self._check_duplicates(contract))

        # E2-010: Check PP_TTOT reconciliation
        findings.extend(self._check_pp_ttot(contract))

        # E2-011: Check IBAN format and checksum
        findings.extend(self._check_iban(contract))

        # E2-012: Check prolongation consistency
        findings.extend(self._check_prolongation_consistency(contract))

        # E2-013: Check branch-coverage compatibility
        findings.extend(self._check_branch_coverage_compatibility(contract))

        # E2-014: Check ingangsdatum not in past for new policies
        findings.extend(self._check_ingangsdatum_new_policy(contract))

        # E2-015: Check verzekerde som maximums
        findings.extend(self._check_verzekerde_som_maximum(contract))

        # E2-016: Check forbidden coverage combinations
        findings.extend(self._check_coverage_combinations(contract))

        # E2-017: Check object type matches branch
        findings.extend(self._check_object_type_branch(contract))

        return findings

    def _check_volgnum_sequence(self, contract: ContractData) -> List[Finding]:
        """Check if VOLGNUM is sequential per entity type (E2-001)."""
        findings = []

        # Group entities by type
        entities_by_type: Dict[str, List[EntityData]] = defaultdict(list)
        for entity in contract.entities:
            entities_by_type[entity.entity_type].append(entity)

        # Check sequence for each type
        for entity_type, entities in entities_by_type.items():
            # Get volgnums
            volgnums = [e.volgnum for e in entities if e.volgnum is not None]

            if not volgnums:
                continue

            # Sort and check sequence
            volgnums_sorted = sorted(volgnums)
            expected = list(range(1, len(volgnums) + 1))

            if volgnums_sorted != expected:
                # Find the specific issue
                missing = set(expected) - set(volgnums_sorted)
                duplicates = [v for v in volgnums_sorted if volgnums_sorted.count(v) > 1]

                if duplicates:
                    issue = f"duplicaten: {set(duplicates)}"
                elif missing:
                    issue = f"ontbrekend: {missing}"
                else:
                    issue = f"niet opeenvolgend: {volgnums_sorted}"

                findings.append(
                    Finding(
                        severity=Severity.FOUT,
                        engine=Engine.RULES,
                        code="E2-001",
                        regeltype="volgnum_niet_sequentieel",
                        contract=contract.contract_nummer,
                        branche=contract.branche,
                        entiteit=entity_type,
                        label=f"{entity_type}_VOLGNUM",
                        waarde=str(volgnums_sorted),
                        omschrijving=f"VOLGNUM voor {entity_type} is niet sequentieel: {issue}",
                        verwacht=f"Sequentieel: 1, 2, 3, ... ({len(volgnums)} entiteiten)",
                        bron="ADN business rules",
                    )
                )

        return findings

    def _check_premium_sum(self, contract: ContractData) -> List[Finding]:
        """Check if PP_BTP equals sum of coverage BTPs (E2-002)."""
        findings = []

        # Get PP entities
        pp_entities = contract.get_entities_by_type("PP")
        if not pp_entities:
            return findings

        for pp_entity in pp_entities:
            pp_btp_str = pp_entity.get_attr("BTP")
            if not pp_btp_str:
                continue

            try:
                pp_btp = Decimal(pp_btp_str)
            except (InvalidOperation, ValueError):
                continue

            # Sum up coverage BTPs
            coverage_btp_sum = Decimal("0")
            coverage_entities = contract.get_premium_entities()

            for cov_entity in coverage_entities:
                btp_str = cov_entity.get_attr("BTP")
                if btp_str:
                    try:
                        coverage_btp_sum += Decimal(btp_str)
                    except (InvalidOperation, ValueError):
                        pass

            # Check difference
            diff = abs(pp_btp - coverage_btp_sum)
            tolerance = Decimal(str(self.config.premium_tolerance_warning))

            if diff > tolerance:
                severity = Severity.FOUT if diff > Decimal("0.01") else Severity.WAARSCHUWING

                findings.append(
                    Finding(
                        severity=severity,
                        engine=Engine.RULES,
                        code="E2-002",
                        regeltype="premie_som_onjuist",
                        contract=contract.contract_nummer,
                        branche=contract.branche,
                        entiteit="PP",
                        label="PP_BTP",
                        waarde=str(pp_btp),
                        omschrijving=f"PP_BTP ({pp_btp}) != som dekkings-BTPs ({coverage_btp_sum}), verschil: {diff}",
                        verwacht=f"PP_BTP = som dekkings-BTPs (tolerantie: €0.01)",
                        bron="ADN business rules",
                    )
                )

        return findings

    def _check_multiple_prolmonths(self, batch: BatchData) -> List[Finding]:
        """Check for multiple prolongation months in batch (E2-003)."""
        findings = []

        prol_months = batch.get_prolongation_months()

        if len(prol_months) > 1:
            findings.append(
                Finding(
                    severity=Severity.FOUT,
                    engine=Engine.RULES,
                    code="E2-003",
                    regeltype="meerdere_prolongatiemaanden",
                    contract="BATCH",
                    branche="",
                    entiteit="PP",
                    label="PP_PROLMND",
                    waarde=str(sorted(prol_months)),
                    omschrijving=f"Batch bevat meerdere prolongatiemaanden: {sorted(prol_months)}",
                    verwacht="Één prolongatiemaand per batch",
                    bron="ADN business rules",
                )
            )

        return findings

    def _check_xd_entity(self, contract: ContractData) -> List[Finding]:
        """Check for forbidden XD entity (E2-004)."""
        findings = []

        xd_entities = contract.get_entities_by_type("XD")

        if xd_entities:
            for xd_entity in xd_entities:
                findings.append(
                    Finding(
                        severity=Severity.FOUT,
                        engine=Engine.RULES,
                        code="E2-004",
                        regeltype="xd_entiteit_verboden",
                        contract=contract.contract_nummer,
                        branche=contract.branche,
                        entiteit="XD",
                        label="XD_ENTITEI",
                        waarde=xd_entity.get_attr("ENTITEI") or "XD",
                        omschrijving="XD-entiteit is niet toegestaan in ADN-berichten",
                        verwacht="Geen XD-entiteit (systeemhuizen kunnen dit niet verwerken)",
                        bron="ADN business rules",
                    )
                )

        return findings

    def _check_bo_brprm(self, contract: ContractData) -> List[Finding]:
        """Check if BO_BRPRM equals PP_BTP (E2-005)."""
        findings = []

        # Get PP entities
        pp_entities = contract.get_entities_by_type("PP")
        if not pp_entities:
            return findings

        # Get BO entities
        bo_entities = contract.get_entities_by_type("BO")
        if not bo_entities:
            return findings

        # Sum PP_BTP
        pp_btp_total = Decimal("0")
        for pp_entity in pp_entities:
            pp_btp_str = pp_entity.get_attr("BTP")
            if pp_btp_str:
                try:
                    pp_btp_total += Decimal(pp_btp_str)
                except (InvalidOperation, ValueError):
                    pass

        # Sum BO_BRPRM
        bo_brprm_total = Decimal("0")
        for bo_entity in bo_entities:
            brprm_str = bo_entity.get_attr("BRPRM")
            if brprm_str:
                try:
                    bo_brprm_total += Decimal(brprm_str)
                except (InvalidOperation, ValueError):
                    pass

        # Check difference
        if pp_btp_total > 0 or bo_brprm_total > 0:
            diff = abs(pp_btp_total - bo_brprm_total)
            tolerance = Decimal(str(self.config.premium_tolerance_error))

            if diff > tolerance:
                findings.append(
                    Finding(
                        severity=Severity.FOUT,
                        engine=Engine.RULES,
                        code="E2-005",
                        regeltype="bo_brprm_afwijkend",
                        contract=contract.contract_nummer,
                        branche=contract.branche,
                        entiteit="BO",
                        label="BO_BRPRM",
                        waarde=str(bo_brprm_total),
                        omschrijving=f"BO_BRPRM ({bo_brprm_total}) != PP_BTP ({pp_btp_total}), verschil: {diff}",
                        verwacht=f"BO_BRPRM = PP_BTP (tolerantie: €{tolerance})",
                        bron="ADN business rules",
                    )
                )

        return findings

    def _check_date_logic(self, contract: ContractData) -> List[Finding]:
        """Check date logic: start date < end date (E2-006)."""
        findings = []

        # Date field pairs to check (ingangsdatum, einddatum)
        date_pairs = [
            ("INGDAT", "EINDDAT"),
            ("DVDAT", "DEDAT"),
            ("PROLDAT", "EINDDAT"),
        ]

        for entity in contract.get_all_entities_recursive():
            for start_field, end_field in date_pairs:
                start_date = entity.get_attr(start_field)
                end_date = entity.get_attr(end_field)

                if start_date and end_date and len(start_date) == 8 and len(end_date) == 8:
                    try:
                        # Compare as strings (YYYYMMDD format is sortable)
                        if start_date > end_date:
                            findings.append(Finding(
                                severity=Severity.FOUT,
                                engine=Engine.RULES,
                                code="E2-006",
                                regeltype="datum_logica_fout",
                                contract=contract.contract_nummer,
                                branche=contract.branche,
                                entiteit=entity.entity_type,
                                label=f"{entity.entity_type}_{start_field}/{end_field}",
                                waarde=f"{start_date} > {end_date}",
                                omschrijving=(
                                    f"Ingangsdatum ({start_date}) ligt na einddatum ({end_date})"
                                ),
                                verwacht="Ingangsdatum < Einddatum",
                                bron="ADN business rules",
                                regel=entity.line_number,
                            ))
                    except (ValueError, TypeError):
                        pass

        return findings

    def _check_postcode(self, contract: ContractData) -> List[Finding]:
        """Check Dutch postcode format (E2-007)."""
        findings = []

        for entity in contract.get_all_entities_recursive():
            postcode = entity.get_attr("PCODE")
            if postcode and not self.POSTCODE_PATTERN.match(postcode.upper()):
                findings.append(Finding(
                    severity=Severity.WAARSCHUWING,
                    engine=Engine.RULES,
                    code="E2-007",
                    regeltype="postcode_formaat_fout",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit=entity.entity_type,
                    label=f"{entity.entity_type}_PCODE",
                    waarde=postcode,
                    omschrijving=f"Postcode '{postcode}' voldoet niet aan Nederlands formaat",
                    verwacht="Formaat: 1234AB of 1234 AB",
                    bron="ADN business rules",
                    regel=entity.line_number,
                ))

        return findings

    def _check_bsn_kvk(self, contract: ContractData) -> List[Finding]:
        """Check BSN/KVK with 11-proef (E2-008)."""
        findings = []

        for entity in contract.get_all_entities_recursive():
            # Check BSN (can be BSN or SOFINR attribute)
            bsn = entity.get_attr("BSN") or entity.get_attr("SOFINR")
            if bsn:
                # Clean up BSN (remove spaces/dashes)
                bsn_clean = bsn.replace(" ", "").replace("-", "")
                if bsn_clean and not self._is_valid_bsn(bsn_clean):
                    findings.append(Finding(
                        severity=Severity.FOUT,
                        engine=Engine.RULES,
                        code="E2-008",
                        regeltype="bsn_ongeldig",
                        contract=contract.contract_nummer,
                        branche=contract.branche,
                        entiteit=entity.entity_type,
                        label=f"{entity.entity_type}_BSN",
                        waarde=bsn,
                        omschrijving=f"BSN '{bsn}' voldoet niet aan 11-proef",
                        verwacht="Geldig BSN (11-proef)",
                        bron="ADN business rules",
                        regel=entity.line_number,
                    ))

            # Check KVK number
            kvk = entity.get_attr("KVK") or entity.get_attr("KVKNR")
            if kvk:
                kvk_clean = kvk.replace(" ", "").replace("-", "")
                if kvk_clean and not self._is_valid_kvk(kvk_clean):
                    findings.append(Finding(
                        severity=Severity.WAARSCHUWING,
                        engine=Engine.RULES,
                        code="E2-008",
                        regeltype="kvk_ongeldig",
                        contract=contract.contract_nummer,
                        branche=contract.branche,
                        entiteit=entity.entity_type,
                        label=f"{entity.entity_type}_KVK",
                        waarde=kvk,
                        omschrijving=f"KVK-nummer '{kvk}' heeft ongeldig formaat",
                        verwacht="8-cijferig KVK-nummer",
                        bron="ADN business rules",
                        regel=entity.line_number,
                    ))

        return findings

    def _is_valid_bsn(self, bsn: str) -> bool:
        """Validate BSN with 11-proef."""
        if not bsn or len(bsn) != 9 or not bsn.isdigit():
            return False

        # 11-proef for BSN
        # Weighting: 9, 8, 7, 6, 5, 4, 3, 2, -1
        weights = [9, 8, 7, 6, 5, 4, 3, 2, -1]
        total = sum(int(d) * w for d, w in zip(bsn, weights))
        return total % 11 == 0

    def _is_valid_kvk(self, kvk: str) -> bool:
        """Validate KVK number format."""
        # KVK numbers are 8 digits
        if not kvk or len(kvk) != 8 or not kvk.isdigit():
            return False
        return True

    def _check_duplicates(self, contract: ContractData) -> List[Finding]:
        """Check for duplicate entities (E2-009)."""
        findings = []
        seen: Dict[Tuple[str, Optional[int]], EntityData] = {}

        for entity in contract.get_all_entities_recursive():
            key = (entity.entity_type, entity.volgnum)

            if key in seen and entity.volgnum is not None:
                original = seen[key]
                findings.append(Finding(
                    severity=Severity.WAARSCHUWING,
                    engine=Engine.RULES,
                    code="E2-009",
                    regeltype="duplicaat_entiteit",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit=entity.entity_type,
                    label=f"{entity.entity_type}_VOLGNUM",
                    waarde=str(entity.volgnum),
                    omschrijving=(
                        f"Duplicaat {entity.entity_type} met VOLGNUM {entity.volgnum} "
                        f"(eerste op regel {original.line_number}, tweede op regel {entity.line_number})"
                    ),
                    verwacht="Unieke VOLGNUM per entiteitstype",
                    bron="ADN business rules",
                    regel=entity.line_number,
                ))
            else:
                seen[key] = entity

        return findings

    def _check_pp_ttot(self, contract: ContractData) -> List[Finding]:
        """Check PP_TTOT = PP_BTP + PP_TASS + PP_TKST + PP_TKRT + PP_TTSL (E2-010)."""
        findings = []

        pp_entities = contract.get_entities_by_type("PP")
        if not pp_entities:
            return findings

        for pp_entity in pp_entities:
            pp_ttot_str = pp_entity.get_attr("TTOT")
            if not pp_ttot_str:
                continue

            try:
                pp_ttot = Decimal(pp_ttot_str)
            except (InvalidOperation, ValueError):
                continue

            # Sum the component fields
            component_fields = ["BTP", "TASS", "TKST", "TKRT", "TTSL"]
            calculated_total = Decimal("0")
            components_found = []

            for field in component_fields:
                value_str = pp_entity.get_attr(field)
                if value_str:
                    try:
                        value = Decimal(value_str)
                        calculated_total += value
                        components_found.append(f"PP_{field}={value}")
                    except (InvalidOperation, ValueError):
                        pass

            # Check if there's a significant difference
            diff = abs(pp_ttot - calculated_total)
            tolerance = Decimal(str(self.config.premium_tolerance_error))

            if diff > tolerance and components_found:
                findings.append(Finding(
                    severity=Severity.FOUT,
                    engine=Engine.RULES,
                    code="E2-010",
                    regeltype="pp_ttot_som_onjuist",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit="PP",
                    label="PP_TTOT",
                    waarde=str(pp_ttot),
                    omschrijving=(
                        f"PP_TTOT ({pp_ttot}) != som componenten ({calculated_total}), "
                        f"verschil: {diff}. Componenten: {', '.join(components_found)}"
                    ),
                    verwacht="PP_TTOT = PP_BTP + PP_TASS + PP_TKST + PP_TKRT + PP_TTSL",
                    bron="ADN business rules",
                    regel=pp_entity.line_number,
                ))

        return findings

    def _check_iban(self, contract: ContractData) -> List[Finding]:
        """Check IBAN format and checksum (E2-011)."""
        findings = []

        for entity in contract.get_all_entities_recursive():
            # Look for IBAN fields (various naming conventions)
            iban_fields = ["IBAN", "IBANR", "IBANNR", "BANKNR"]

            for field in iban_fields:
                iban = entity.get_attr(field)
                if iban:
                    # Clean up IBAN (remove spaces)
                    iban_clean = iban.replace(" ", "").upper()

                    if iban_clean and not self._is_valid_iban(iban_clean):
                        findings.append(Finding(
                            severity=Severity.FOUT,
                            engine=Engine.RULES,
                            code="E2-011",
                            regeltype="iban_ongeldig",
                            contract=contract.contract_nummer,
                            branche=contract.branche,
                            entiteit=entity.entity_type,
                            label=f"{entity.entity_type}_{field}",
                            waarde=iban,
                            omschrijving=f"IBAN '{iban}' is ongeldig (formaat of checksum fout)",
                            verwacht="Geldig IBAN (bijv. NL91ABNA0417164300)",
                            bron="ADN business rules",
                            regel=entity.line_number,
                        ))

        return findings

    def _is_valid_iban(self, iban: str) -> bool:
        """Validate IBAN using modulo 97 check."""
        # IBAN must be at least 15 characters (shortest valid IBAN)
        if not iban or len(iban) < 15 or len(iban) > 34:
            return False

        # First 2 characters must be letters (country code)
        if not iban[:2].isalpha():
            return False

        # Characters 3-4 must be digits (check digits)
        if not iban[2:4].isdigit():
            return False

        # Move first 4 characters to the end
        rearranged = iban[4:] + iban[:4]

        # Convert letters to numbers (A=10, B=11, ..., Z=35)
        numeric_string = ""
        for char in rearranged:
            if char.isdigit():
                numeric_string += char
            elif char.isalpha():
                numeric_string += str(ord(char.upper()) - ord('A') + 10)
            else:
                return False

        # Check if modulo 97 equals 1
        try:
            return int(numeric_string) % 97 == 1
        except ValueError:
            return False

    def _check_prolongation_consistency(self, contract: ContractData) -> List[Finding]:
        """Check betaaltermijn/prolongatie consistency (E2-012)."""
        findings = []

        pp_entities = contract.get_entities_by_type("PP")
        if not pp_entities:
            return findings

        for pp_entity in pp_entities:
            ingdat = pp_entity.get_attr("INGDAT")
            proldat = pp_entity.get_attr("PROLDAT")
            betterm = pp_entity.get_attr("BETTERM")

            # All three fields must be present for this check
            if not ingdat or not proldat or not betterm:
                continue

            # Parse dates (YYYYMMDD format)
            if len(ingdat) != 8 or len(proldat) != 8:
                continue

            try:
                ing_month = int(ingdat[4:6])
                ing_day = int(ingdat[6:8])
                prol_month = int(proldat[4:6])
                prol_day = int(proldat[6:8])
                term_months = int(betterm) if betterm.isdigit() else 0
            except ValueError:
                continue

            # For 12-month term, prolongation date month/day should match start date
            if term_months == 12:
                # Check if day matches (allowing for month-end variations)
                if ing_month != prol_month and ing_day != prol_day:
                    findings.append(Finding(
                        severity=Severity.WAARSCHUWING,
                        engine=Engine.RULES,
                        code="E2-012",
                        regeltype="prolongatie_inconsistent",
                        contract=contract.contract_nummer,
                        branche=contract.branche,
                        entiteit="PP",
                        label="PP_PROLDAT",
                        waarde=proldat,
                        omschrijving=(
                            f"Bij 12-maands termijn (betaaltermijn={betterm}) "
                            f"moet prolongatiedatum ({proldat}) overeenkomen met "
                            f"ingangsdatum ({ingdat}) qua maand/dag"
                        ),
                        verwacht=f"Prolongatiedatum dag {ing_day:02d} van maand {ing_month:02d}",
                        bron="ADN business rules",
                        regel=pp_entity.line_number,
                    ))

        return findings

    def _check_branch_coverage_compatibility(self, contract: ContractData) -> List[Finding]:
        """Check if coverage entities are valid for the branch (E2-013)."""
        findings = []

        # Get branch code (standardize to 3 digits)
        branche = contract.branche.zfill(3) if contract.branche else ""
        if not branche:
            return findings

        # Check if we have branch rules
        branch_rules = self.BRANCH_COVERAGE_MAPPING.get(branche)
        if not branch_rules:
            return findings

        # Get all coverage entity types present in contract
        coverage_entities = contract.get_premium_entities()
        coverage_types = {e.entity_type for e in coverage_entities}

        # Check for forbidden entities
        forbidden = branch_rules.get("forbidden", set())
        for entity_type in coverage_types & forbidden:
            findings.append(Finding(
                severity=Severity.FOUT,
                engine=Engine.RULES,
                code="E2-013",
                regeltype="branche_dekking_mismatch",
                contract=contract.contract_nummer,
                branche=contract.branche,
                entiteit=entity_type,
                label=f"{entity_type}_ENTITEI",
                waarde=entity_type,
                omschrijving=(
                    f"Dekking-entiteit {entity_type} is niet toegestaan "
                    f"voor branche {branche} ({branch_rules.get('description', '')})"
                ),
                verwacht=f"Geen {entity_type} entiteit bij branche {branche}",
                bron="ADN business rules",
            ))

        return findings

    def _check_ingangsdatum_new_policy(self, contract: ContractData) -> List[Finding]:
        """Check if ingangsdatum is not in past for new policies (E2-014)."""
        findings = []
        from datetime import datetime

        pp_entities = contract.get_entities_by_type("PP")
        if not pp_entities:
            return findings

        today = datetime.now().strftime("%Y%m%d")

        for pp_entity in pp_entities:
            # Check mutatievlag - only check new policies (N = nieuw)
            mutefg = pp_entity.get_attr("MUTEFG")
            if mutefg not in ("N", ""):  # N = nieuw, empty might also be new
                continue

            ingdat = pp_entity.get_attr("INGDAT")
            if not ingdat or len(ingdat) != 8:
                continue

            # Check if ingangsdatum is in the past (allow some grace period)
            # Only warn, don't error - there may be legitimate backdated policies
            if ingdat < today:
                findings.append(Finding(
                    severity=Severity.WAARSCHUWING,
                    engine=Engine.RULES,
                    code="E2-014",
                    regeltype="ingangsdatum_verleden",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit="PP",
                    label="PP_INGDAT",
                    waarde=ingdat,
                    omschrijving=(
                        f"Ingangsdatum ({ingdat}) ligt in het verleden "
                        f"voor een nieuwe polis (mutefg={mutefg or 'leeg'})"
                    ),
                    verwacht=f"Ingangsdatum >= {today} voor nieuwe polissen",
                    bron="ADN business rules",
                    regel=pp_entity.line_number,
                ))

        return findings

    def _check_verzekerde_som_maximum(self, contract: ContractData) -> List[Finding]:
        """Check if verzekerde som doesn't exceed maximum (E2-015)."""
        findings = []

        for entity in contract.get_all_entities_recursive():
            for attr_suffix, max_value in self.MAX_VERZEKERDE_SOM.items():
                # Check if this attribute applies to this entity
                entity_prefix = attr_suffix.split("_")[0]
                if entity.entity_type != entity_prefix:
                    continue

                attr_name = attr_suffix
                value_str = entity.get_attr(attr_suffix.split("_")[1])
                if not value_str:
                    continue

                try:
                    value = Decimal(value_str)
                    if value > max_value:
                        findings.append(Finding(
                            severity=Severity.WAARSCHUWING,
                            engine=Engine.RULES,
                            code="E2-015",
                            regeltype="verzekerde_som_maximum",
                            contract=contract.contract_nummer,
                            branche=contract.branche,
                            entiteit=entity.entity_type,
                            label=f"{entity.entity_type}_{attr_suffix.split('_')[1]}",
                            waarde=value_str,
                            omschrijving=(
                                f"Verzekerde som ({value}) overschrijdt "
                                f"gebruikelijk maximum ({max_value})"
                            ),
                            verwacht=f"Waarde <= {max_value}",
                            bron="ADN business rules",
                            regel=entity.line_number,
                        ))
                except (InvalidOperation, ValueError):
                    pass

        return findings

    def _check_coverage_combinations(self, contract: ContractData) -> List[Finding]:
        """Check for forbidden coverage combinations (E2-016)."""
        findings = []

        # Get all coverage entities with their codes
        coverage_entities = contract.get_premium_entities()
        coverage_by_type: Dict[str, Set[str]] = defaultdict(set)

        for entity in coverage_entities:
            code = entity.get_attr("CODE")
            if code:
                coverage_by_type[entity.entity_type].add(code)

        # Check forbidden combinations
        for ent1, code1, ent2, code2, description in self.FORBIDDEN_COVERAGE_COMBINATIONS:
            if code1 in coverage_by_type.get(ent1, set()) and \
               code2 in coverage_by_type.get(ent2, set()):
                findings.append(Finding(
                    severity=Severity.WAARSCHUWING,
                    engine=Engine.RULES,
                    code="E2-016",
                    regeltype="ongeldige_dekkingscombinatie",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit=f"{ent1}/{ent2}",
                    label=f"{ent1}_CODE/{ent2}_CODE",
                    waarde=f"{code1}/{code2}",
                    omschrijving=f"Ongeldige dekkingscombinatie: {description}",
                    verwacht="Dekkingen mogen niet tegelijk actief zijn",
                    bron="ADN business rules",
                ))

        return findings

    def _check_object_type_branch(self, contract: ContractData) -> List[Finding]:
        """Check if object type matches branch requirements (E2-017)."""
        findings = []

        # Get branch code (standardize to 3 digits)
        branche = contract.branche.zfill(3) if contract.branche else ""
        if not branche:
            return findings

        # Check if this branch requires a specific object entity
        required_object = self.BRANCH_OBJECT_MAPPING.get(branche)
        if not required_object:
            return findings

        # Check if the required object entity is present
        object_entities = contract.get_entities_by_type_recursive(required_object)
        if not object_entities:
            findings.append(Finding(
                severity=Severity.WAARSCHUWING,
                engine=Engine.RULES,
                code="E2-017",
                regeltype="object_branche_mismatch",
                contract=contract.contract_nummer,
                branche=contract.branche,
                entiteit=required_object,
                label=f"{required_object}_ENTITEI",
                waarde="",
                omschrijving=(
                    f"Branche {branche} vereist {required_object}-entiteit "
                    f"maar deze ontbreekt"
                ),
                verwacht=f"{required_object}-entiteit aanwezig",
                bron="ADN business rules",
            ))

        return findings
