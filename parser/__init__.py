"""Parsers for SIVI AFD XML Validator."""

from .xsd_parser import XSDParser, SchemaLookup, FormatSpec
from .xml_parser import XMLParser
from .xsd_structure_parser import XSDStructureParser, StructureLookup, ElementStructure
from .version_manager import (
    SIVIVersion,
    SchemaSet,
    VersionDetector,
    VersionManager,
    NamespaceValidator,
    get_version_manager,
    detect_xml_version,
)

__all__ = [
    # XSD Parser
    "XSDParser",
    "SchemaLookup",
    "FormatSpec",
    # XML Parser
    "XMLParser",
    # Structure Parser
    "XSDStructureParser",
    "StructureLookup",
    "ElementStructure",
    # Version Manager
    "SIVIVersion",
    "SchemaSet",
    "VersionDetector",
    "VersionManager",
    "NamespaceValidator",
    "get_version_manager",
    "detect_xml_version",
]
