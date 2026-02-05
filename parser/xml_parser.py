"""XML parser for ADN batch files."""

from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Union
from lxml import etree

from engines.base import BatchData, ContractData, EntityData


class XMLParser:
    """Parser for ADN batch XML files.

    Supports both flat and hierarchical parsing modes.
    Hierarchical parsing preserves parent-child relationships between entities.
    """

    def __init__(self, hierarchical: bool = True):
        """Initialize parser.

        Args:
            hierarchical: If True, parse with hierarchy support (default).
                         If False, use flat parsing for backward compatibility.
        """
        self.hierarchical = hierarchical

    def parse_file(self, file_path: Union[str, Path]) -> BatchData:
        """Parse an ADN batch XML file."""
        path = Path(file_path)
        # Parse with line numbers preserved
        parser = etree.XMLParser(remove_blank_text=False)
        tree = etree.parse(str(path), parser)
        root = tree.getroot()

        batch = BatchData(source_file=str(path))
        self._parse_batch(root, batch)
        return batch

    def parse_string(self, xml_string: str) -> BatchData:
        """Parse an ADN batch XML string."""
        root = etree.fromstring(xml_string.encode("utf-8"))
        batch = BatchData()
        self._parse_batch(root, batch)
        return batch

    def _parse_batch(self, root: etree._Element, batch: BatchData) -> None:
        """Parse the batch element and extract contracts."""
        # Handle namespaced and non-namespaced XML
        # Remove namespace for easier processing
        for elem in root.iter():
            # Skip comments and other non-element nodes
            if not isinstance(elem.tag, str):
                continue
            if elem.tag.startswith("{"):
                elem.tag = elem.tag.split("}", 1)[1]

        # Find all Contract elements
        contracts = root.findall(".//Contract")
        for contract_elem in contracts:
            contract = self._parse_contract(contract_elem)
            if contract:
                batch.contracts.append(contract)

        # Also check for direct entity elements (flat ADN format)
        if not batch.contracts:
            # Try parsing as flat format
            batch.contracts = self._parse_flat_format(root)

    def _parse_contract(self, contract_elem: etree._Element) -> Optional[ContractData]:
        """Parse a single Contract element."""
        contract = ContractData(contract_nummer="", branche="")

        # Store raw XML for LLM analysis
        contract.raw_xml = etree.tostring(contract_elem, encoding="unicode")

        # Parse all child elements as entities
        for child in contract_elem:
            if self.hierarchical:
                entity = self._parse_entity_recursive(child, parent=None, path="Contract")
            else:
                entity = self._parse_entity(child)

            if entity:
                contract.entities.append(entity)

                # Extract contract number from AL entity
                if entity.entity_type == "AL":
                    contract.contract_nummer = entity.get_attr("POLNR") or entity.get_attr("CPOLNR") or ""

                # Extract branche from PP entity (check recursively)
                self._extract_branche_from_entity(entity, contract)

        return contract if contract.contract_nummer else None

    def _extract_branche_from_entity(self, entity: EntityData, contract: ContractData) -> None:
        """Extract branche from PP entity, checking recursively."""
        if entity.entity_type == "PP":
            branche = entity.get_attr("BRANCHE") or entity.get_attr("BRA") or ""
            if branche and not contract.branche:
                contract.branche = branche
        for child in entity.children:
            self._extract_branche_from_entity(child, contract)

    def _parse_entity_recursive(
        self,
        elem: etree._Element,
        parent: Optional[EntityData] = None,
        path: str = ""
    ) -> Optional[EntityData]:
        """Parse entity with hierarchy preservation."""
        # Skip comments and other non-element nodes
        if not isinstance(elem.tag, str):
            return None

        tag = self._get_clean_tag(elem)
        if not tag:
            return None

        # Entity tags are typically 2 characters
        if len(tag) != 2:
            # Could be a wrapper element, check children
            entities = []
            for child in elem:
                entity = self._parse_entity_recursive(child, parent, path)
                if entity:
                    entities.append(entity)
            if len(entities) == 1:
                return entities[0]
            return None

        # Build path
        current_path = f"{path}/{tag}" if path else tag

        # Get line number if available
        line_number = getattr(elem, 'sourceline', None)

        entity = EntityData(
            entity_type=tag,
            xml_path=current_path,
            line_number=line_number,
            parent=parent
        )

        # Parse child elements
        for child in elem:
            # Skip comments and other non-element nodes
            if not isinstance(child.tag, str):
                continue

            child_tag = self._get_clean_tag(child)
            if not child_tag:
                continue

            # Check if this is an attribute (starts with entity prefix)
            if child_tag.startswith(f"{tag}_"):
                value = child.text or ""
                entity.attributes[child_tag] = value

                # Extract VOLGNUM
                if child_tag.endswith("_VOLGNUM"):
                    try:
                        entity.volgnum = int(value)
                    except (ValueError, TypeError):
                        pass
            elif len(child_tag) == 2:
                # This is a nested entity
                child_entity = self._parse_entity_recursive(child, entity, current_path)
                if child_entity:
                    entity.children.append(child_entity)

        return entity if entity.attributes or entity.children else None

    def _get_clean_tag(self, elem: etree._Element) -> Optional[str]:
        """Get tag name without namespace."""
        if not isinstance(elem.tag, str):
            return None
        tag = elem.tag
        if tag.startswith("{"):
            tag = tag.split("}", 1)[1]
        return tag

    def _parse_entity(self, elem: etree._Element) -> Optional[EntityData]:
        """Parse a single entity element (flat mode, backward compatible)."""
        # Skip comments and other non-element nodes
        if not isinstance(elem.tag, str):
            return None

        tag = self._get_clean_tag(elem)
        if not tag:
            return None

        # Entity tags are typically 2 characters
        if len(tag) != 2:
            # Could be a wrapper element, check children
            entities = []
            for child in elem:
                entity = self._parse_entity(child)
                if entity:
                    entities.append(entity)
            if len(entities) == 1:
                return entities[0]
            return None

        # Get line number if available
        line_number = getattr(elem, 'sourceline', None)

        entity = EntityData(
            entity_type=tag,
            xml_path=tag,
            line_number=line_number
        )

        # Parse child elements as attributes
        for child in elem:
            # Skip comments and other non-element nodes
            if not isinstance(child.tag, str):
                continue

            child_tag = self._get_clean_tag(child)
            if not child_tag:
                continue

            # Entity attributes start with entity code
            if child_tag.startswith(f"{tag}_"):
                value = child.text or ""
                entity.attributes[child_tag] = value

                # Extract VOLGNUM
                if child_tag.endswith("_VOLGNUM"):
                    try:
                        entity.volgnum = int(value)
                    except (ValueError, TypeError):
                        pass

        return entity if entity.attributes else None

    def _parse_flat_format(self, root: etree._Element) -> List[ContractData]:
        """Parse flat ADN format where entities are direct children."""
        contracts: Dict[str, ContractData] = {}
        current_contract_nr = ""
        current_branche = ""

        # In flat format, AL entity defines a new contract
        for elem in root.iter():
            # Skip comments and other non-element nodes
            if not isinstance(elem.tag, str):
                continue
            tag = elem.tag
            if tag.startswith("{"):
                tag = tag.split("}", 1)[1]

            if len(tag) != 2:
                continue

            entity = EntityData(entity_type=tag)

            # Parse attributes
            for child in elem:
                # Skip comments and other non-element nodes
                if not isinstance(child.tag, str):
                    continue
                child_tag = child.tag
                if child_tag.startswith("{"):
                    child_tag = child_tag.split("}", 1)[1]

                if child_tag.startswith(f"{tag}_"):
                    value = child.text or ""
                    entity.attributes[child_tag] = value

                    if child_tag.endswith("_VOLGNUM"):
                        try:
                            entity.volgnum = int(value)
                        except (ValueError, TypeError):
                            pass

            if not entity.attributes:
                continue

            # AL entity starts a new contract context
            if tag == "AL":
                current_contract_nr = entity.get_attr("POLNR") or entity.get_attr("CPOLNR") or f"contract_{len(contracts) + 1}"

                if current_contract_nr and current_contract_nr not in contracts:
                    contracts[current_contract_nr] = ContractData(
                        contract_nummer=current_contract_nr,
                        branche="",
                    )

            # PP entity contains branche
            if tag == "PP" and current_contract_nr:
                branche = entity.get_attr("BRANCHE") or entity.get_attr("BRA") or ""
                if branche and current_contract_nr in contracts:
                    contracts[current_contract_nr].branche = branche

            # Add entity to current contract
            if current_contract_nr and current_contract_nr in contracts:
                contracts[current_contract_nr].entities.append(entity)

        return list(contracts.values())


def parse_adn_batch(file_path: Union[str, Path]) -> BatchData:
    """Convenience function to parse an ADN batch file."""
    parser = XMLParser()
    return parser.parse_file(file_path)
