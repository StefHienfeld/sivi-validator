"""SIVI Version Management Module.

Handles SIVI AFD version detection, multi-version schema support,
and version-specific validation rules.

SIVI versioning structure:
- Datacategorie: e.g., 41D, 45C
- Viewcode: e.g., 00901
- Versienummer: e.g., 103
- Release date: Monthly updates (first day of month)

Schema file naming convention:
- formaten_{date}.xsd
- codelist_{date}.xsd
- attributen_{date}.xsd
- entiteiten_{date}.xsd
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from lxml import etree


@dataclass
class SIVIVersion:
    """Represents a SIVI AFD version."""

    datacategorie: str = ""  # e.g., "45C"
    viewcode: str = ""  # e.g., "00901"
    versienummer: int = 0  # e.g., 103
    release_date: Optional[datetime] = None
    namespace_uri: str = ""

    def __str__(self) -> str:
        """String representation of version."""
        parts = []
        if self.datacategorie:
            parts.append(f"DC:{self.datacategorie}")
        if self.viewcode:
            parts.append(f"VC:{self.viewcode}")
        if self.versienummer:
            parts.append(f"V:{self.versienummer}")
        if self.release_date:
            parts.append(f"({self.release_date.strftime('%Y%m%d')})")
        return " ".join(parts) if parts else "Unknown"

    def is_compatible_with(self, other: "SIVIVersion") -> bool:
        """Check if this version is compatible with another."""
        # Same datacategorie is required for compatibility
        if self.datacategorie and other.datacategorie:
            if self.datacategorie != other.datacategorie:
                return False

        # Viewcode should match for full compatibility
        if self.viewcode and other.viewcode:
            if self.viewcode != other.viewcode:
                return False

        return True

    @property
    def is_valid(self) -> bool:
        """Check if version information is valid."""
        return bool(self.datacategorie or self.viewcode or self.versienummer)


@dataclass
class SchemaSet:
    """A set of related XSD schema files for a specific version."""

    version: SIVIVersion
    formaten_path: Optional[Path] = None
    codelist_path: Optional[Path] = None
    attributen_path: Optional[Path] = None
    entiteiten_path: Optional[Path] = None
    dekkingcodes_path: Optional[Path] = None
    contractbericht_path: Optional[Path] = None

    def is_complete(self) -> bool:
        """Check if all required schema files are present."""
        required = [
            self.formaten_path,
            self.codelist_path,
            self.attributen_path,
            self.entiteiten_path,
        ]
        return all(p is not None and p.exists() for p in required if p is not None)

    def get_missing_files(self) -> List[str]:
        """Get list of missing schema files."""
        missing = []
        checks = [
            ("formaten", self.formaten_path),
            ("codelist", self.codelist_path),
            ("attributen", self.attributen_path),
            ("entiteiten", self.entiteiten_path),
        ]
        for name, path in checks:
            if path is None or not path.exists():
                missing.append(name)
        return missing


class VersionDetector:
    """
    Detects SIVI AFD version from XML documents and schema files.

    Supports detection from:
    1. XML namespace declarations
    2. Root element attributes
    3. Schema file names
    4. Schema namespace definitions
    """

    # Namespace patterns for version extraction
    NAMESPACE_PATTERNS = [
        # http://schemas.sivi.org/AFD/Formaten/2026/2/1
        re.compile(r"http://schemas\.sivi\.org/AFD/\w+/(\d{4})/(\d+)/(\d+)"),
        # http://www.sivi.org/berichtschema/2026/2/1
        re.compile(r"http://www\.sivi\.org/berichtschema/(\d{4})/(\d+)/(\d+)"),
    ]

    # File name patterns for version/date extraction
    FILE_PATTERNS = [
        # 20260201_hierarchy_ADN_branchecode_45C__0.json
        re.compile(r"(\d{8})_\w+_ADN_\w+_(\w+)_"),
        # formaten_20260201.xsd
        re.compile(r"\w+_(\d{8})\.xsd"),
    ]

    def detect_from_xml(self, xml_path: Path) -> SIVIVersion:
        """
        Detect version from an XML file.

        Looks at namespace declarations and root element attributes.
        """
        version = SIVIVersion()

        try:
            # Parse XML and get root
            tree = etree.parse(str(xml_path))
            root = tree.getroot()

            # Check namespace declarations
            for prefix, uri in root.nsmap.items():
                if uri:
                    extracted = self._extract_version_from_namespace(uri)
                    if extracted.is_valid:
                        version = extracted
                        version.namespace_uri = uri
                        break

            # Check root element attributes for version info
            for attr in ["versie", "version", "datacategorie", "viewcode"]:
                value = root.get(attr)
                if value:
                    if attr in ("versie", "version"):
                        try:
                            version.versienummer = int(value)
                        except ValueError:
                            pass
                    elif attr == "datacategorie":
                        version.datacategorie = value
                    elif attr == "viewcode":
                        version.viewcode = value

            # Try to detect from child elements
            for elem in root.iter():
                tag_local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

                if tag_local == "AL_DCVRSNR" and elem.text:
                    version.datacategorie = elem.text
                elif tag_local == "AL_VIEWCODE" and elem.text:
                    version.viewcode = elem.text
                elif tag_local == "AL_VRSNR" and elem.text:
                    try:
                        version.versienummer = int(elem.text)
                    except ValueError:
                        pass

        except (etree.XMLSyntaxError, OSError):
            pass

        return version

    def detect_from_schema(self, schema_path: Path) -> SIVIVersion:
        """
        Detect version from an XSD schema file.

        Looks at namespace declarations and file name.
        """
        version = SIVIVersion()

        # Try file name first
        for pattern in self.FILE_PATTERNS:
            match = pattern.search(schema_path.name)
            if match:
                groups = match.groups()
                if len(groups) >= 1:
                    try:
                        date_str = groups[0]
                        if len(date_str) == 8:
                            version.release_date = datetime.strptime(date_str, "%Y%m%d")
                    except ValueError:
                        pass
                if len(groups) >= 2:
                    version.datacategorie = groups[1]

        # Parse XSD for namespace
        if schema_path.exists():
            try:
                tree = etree.parse(str(schema_path))
                root = tree.getroot()

                # Check targetNamespace
                target_ns = root.get("targetNamespace")
                if target_ns:
                    extracted = self._extract_version_from_namespace(target_ns)
                    if extracted.is_valid:
                        version.versienummer = extracted.versienummer
                        version.namespace_uri = target_ns
                        if extracted.release_date:
                            version.release_date = extracted.release_date

            except (etree.XMLSyntaxError, OSError):
                pass

        return version

    def _extract_version_from_namespace(self, namespace: str) -> SIVIVersion:
        """Extract version information from a namespace URI."""
        version = SIVIVersion()

        for pattern in self.NAMESPACE_PATTERNS:
            match = pattern.search(namespace)
            if match:
                groups = match.groups()
                if len(groups) >= 3:
                    try:
                        year = int(groups[0])
                        month = int(groups[1])
                        day = int(groups[2])
                        version.release_date = datetime(year, month, day)
                    except (ValueError, TypeError):
                        pass
                break

        return version


class VersionManager:
    """
    Manages multiple SIVI AFD schema versions.

    Supports:
    1. Automatic version detection
    2. Multi-version schema loading
    3. Version-specific validation configuration
    4. Schema archive management
    """

    def __init__(self, sivi_dir: Path):
        self.sivi_dir = sivi_dir
        self.detector = VersionDetector()
        self._schema_sets: Dict[str, SchemaSet] = {}
        self._current_version: Optional[SIVIVersion] = None

        # Scan for available versions
        self._scan_available_versions()

    def _scan_available_versions(self) -> None:
        """Scan the SIVI directory for available schema versions."""
        if not self.sivi_dir.exists():
            return

        # Look for schema files and group by version
        schema_files = {
            "formaten": list(self.sivi_dir.glob("formaten*.xsd")),
            "codelist": list(self.sivi_dir.glob("codelist*.xsd")),
            "attributen": list(self.sivi_dir.glob("attributen*.xsd")),
            "entiteiten": list(self.sivi_dir.glob("entiteiten*.xsd")),
            "dekkingcodes": list(self.sivi_dir.glob("dekkingcodes*.xsd")),
            "contractbericht": list(self.sivi_dir.glob("Contractbericht*.xsd")),
        }

        # Create default schema set from current files
        default_version = SIVIVersion(datacategorie="default")
        default_set = SchemaSet(version=default_version)

        # Map standard file names
        for schema_type, files in schema_files.items():
            if files:
                # Prefer files without date suffix
                standard_file = None
                for f in files:
                    if not re.search(r"_\d{8}\.", f.name):
                        standard_file = f
                        break
                if standard_file is None:
                    standard_file = files[0]

                setattr(default_set, f"{schema_type}_path", standard_file)

                # Detect version from file
                version = self.detector.detect_from_schema(standard_file)
                if version.is_valid:
                    default_version = version
                    default_set.version = version

        if default_set.is_complete():
            self._schema_sets["default"] = default_set
            self._current_version = default_version

        # Look for versioned subdirectories (archive)
        for subdir in self.sivi_dir.iterdir():
            if subdir.is_dir() and re.match(r"\d{8}", subdir.name):
                version_set = self._load_schema_set_from_dir(subdir)
                if version_set and version_set.is_complete():
                    key = str(version_set.version) or subdir.name
                    self._schema_sets[key] = version_set

    def _load_schema_set_from_dir(self, directory: Path) -> Optional[SchemaSet]:
        """Load a schema set from a directory."""
        version = SIVIVersion()

        # Try to parse date from directory name
        try:
            version.release_date = datetime.strptime(directory.name[:8], "%Y%m%d")
        except ValueError:
            pass

        schema_set = SchemaSet(version=version)

        # Map files
        mappings = [
            ("formaten_path", "formaten*.xsd"),
            ("codelist_path", "codelist*.xsd"),
            ("attributen_path", "attributen*.xsd"),
            ("entiteiten_path", "entiteiten*.xsd"),
            ("dekkingcodes_path", "dekkingcodes*.xsd"),
            ("contractbericht_path", "Contractbericht*.xsd"),
        ]

        for attr, pattern in mappings:
            files = list(directory.glob(pattern))
            if files:
                setattr(schema_set, attr, files[0])

        return schema_set if schema_set.is_complete() else None

    def get_version_for_xml(self, xml_path: Path) -> SIVIVersion:
        """Detect the appropriate version for an XML file."""
        return self.detector.detect_from_xml(xml_path)

    def get_schema_set(
        self,
        version: Optional[SIVIVersion] = None,
    ) -> Optional[SchemaSet]:
        """
        Get the schema set for a specific version.

        If no version specified, returns the default/current schema set.
        """
        if version is None or not version.is_valid:
            return self._schema_sets.get("default")

        # Look for exact match first
        version_key = str(version)
        if version_key in self._schema_sets:
            return self._schema_sets[version_key]

        # Look for compatible version
        for key, schema_set in self._schema_sets.items():
            if schema_set.version.is_compatible_with(version):
                return schema_set

        # Fall back to default
        return self._schema_sets.get("default")

    def get_available_versions(self) -> List[SIVIVersion]:
        """Get list of available versions."""
        return [s.version for s in self._schema_sets.values()]

    @property
    def current_version(self) -> Optional[SIVIVersion]:
        """Get the current/default version."""
        return self._current_version

    def get_version_info(self) -> Dict:
        """Get information about available versions."""
        return {
            "current_version": str(self._current_version) if self._current_version else None,
            "available_versions": [str(v) for v in self.get_available_versions()],
            "schema_sets": {
                key: {
                    "version": str(ss.version),
                    "complete": ss.is_complete(),
                    "missing": ss.get_missing_files(),
                }
                for key, ss in self._schema_sets.items()
            },
        }


class NamespaceValidator:
    """
    Validates XML namespace compliance with SIVI standards.

    SIVI namespace structure:
    - xmlns:afd="http://www.sivi.org/berichtschema"
    - xmlns:fm="http://schemas.sivi.org/AFD/Formaten/{year}/{month}/{day}"
    - xmlns:cl="http://schemas.sivi.org/AFD/Codelijsten/{year}/{month}/{day}"
    """

    STANDARD_NAMESPACES = {
        "afd": "http://www.sivi.org/berichtschema",
        "afdFormats": "http://schemas.sivi.org/afdFormats",
        "afdCodelists": "http://schemas.sivi.org/afdCodelists",
    }

    NAMESPACE_PATTERNS = {
        "formaten": re.compile(r"http://schemas\.sivi\.org/AFD/Formaten/\d{4}/\d+/\d+"),
        "codelijsten": re.compile(r"http://schemas\.sivi\.org/AFD/Codelijsten/\d{4}/\d+/\d+"),
        "bericht": re.compile(r"http://www\.sivi\.org/berichtschema"),
    }

    def validate_namespaces(self, xml_path: Path) -> List[Dict]:
        """
        Validate namespace declarations in an XML file.

        Returns list of issues found.
        """
        issues = []

        try:
            tree = etree.parse(str(xml_path))
            root = tree.getroot()

            # Check declared namespaces
            declared_namespaces = root.nsmap

            # Check for required base namespace
            has_base_ns = any(
                self.NAMESPACE_PATTERNS["bericht"].match(uri)
                for uri in declared_namespaces.values()
                if uri
            )

            if not has_base_ns:
                issues.append({
                    "type": "missing_namespace",
                    "severity": "warning",
                    "message": "SIVI berichtschema namespace niet gevonden",
                    "expected": "http://www.sivi.org/berichtschema",
                })

            # Check namespace consistency
            for prefix, uri in declared_namespaces.items():
                if prefix in self.STANDARD_NAMESPACES:
                    expected = self.STANDARD_NAMESPACES[prefix]
                    if uri and not uri.startswith(expected.split("/")[0:3]):
                        issues.append({
                            "type": "namespace_mismatch",
                            "severity": "info",
                            "message": f"Namespace prefix '{prefix}' wijkt af van standaard",
                            "found": uri,
                            "expected": expected,
                        })

            # Check for unknown namespaces
            known_patterns = list(self.NAMESPACE_PATTERNS.values())
            for prefix, uri in declared_namespaces.items():
                if uri and prefix not in (None, "xs", "xsi"):
                    is_known = any(p.match(uri) for p in known_patterns)
                    if not is_known and not uri.startswith("http://www.w3.org"):
                        issues.append({
                            "type": "unknown_namespace",
                            "severity": "info",
                            "message": f"Onbekende namespace: {prefix}={uri}",
                            "prefix": prefix,
                            "uri": uri,
                        })

        except (etree.XMLSyntaxError, OSError) as e:
            issues.append({
                "type": "parse_error",
                "severity": "error",
                "message": f"Kan XML niet parsen: {e}",
            })

        return issues

    def get_namespace_info(self, xml_path: Path) -> Dict:
        """Get namespace information from an XML file."""
        info = {
            "namespaces": {},
            "version_info": {},
            "valid": True,
            "issues": [],
        }

        try:
            tree = etree.parse(str(xml_path))
            root = tree.getroot()

            info["namespaces"] = dict(root.nsmap)

            # Extract version from namespaces
            for prefix, uri in root.nsmap.items():
                if uri:
                    for ns_type, pattern in self.NAMESPACE_PATTERNS.items():
                        if pattern.match(uri):
                            info["version_info"][ns_type] = uri

            # Validate
            issues = self.validate_namespaces(xml_path)
            info["issues"] = issues
            info["valid"] = not any(i["severity"] == "error" for i in issues)

        except (etree.XMLSyntaxError, OSError):
            info["valid"] = False

        return info


# Convenience functions
_version_manager: Optional[VersionManager] = None


def get_version_manager(sivi_dir: Optional[Path] = None) -> VersionManager:
    """Get a cached version manager instance."""
    global _version_manager
    if _version_manager is None:
        from config import get_config
        config = get_config()
        _version_manager = VersionManager(sivi_dir or config.sivi_dir)
    return _version_manager


def detect_xml_version(xml_path: Path) -> SIVIVersion:
    """Detect the SIVI version of an XML file."""
    detector = VersionDetector()
    return detector.detect_from_xml(xml_path)
