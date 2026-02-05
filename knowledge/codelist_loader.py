"""Loader for SIVI branch hierarchy and codelist JSON files."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from config import Config, get_config


@dataclass
class BranchCode:
    """A single branch code with metadata."""

    value: str
    description: str
    short_description: str = ""
    node_description: str = ""
    path: List[str] = field(default_factory=list)
    children: List["BranchCode"] = field(default_factory=list)


@dataclass
class BranchHierarchy:
    """Branch code hierarchy."""

    table_name: str
    table_description: str
    root_branches: List[BranchCode] = field(default_factory=list)
    _lookup: Dict[str, BranchCode] = field(default_factory=dict, repr=False)

    def get_branch(self, code: str) -> Optional[BranchCode]:
        """Get branch by code."""
        return self._lookup.get(code)

    def get_parent_code(self, code: str) -> Optional[str]:
        """Get parent branch code."""
        branch = self._lookup.get(code)
        if branch and branch.path:
            # Path contains ancestors, last element is direct parent
            if len(branch.path) >= 2:
                return branch.path[-1]
        return None

    def get_description(self, code: str) -> str:
        """Get branch description."""
        branch = self._lookup.get(code)
        return branch.description if branch else ""

    def is_sub_branch(self, child_code: str, parent_code: str) -> bool:
        """Check if child_code is a sub-branch of parent_code."""
        branch = self._lookup.get(child_code)
        if not branch:
            return False
        return parent_code in branch.path

    def get_all_codes(self) -> Set[str]:
        """Get all branch codes."""
        return set(self._lookup.keys())


def _parse_branch_code(data: dict) -> BranchCode:
    """Parse a branch code from JSON data."""
    branch = BranchCode(
        value=data.get("value", ""),
        description=data.get("description", ""),
        short_description=data.get("shortDescription", ""),
        node_description=data.get("nodeDescription", ""),
        path=data.get("path", []),
    )

    # Parse children recursively
    for child_data in data.get("code", []):
        child = _parse_branch_code(child_data)
        branch.children.append(child)

    return branch


def _build_lookup(branch: BranchCode, lookup: Dict[str, BranchCode]) -> None:
    """Build lookup dictionary recursively."""
    lookup[branch.value] = branch
    for child in branch.children:
        _build_lookup(child, lookup)


def load_branch_hierarchy(config: Optional[Config] = None) -> BranchHierarchy:
    """Load branch hierarchy from JSON file."""
    config = config or get_config()
    path = config.branch_hierarchy_path

    if not path.exists():
        return BranchHierarchy(table_name="", table_description="")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    common = data.get("commonFunctional", {})
    hierarchy = BranchHierarchy(
        table_name=common.get("tableName", ""),
        table_description=common.get("tableDescription", ""),
    )

    # Parse branch codes
    afs_table = data.get("afsTable", {})
    for code_data in afs_table.get("codeValues", []):
        branch = _parse_branch_code(code_data)
        hierarchy.root_branches.append(branch)
        _build_lookup(branch, hierarchy._lookup)

    return hierarchy


# Coverage code mappings per branch category
BRANCH_COVERAGE_MAPPINGS = {
    # Motorrijtuigen (20)
    "20": {"WA", "CA", "AN", "AH"},  # Motor vehicles
    "21": {"WA", "CA", "AN"},  # Personenauto's
    "22": {"WA", "CA", "AN"},  # Motoren
    "23": {"WA", "CA", "AN"},  # Bedrijfsauto's
    "24": {"WA", "CA", "AN"},  # Bromfietsen
    "25": {"WA", "CA", "AN"},  # Caravans

    # Brand (30)
    "30": {"DA", "BR"},  # Brand
    "31": {"DA"},  # Woningen
    "32": {"DA"},  # Inboedels

    # Transport (40)
    "40": {"DA"},  # Transport

    # Aansprakelijkheid (50)
    "50": {"AN", "DR"},  # Aansprakelijkheid
    "51": {"AN"},  # AVB
    "52": {"AN"},  # AVP

    # Rechtsbijstand (60)
    "60": {"DR"},  # Rechtsbijstand

    # Leven (70)
    "70": {"DA"},  # Leven
    "71": {"DA"},  # Levensverzekering
    "72": {"DA"},  # Uitvaartverzekering

    # Ziekte/Ongevallen (10)
    "10": {"AO", "CY", "DA"},  # Ongevallen en ziekte
    "11": {"AO"},  # Ongevallen
    "12": {"DA"},  # Ziektekosten
    "13": {"AO"},  # Arbeidsongeschiktheid

    # Pensioen (80)
    "80": {"DA"},  # Pensioen
}


def get_expected_coverage_entities(branch_code: str) -> Set[str]:
    """Get expected coverage entity types for a branch."""
    # Check exact match first
    if branch_code in BRANCH_COVERAGE_MAPPINGS:
        return BRANCH_COVERAGE_MAPPINGS[branch_code]

    # Check parent branch (first 2 digits)
    if len(branch_code) >= 2:
        parent = branch_code[:2]
        if parent in BRANCH_COVERAGE_MAPPINGS:
            return BRANCH_COVERAGE_MAPPINGS[parent]

    # Default - any coverage is OK
    return set()
