"""
XSD processor for converting schema definitions to searchable text documents.
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

from lxml import etree

logger = logging.getLogger(__name__)


class XSDProcessor:
    """Processor for converting XSD schemas to searchable documents."""

    XS_NS = "{http://www.w3.org/2001/XMLSchema}"

    def __init__(self, sivi_dir: Path):
        """
        Initialize the XSD processor.

        Args:
            sivi_dir: Path to the SIVI directory containing XSD files.
        """
        self.sivi_dir = sivi_dir

    def process_all(self) -> list[dict]:
        """
        Process all relevant XSD files.

        Returns:
            List of document chunks.
        """
        all_docs = []

        # Process each XSD file
        xsd_files = [
            ("formaten.xsd", self._process_formaten),
            ("codelist.xsd", self._process_codelist),
            ("attributen.xsd", self._process_attributen),
            ("entiteiten.xsd", self._process_entiteiten),
            ("dekkingcodesgroup.xsd", self._process_dekkingcodes),
        ]

        for filename, processor in xsd_files:
            filepath = self.sivi_dir / filename
            if filepath.exists():
                logger.info(f"Processing XSD: {filename}")
                docs = processor(filepath)
                all_docs.extend(docs)
                logger.info(f"Created {len(docs)} documents from {filename}")
            else:
                logger.warning(f"XSD file not found: {filepath}")

        return all_docs

    def _process_formaten(self, filepath: Path) -> list[dict]:
        """Process formaten.xsd - format specifications."""
        docs = []
        tree = etree.parse(str(filepath))
        root = tree.getroot()

        for simple_type in root.findall(f"{self.XS_NS}simpleType"):
            name = simple_type.get("name")
            if not name:
                continue

            restriction = simple_type.find(f"{self.XS_NS}restriction")
            if restriction is None:
                continue

            base = restriction.get("base", "").split(":")[-1]

            # Build description
            constraints = []
            for child in restriction:
                tag = child.tag.replace(self.XS_NS, "")
                value = child.get("value")
                if value:
                    if tag == "minLength":
                        constraints.append(f"minimale lengte: {value}")
                    elif tag == "maxLength":
                        constraints.append(f"maximale lengte: {value}")
                    elif tag == "length":
                        constraints.append(f"exacte lengte: {value}")
                    elif tag == "pattern":
                        constraints.append(f"patroon: {value}")
                    elif tag == "totalDigits":
                        constraints.append(f"totaal cijfers: {value}")
                    elif tag == "fractionDigits":
                        constraints.append(f"decimalen: {value}")

            content = f"Format: {name}\nBasistype: {base}\n"
            if constraints:
                content += "Restricties: " + ", ".join(constraints)

            doc_id = f"xsd_format_{hashlib.md5(name.encode()).hexdigest()[:8]}"
            docs.append({
                "id": doc_id,
                "content": content,
                "metadata": {
                    "source_type": "xsd",
                    "source_file": "formaten.xsd",
                    "title": f"Format {name}",
                    "xsd_type": "format",
                    "format_name": name,
                },
            })

        return docs

    def _process_codelist(self, filepath: Path) -> list[dict]:
        """Process codelist.xsd - code enumerations."""
        docs = []
        tree = etree.parse(str(filepath))
        root = tree.getroot()

        for simple_type in root.findall(f"{self.XS_NS}simpleType"):
            name = simple_type.get("name")
            if not name:
                continue

            restriction = simple_type.find(f"{self.XS_NS}restriction")
            if restriction is None:
                continue

            values = []
            for enum in restriction.findall(f"{self.XS_NS}enumeration"):
                value = enum.get("value")
                if value:
                    values.append(value)

            if not values:
                continue

            # Create document with code list
            content = f"Codelijst: {name}\n"
            content += f"Aantal geldige codes: {len(values)}\n"
            content += "Geldige waarden: " + ", ".join(sorted(values)[:50])
            if len(values) > 50:
                content += f"... (en {len(values) - 50} meer)"

            doc_id = f"xsd_codelist_{hashlib.md5(name.encode()).hexdigest()[:8]}"
            docs.append({
                "id": doc_id,
                "content": content,
                "metadata": {
                    "source_type": "xsd",
                    "source_file": "codelist.xsd",
                    "title": f"Codelijst {name}",
                    "xsd_type": "codelist",
                    "codelist_name": name,
                    "code_count": len(values),
                },
            })

        return docs

    def _process_attributen(self, filepath: Path) -> list[dict]:
        """Process attributen.xsd - attribute definitions."""
        docs = []
        tree = etree.parse(str(filepath))
        root = tree.getroot()

        # Group attributes by their base/format reference
        attr_groups = {}

        for simple_type in root.findall(f"{self.XS_NS}simpleType"):
            name = simple_type.get("name")
            if not name:
                continue

            restriction = simple_type.find(f"{self.XS_NS}restriction")
            if restriction is None:
                continue

            base = restriction.get("base", "")

            if base not in attr_groups:
                attr_groups[base] = []
            attr_groups[base].append(name)

        # Create documents for attribute groups
        for base, attrs in attr_groups.items():
            # Determine if it's a format or codelist reference
            if base.startswith("cl:"):
                ref_type = "codelijst"
                ref_name = base[3:]
            elif base.startswith("fm:"):
                ref_type = "formaat"
                ref_name = base[3:]
            else:
                ref_type = "type"
                ref_name = base

            content = f"Attributen met {ref_type} '{ref_name}':\n"
            content += ", ".join(sorted(attrs)[:30])
            if len(attrs) > 30:
                content += f"... (en {len(attrs) - 30} meer)"
            content += f"\n\nTotaal: {len(attrs)} attributen gebruiken dit {ref_type}."

            doc_id = f"xsd_attrs_{hashlib.md5(base.encode()).hexdigest()[:8]}"
            docs.append({
                "id": doc_id,
                "content": content,
                "metadata": {
                    "source_type": "xsd",
                    "source_file": "attributen.xsd",
                    "title": f"Attributen ({ref_name})",
                    "xsd_type": "attributes",
                    "reference_type": ref_type,
                    "reference_name": ref_name,
                },
            })

        return docs

    def _process_entiteiten(self, filepath: Path) -> list[dict]:
        """Process entiteiten.xsd - entity definitions."""
        docs = []
        tree = etree.parse(str(filepath))
        root = tree.getroot()

        for complex_type in root.findall(f"{self.XS_NS}complexType"):
            name = complex_type.get("name")
            if not name or len(name) != 2:
                continue

            # Collect attributes
            attributes = []
            sequence = complex_type.find(f"{self.XS_NS}sequence")
            if sequence is not None:
                for child in sequence:
                    if child.tag == f"{self.XS_NS}element":
                        elem_name = child.get("name")
                        if elem_name:
                            attributes.append(elem_name)
                    elif child.tag == f"{self.XS_NS}group":
                        ref = child.get("ref", "")
                        if "_CODEGroup" in ref:
                            group_name = ref.split(":")[-1] if ":" in ref else ref
                            code_elem = group_name.replace("Group", "")
                            attributes.append(code_elem)

            if not attributes:
                continue

            # Create human-readable description
            entity_desc = self._get_entity_description(name)
            content = f"Entiteit: {name} ({entity_desc})\n\n"
            content += f"Geldige attributen voor entiteit {name}:\n"
            content += ", ".join(sorted(attributes))
            content += f"\n\nTotaal: {len(attributes)} attributen."

            doc_id = f"xsd_entity_{name}"
            docs.append({
                "id": doc_id,
                "content": content,
                "metadata": {
                    "source_type": "xsd",
                    "source_file": "entiteiten.xsd",
                    "title": f"Entiteit {name}",
                    "xsd_type": "entity",
                    "entity_code": name,
                    "attribute_count": len(attributes),
                },
            })

        return docs

    def _process_dekkingcodes(self, filepath: Path) -> list[dict]:
        """Process dekkingcodesgroup.xsd - coverage codes per entity."""
        docs = []
        tree = etree.parse(str(filepath))
        root = tree.getroot()

        for group in root.findall(f"{self.XS_NS}group"):
            name = group.get("name")
            if not name or not name.endswith("_CODEGroup"):
                continue

            entity_code = name.replace("_CODEGroup", "")

            # Collect coverage codes
            codes = []
            for element in group.iter(f"{self.XS_NS}element"):
                simple_type = element.find(f"{self.XS_NS}simpleType")
                if simple_type is not None:
                    restriction = simple_type.find(f"{self.XS_NS}restriction")
                    if restriction is not None:
                        for enum in restriction.findall(f"{self.XS_NS}enumeration"):
                            value = enum.get("value")
                            if value:
                                codes.append(value)

            if not codes:
                continue

            entity_desc = self._get_entity_description(entity_code)
            content = f"Dekkingscodes voor entiteit {entity_code} ({entity_desc}):\n\n"
            content += f"Geldige {entity_code}_CODE waarden:\n"
            content += ", ".join(sorted(codes))
            content += f"\n\nTotaal: {len(codes)} geldige codes voor {entity_code}."
            content += f"\n\nLET OP: Deze codes zijn ALLEEN geldig voor entiteit {entity_code}. "
            content += f"Gebruik deze codes niet voor andere entiteiten."

            doc_id = f"xsd_coverage_{entity_code}"
            docs.append({
                "id": doc_id,
                "content": content,
                "metadata": {
                    "source_type": "xsd",
                    "source_file": "dekkingcodesgroup.xsd",
                    "title": f"Dekkingscodes {entity_code}",
                    "xsd_type": "coverage_codes",
                    "entity_code": entity_code,
                    "code_count": len(codes),
                },
            })

        return docs

    def _get_entity_description(self, code: str) -> str:
        """Get human-readable description for entity codes."""
        descriptions = {
            "VP": "Verzekeringspolis",
            "PP": "Premiepenning / Premie",
            "CA": "Clausules en Aanvullende dekkingen",
            "AH": "Aanvullende dekkingen Hierarchisch",
            "PV": "Polisvorm / Voertuig gegevens",
            "DA": "Dekking Attributen",
            "BO": "Branche Object",
            "AN": "Adres Nummeringen",
            "DR": "Dekking Rechtsbijstand",
            "XD": "eXtra Data",
            "VZ": "Verzekerde",
            "VN": "Verzekeringnemer",
        }
        return descriptions.get(code, "Onbekende entiteit")
