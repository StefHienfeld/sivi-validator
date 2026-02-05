"""XSD parser for extracting schema information from SIVI XSD files."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Set, Tuple
from lxml import etree

from config import Config, get_config


@dataclass
class FormatSpec:
    """Specification for a format type."""

    name: str
    base_type: str  # e.g., "Alphanumeric", "Numeric", "xs:decimal"
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    total_digits: Optional[int] = None
    fraction_digits: Optional[int] = None
    parent_format: Optional[str] = None  # For inheritance (e.g., codeB2 -> Bn)

    def is_decimal_format(self) -> bool:
        """Check if this format is a decimal type (Bn, Pn, An)."""
        return self.base_type in ("decimal", "Bn", "Pn", "An") or self.name.startswith(("codeB", "codeP", "codeA"))

    def is_amount_format(self) -> bool:
        """Check if this format is a Bn (Bedrag/Amount) type."""
        return self.base_type == "Bn" or self.name.startswith("codeB") or self.name == "Bn"

    def is_percentage_format(self) -> bool:
        """Check if this format is a Pn (Percentage) type."""
        return self.base_type == "Pn" or self.name.startswith("codeP") or self.name == "Pn"

    def is_quantity_format(self) -> bool:
        """Check if this format is an An (Aantal/Quantity) type."""
        return self.base_type == "An" or self.name.startswith("codeA") or self.name == "An"

    def get_effective_total_digits(self) -> Optional[int]:
        """Get effective total digits (considering inheritance)."""
        if self.total_digits is not None:
            return self.total_digits
        # Default values for base types
        if self.is_amount_format():
            return 15  # Default for Bn
        if self.is_percentage_format():
            return 8   # Default for Pn
        if self.is_quantity_format():
            return 15  # Default for An
        return None

    def get_effective_fraction_digits(self) -> Optional[int]:
        """Get effective fraction digits (considering inheritance)."""
        return self.fraction_digits

    def validate_decimal_value(self, value: str) -> Tuple[bool, str]:
        """
        Validate a decimal value against this format spec.

        Returns (is_valid, error_message).
        """
        if not value or not self.is_decimal_format():
            return True, ""

        # Clean value
        clean_value = value.strip().replace(",", ".")

        # Check if it's a valid decimal
        try:
            dec_value = Decimal(clean_value)
        except (InvalidOperation, ValueError):
            return False, f"Ongeldige decimale waarde: {value}"

        # Check total digits
        total_digits = self.get_effective_total_digits()
        if total_digits is not None:
            # Count significant digits (excluding leading zeros and decimal point)
            sign, digits, exp = dec_value.as_tuple()
            digit_count = len(digits)
            if digit_count > total_digits:
                return False, f"Te veel cijfers: {digit_count} (max {total_digits})"

        # Check fraction digits
        fraction_digits = self.get_effective_fraction_digits()
        if fraction_digits is not None:
            # Count decimal places
            if "." in clean_value:
                decimal_places = len(clean_value.split(".")[1])
                if decimal_places > fraction_digits:
                    return False, f"Te veel decimalen: {decimal_places} (max {fraction_digits})"

        return True, ""


@dataclass
class SchemaLookup:
    """Lookup tables derived from XSD files."""

    # From formaten.xsd: format name -> FormatSpec
    formats: Dict[str, FormatSpec] = field(default_factory=dict)

    # From codelist.xsd: codelist name -> set of valid values
    codelists: Dict[str, Set[str]] = field(default_factory=dict)

    # From attributen.xsd: attribute name -> format or codelist name
    attributes: Dict[str, str] = field(default_factory=dict)

    # From entiteiten.xsd: entity code -> set of valid attribute names
    entities: Dict[str, Set[str]] = field(default_factory=dict)

    # From dekkingcodesgroup.xsd: entity code -> set of valid coverage codes
    coverage_codes: Dict[str, Set[str]] = field(default_factory=dict)

    # Business-required attributes per entity (not from XSD, but from ADN rules)
    required_attributes: Dict[str, Set[str]] = field(default_factory=dict)

    def is_valid_attribute_for_entity(self, entity: str, attribute: str) -> bool:
        """Check if an attribute is valid for an entity."""
        if entity not in self.entities:
            return False
        return attribute in self.entities[entity]

    def is_valid_coverage_code(self, entity: str, code: str) -> bool:
        """Check if a coverage code is valid for an entity."""
        if entity not in self.coverage_codes:
            # Entity doesn't have specific coverage codes
            return True
        return code in self.coverage_codes[entity]

    def get_valid_coverage_codes(self, entity: str) -> Set[str]:
        """Get valid coverage codes for an entity."""
        return self.coverage_codes.get(entity, set())

    def get_format_for_attribute(self, attribute: str) -> Optional[FormatSpec]:
        """Get the format specification for an attribute."""
        # Remove entity prefix (e.g., "VP_ANAAM" -> "_ANAAM")
        attr_suffix = "_" + attribute.split("_", 1)[1] if "_" in attribute else attribute

        format_name = self.attributes.get(attr_suffix)
        if not format_name:
            return None

        # Check if it's a codelist reference
        if format_name.startswith("cl:"):
            format_name = format_name[3:]
        if format_name.startswith("fm:"):
            format_name = format_name[3:]

        return self.formats.get(format_name)

    def is_codelist_attribute(self, attribute: str) -> bool:
        """Check if an attribute uses a codelist."""
        attr_suffix = "_" + attribute.split("_", 1)[1] if "_" in attribute else attribute
        format_ref = self.attributes.get(attr_suffix, "")
        return format_ref.startswith("cl:") or format_ref in self.codelists

    def get_codelist_for_attribute(self, attribute: str) -> Optional[Set[str]]:
        """Get the valid codelist values for an attribute."""
        attr_suffix = "_" + attribute.split("_", 1)[1] if "_" in attribute else attribute
        format_ref = self.attributes.get(attr_suffix, "")

        if format_ref.startswith("cl:"):
            codelist_name = format_ref[3:]
        else:
            codelist_name = format_ref

        return self.codelists.get(codelist_name)

    def get_codelist_name_for_attribute(self, attribute: str) -> Optional[str]:
        """Get the codelist name for an attribute (if it uses a codelist)."""
        attr_suffix = "_" + attribute.split("_", 1)[1] if "_" in attribute else attribute
        format_ref = self.attributes.get(attr_suffix, "")

        if format_ref.startswith("cl:"):
            return format_ref[3:]
        elif format_ref in self.codelists:
            return format_ref
        return None

    def get_required_attributes(self, entity: str) -> Set[str]:
        """Get required attributes for an entity based on business rules."""
        return self.required_attributes.get(entity, set())

    def is_required_attribute(self, entity: str, attribute: str) -> bool:
        """Check if an attribute is required for an entity."""
        required = self.required_attributes.get(entity, set())
        # Extract suffix from attribute name
        attr_suffix = attribute.split("_", 1)[1] if "_" in attribute else attribute
        return attr_suffix in required or attribute in required

    def is_decimal_attribute(self, attribute: str) -> bool:
        """Check if an attribute has a decimal format (Bn, Pn, An)."""
        format_spec = self.get_format_for_attribute(attribute)
        return format_spec is not None and format_spec.is_decimal_format()

    def is_amount_attribute(self, attribute: str) -> bool:
        """Check if an attribute is a Bn (Bedrag/Amount) type."""
        format_spec = self.get_format_for_attribute(attribute)
        return format_spec is not None and format_spec.is_amount_format()

    def validate_decimal_precision(self, attribute: str, value: str) -> Tuple[bool, str]:
        """
        Validate decimal precision for an attribute value.

        Returns (is_valid, error_message).
        """
        format_spec = self.get_format_for_attribute(attribute)
        if format_spec is None:
            return True, ""
        return format_spec.validate_decimal_value(value)


class XSDParser:
    """Parser for SIVI XSD files."""

    # XML Schema namespace
    XS_NS = "{http://www.w3.org/2001/XMLSchema}"

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self._lookup: Optional[SchemaLookup] = None

    def parse_all(self) -> SchemaLookup:
        """Parse all XSD files and return a SchemaLookup."""
        if self._lookup is not None:
            return self._lookup

        lookup = SchemaLookup()

        # Parse in order of dependencies
        self._parse_formaten(lookup)
        self._parse_codelist(lookup)
        self._parse_attributen(lookup)
        self._parse_entiteiten(lookup)
        self._parse_dekkingcodes(lookup)

        # Load business-required attributes
        self._load_required_attributes(lookup)

        self._lookup = lookup
        return lookup

    def _parse_formaten(self, lookup: SchemaLookup) -> None:
        """Parse formaten.xsd to extract format specifications."""
        tree = etree.parse(str(self.config.formaten_path))
        root = tree.getroot()

        # First pass: parse all formats
        for simple_type in root.findall(f"{self.XS_NS}simpleType"):
            name = simple_type.get("name")
            if not name:
                continue

            spec = FormatSpec(name=name, base_type="")

            restriction = simple_type.find(f"{self.XS_NS}restriction")
            if restriction is not None:
                base = restriction.get("base", "")
                # Remove namespace prefix
                base_clean = base.split(":")[-1] if ":" in base else base
                spec.base_type = base_clean

                # Track parent format for inheritance
                if base_clean not in ("string", "decimal", "gYear", "base64Binary"):
                    spec.parent_format = base_clean

                # Parse restrictions
                for child in restriction:
                    tag = child.tag.replace(self.XS_NS, "")
                    value = child.get("value")

                    if tag == "minLength" and value:
                        spec.min_length = int(value)
                    elif tag == "maxLength" and value:
                        spec.max_length = int(value)
                    elif tag == "length" and value:
                        spec.min_length = int(value)
                        spec.max_length = int(value)
                    elif tag == "pattern" and value:
                        spec.pattern = value
                    elif tag == "totalDigits" and value:
                        spec.total_digits = int(value)
                    elif tag == "fractionDigits" and value:
                        spec.fraction_digits = int(value)

            lookup.formats[name] = spec

        # Second pass: resolve inheritance for totalDigits/fractionDigits
        self._resolve_format_inheritance(lookup)

    def _parse_codelist(self, lookup: SchemaLookup) -> None:
        """Parse codelist.xsd to extract code enumerations."""
        tree = etree.parse(str(self.config.codelist_path))
        root = tree.getroot()

        for simple_type in root.findall(f"{self.XS_NS}simpleType"):
            name = simple_type.get("name")
            if not name:
                continue

            values = set()
            restriction = simple_type.find(f"{self.XS_NS}restriction")
            if restriction is not None:
                for enum in restriction.findall(f"{self.XS_NS}enumeration"):
                    value = enum.get("value")
                    if value:
                        values.add(value)

            if values:
                lookup.codelists[name] = values

    def _parse_attributen(self, lookup: SchemaLookup) -> None:
        """Parse attributen.xsd to extract attribute-to-format mappings."""
        tree = etree.parse(str(self.config.attributen_path))
        root = tree.getroot()

        for simple_type in root.findall(f"{self.XS_NS}simpleType"):
            name = simple_type.get("name")
            if not name:
                continue

            restriction = simple_type.find(f"{self.XS_NS}restriction")
            if restriction is not None:
                base = restriction.get("base", "")
                # Keep the namespace prefix to distinguish fm: and cl:
                lookup.attributes[name] = base

    def _parse_entiteiten(self, lookup: SchemaLookup) -> None:
        """Parse entiteiten.xsd to extract entity-to-attributes mappings."""
        tree = etree.parse(str(self.config.entiteiten_path))
        root = tree.getroot()

        for complex_type in root.findall(f"{self.XS_NS}complexType"):
            name = complex_type.get("name")
            if not name:
                continue

            # Entity names are typically 2 characters
            if len(name) != 2:
                continue

            attributes = set()
            sequence = complex_type.find(f"{self.XS_NS}sequence")
            if sequence is not None:
                for child in sequence:
                    if child.tag == f"{self.XS_NS}element":
                        elem_name = child.get("name")
                        if elem_name:
                            attributes.add(elem_name)
                    elif child.tag == f"{self.XS_NS}group":
                        # Handle group references like <xs:group ref="dg:AN_CODEGroup"/>
                        ref = child.get("ref", "")
                        if "_CODEGroup" in ref:
                            # Extract element name from group ref
                            # e.g., "dg:AN_CODEGroup" -> "AN_CODE"
                            group_name = ref.split(":")[-1] if ":" in ref else ref
                            code_elem = group_name.replace("Group", "")
                            attributes.add(code_elem)

            if attributes:
                lookup.entities[name] = attributes

    def _parse_dekkingcodes(self, lookup: SchemaLookup) -> None:
        """Parse dekkingcodesgroup.xsd to extract coverage codes per entity."""
        tree = etree.parse(str(self.config.dekkingcodes_path))
        root = tree.getroot()

        for group in root.findall(f"{self.XS_NS}group"):
            name = group.get("name")
            if not name or not name.endswith("_CODEGroup"):
                continue

            # Extract entity code from group name (e.g., "AN_CODEGroup" -> "AN")
            entity_code = name.replace("_CODEGroup", "")

            codes = set()
            # Find the element with enumerations
            for element in group.iter(f"{self.XS_NS}element"):
                simple_type = element.find(f"{self.XS_NS}simpleType")
                if simple_type is not None:
                    restriction = simple_type.find(f"{self.XS_NS}restriction")
                    if restriction is not None:
                        for enum in restriction.findall(f"{self.XS_NS}enumeration"):
                            value = enum.get("value")
                            if value:
                                codes.add(value)

            if codes:
                lookup.coverage_codes[entity_code] = codes

    def _load_required_attributes(self, lookup: SchemaLookup) -> None:
        """Load business-required attributes per entity.

        These are not XSD-defined requirements, but business rules based on
        ADN protocol specifications. VOLGNUM is typically required for most entities.
        ENTITEI (entity type indicator) is typically required.
        """
        # Define required attributes per entity based on ADN business rules
        # These are attributes that should logically be present for proper processing

        # Common required attributes for most entities
        common_required = {"VOLGNUM", "ENTITEI"}

        # Entity-specific required attributes
        required_attrs = {
            # AL - Algemeen (General info)
            "AL": {"VOLGNUM", "ENTITEI", "CNTRNUM"},

            # PP - Polispakket (Policy package)
            "PP": {"VOLGNUM", "ENTITEI", "INGDAT", "BTP"},

            # BO - Branche Object
            "BO": {"VOLGNUM", "ENTITEI", "BRANCHE"},

            # VP - Verzekeringsplichtige (Policyholder)
            "VP": {"VOLGNUM", "ENTITEI"},

            # Coverage entities typically need VOLGNUM and CODE
            "AN": {"VOLGNUM", "CODE"},
            "CA": {"VOLGNUM", "CODE"},
            "AH": {"VOLGNUM", "CODE"},
            "DA": {"VOLGNUM"},
            "DR": {"VOLGNUM", "CODE"},

            # PV - Polisvorm/Voertuig
            "PV": {"VOLGNUM"},

            # Other common entities
            "AD": {"VOLGNUM"},  # Adres
            "RC": {"VOLGNUM"},  # Relatiecode
            "CM": {"VOLGNUM"},  # Communicatie
        }

        lookup.required_attributes = required_attrs

    def _resolve_format_inheritance(self, lookup: SchemaLookup) -> None:
        """Resolve inheritance for format specifications.

        For formats that extend base types (e.g., codeB2 extends Bn),
        inherit totalDigits if not specified locally.
        """
        for format_name, spec in lookup.formats.items():
            if spec.parent_format and spec.parent_format in lookup.formats:
                parent = lookup.formats[spec.parent_format]

                # Inherit totalDigits if not set
                if spec.total_digits is None and parent.total_digits is not None:
                    spec.total_digits = parent.total_digits

                # Note: fractionDigits is typically overridden, not inherited
                # but we can inherit if not set
                if spec.fraction_digits is None and parent.fraction_digits is not None:
                    spec.fraction_digits = parent.fraction_digits


# Convenience function for getting a cached lookup
_cached_lookup: Optional[SchemaLookup] = None


def get_schema_lookup(config: Optional[Config] = None) -> SchemaLookup:
    """Get a cached schema lookup."""
    global _cached_lookup
    if _cached_lookup is None:
        parser = XSDParser(config)
        _cached_lookup = parser.parse_all()
    return _cached_lookup
