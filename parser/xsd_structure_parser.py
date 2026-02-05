"""XSD structure parser for extracting hierarchy rules from Contractberichtstructuur.xsd."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Set
from lxml import etree

from config import Config, get_config


@dataclass
class ElementStructure:
    """Structure definition for an element in the hierarchy."""

    name: str
    type_name: str
    min_occurs: int = 0
    max_occurs: Optional[int] = None  # None = unbounded
    allowed_children: Set[str] = field(default_factory=set)
    required_children: Set[str] = field(default_factory=set)


@dataclass
class StructureLookup:
    """Lookup tables for XML structure validation."""

    # Element name -> ElementStructure
    elements: Dict[str, ElementStructure] = field(default_factory=dict)

    # Child -> Set of valid parents
    child_to_parents: Dict[str, Set[str]] = field(default_factory=dict)

    # Root level elements (direct children of Contractberichtstructuur)
    root_elements: Set[str] = field(default_factory=set)

    def is_valid_parent(self, child: str, parent: str) -> bool:
        """Check if child is valid under parent."""
        if parent not in self.elements:
            return True  # Unknown parent, skip validation
        return child in self.elements[parent].allowed_children

    def is_valid_at_root(self, element: str) -> bool:
        """Check if element can appear at root level (under Contract)."""
        return element in self.root_elements

    def get_allowed_parents(self, child: str) -> Set[str]:
        """Get all valid parents for a child element."""
        return self.child_to_parents.get(child, set())

    def get_allowed_children(self, parent: str) -> Set[str]:
        """Get all valid children for a parent element."""
        if parent not in self.elements:
            return set()
        return self.elements[parent].allowed_children

    def get_required_children(self, parent: str) -> Set[str]:
        """Get required children for a parent element."""
        if parent not in self.elements:
            return set()
        return self.elements[parent].required_children

    def is_entity_type(self, name: str) -> bool:
        """Check if name is a 2-char entity type."""
        return len(name) == 2 and name.isupper()


class XSDStructureParser:
    """Parser for hierarchy structure from Contractberichtstructuur.xsd."""

    XS_NS = "{http://www.w3.org/2001/XMLSchema}"

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self._lookup: Optional[StructureLookup] = None

    def parse(self, xsd_path: Optional[Path] = None) -> StructureLookup:
        """Parse XSD and extract hierarchy rules."""
        if self._lookup is not None:
            return self._lookup

        if xsd_path is None:
            xsd_path = self.config.contractbericht_xsd_path

        if not xsd_path.exists():
            # Return empty lookup if XSD not found
            return StructureLookup()

        tree = etree.parse(str(xsd_path))
        root = tree.getroot()
        lookup = StructureLookup()

        # Find the Contractberichtstructuur complexType
        for complex_type in root.findall(f".//{self.XS_NS}complexType"):
            name = complex_type.get("name")
            if name == "Contractberichtstructuur":
                self._parse_structure_type(complex_type, lookup, is_root=True)
                break

        # Build reverse lookup (child -> parents)
        for parent_name, element in lookup.elements.items():
            for child_name in element.allowed_children:
                if child_name not in lookup.child_to_parents:
                    lookup.child_to_parents[child_name] = set()
                lookup.child_to_parents[child_name].add(parent_name)

        self._lookup = lookup
        return lookup

    def _parse_structure_type(
        self,
        complex_type: etree._Element,
        lookup: StructureLookup,
        is_root: bool = False,
        parent_name: str = "Contract"
    ) -> None:
        """Parse a complexType and extract child elements."""
        # Find sequence
        sequence = complex_type.find(f".//{self.XS_NS}sequence")
        if sequence is None:
            return

        if is_root:
            # Create root element structure
            root_struct = ElementStructure(
                name="Contract",
                type_name="Contractberichtstructuur"
            )
            lookup.elements["Contract"] = root_struct
            parent_name = "Contract"

        for elem in sequence:
            if elem.tag == f"{self.XS_NS}element":
                self._parse_element(elem, lookup, parent_name, is_root)

    def _parse_element(
        self,
        elem: etree._Element,
        lookup: StructureLookup,
        parent_name: str,
        is_root: bool
    ) -> None:
        """Parse a single element and its nested structure."""
        name = elem.get("name")
        if not name or len(name) != 2:
            return  # Only process 2-char entity names

        # Get occurrences
        min_occurs = int(elem.get("minOccurs", "1"))
        max_occurs_str = elem.get("maxOccurs", "1")
        max_occurs = None if max_occurs_str == "unbounded" else int(max_occurs_str)

        # Add to parent's allowed children
        if parent_name in lookup.elements:
            lookup.elements[parent_name].allowed_children.add(name)
            if min_occurs >= 1:
                lookup.elements[parent_name].required_children.add(name)

        if is_root:
            lookup.root_elements.add(name)

        # Create structure for this element if it has nested children
        element_struct = ElementStructure(
            name=name,
            type_name=name,
            min_occurs=min_occurs,
            max_occurs=max_occurs
        )
        lookup.elements[name] = element_struct

        # Check for nested complexType with children
        nested_complex = elem.find(f"./{self.XS_NS}complexType")
        if nested_complex is not None:
            self._parse_nested_complex(nested_complex, lookup, name)

    def _parse_nested_complex(
        self,
        complex_type: etree._Element,
        lookup: StructureLookup,
        parent_name: str
    ) -> None:
        """Parse nested complexType for child elements."""
        # Look for sequence in complexContent/extension or directly
        sequences = []

        # Direct sequence
        direct_seq = complex_type.find(f"./{self.XS_NS}sequence")
        if direct_seq is not None:
            sequences.append(direct_seq)

        # Sequence in complexContent/extension
        complex_content = complex_type.find(f"./{self.XS_NS}complexContent")
        if complex_content is not None:
            extension = complex_content.find(f"./{self.XS_NS}extension")
            if extension is not None:
                ext_seq = extension.find(f"./{self.XS_NS}sequence")
                if ext_seq is not None:
                    sequences.append(ext_seq)

        for sequence in sequences:
            for elem in sequence:
                if elem.tag == f"{self.XS_NS}element":
                    child_name = elem.get("name")
                    if child_name and len(child_name) == 2:
                        # Add to parent's allowed children
                        if parent_name in lookup.elements:
                            lookup.elements[parent_name].allowed_children.add(child_name)

                            min_occurs = int(elem.get("minOccurs", "1"))
                            if min_occurs >= 1:
                                lookup.elements[parent_name].required_children.add(child_name)

                        # Recursively parse nested elements
                        nested_complex = elem.find(f"./{self.XS_NS}complexType")
                        if nested_complex is not None:
                            # Create element structure if not exists
                            if child_name not in lookup.elements:
                                lookup.elements[child_name] = ElementStructure(
                                    name=child_name,
                                    type_name=child_name
                                )
                            self._parse_nested_complex(nested_complex, lookup, child_name)


# Cached lookup
_cached_structure_lookup: Optional[StructureLookup] = None


def get_structure_lookup(config: Optional[Config] = None) -> StructureLookup:
    """Get a cached structure lookup."""
    global _cached_structure_lookup
    if _cached_structure_lookup is None:
        parser = XSDStructureParser(config)
        _cached_structure_lookup = parser.parse()
    return _cached_structure_lookup


def clear_structure_lookup_cache() -> None:
    """Clear the cached structure lookup."""
    global _cached_structure_lookup
    _cached_structure_lookup = None
