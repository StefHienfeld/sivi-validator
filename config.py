"""Configuration for SIVI AFD XML Validator."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import os


@dataclass
class Config:
    """Configuration for the SIVI validator."""

    # Base directory for SIVI files
    sivi_dir: Path = field(default_factory=lambda: Path(r"C:\Users\Stef\Desktop\sivi"))

    # XSD file paths (relative to sivi_dir)
    formaten_xsd: str = "formaten.xsd"
    codelist_xsd: str = "codelist.xsd"
    attributen_xsd: str = "attributen.xsd"
    entiteiten_xsd: str = "entiteiten.xsd"
    dekkingcodes_xsd: str = "dekkingcodesgroup.xsd"
    contractbericht_xsd: str = "Contractberichtstructuur.xsd"

    # Branch hierarchy JSON files
    branch_hierarchy_json: str = "20250901_hierarchy_ADN_branchecode_45C__0.json"
    branch_codelist_json: str = "20250901_codelist_ADN_branchecode_45C__0.json"

    # LLM settings
    llm_model: str = "claude-sonnet-4-5-20250929"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.0

    # Validation settings
    premium_tolerance_warning: float = 0.01  # 1 cent for warning
    premium_tolerance_error: float = 0.01    # >1 cent for error

    # Engine enable/disable settings
    enable_xsd_validation: bool = True
    enable_hierarchy_validation: bool = True
    enable_final_certification: bool = True

    # Output settings
    default_output_format: str = "console"  # console, json, xlsx

    def get_xsd_path(self, xsd_name: str) -> Path:
        """Get full path to an XSD file."""
        return self.sivi_dir / xsd_name

    def get_json_path(self, json_name: str) -> Path:
        """Get full path to a JSON file."""
        return self.sivi_dir / json_name

    @property
    def formaten_path(self) -> Path:
        return self.get_xsd_path(self.formaten_xsd)

    @property
    def codelist_path(self) -> Path:
        return self.get_xsd_path(self.codelist_xsd)

    @property
    def attributen_path(self) -> Path:
        return self.get_xsd_path(self.attributen_xsd)

    @property
    def entiteiten_path(self) -> Path:
        return self.get_xsd_path(self.entiteiten_xsd)

    @property
    def dekkingcodes_path(self) -> Path:
        return self.get_xsd_path(self.dekkingcodes_xsd)

    @property
    def contractbericht_xsd_path(self) -> Path:
        return self.get_xsd_path(self.contractbericht_xsd)

    @property
    def branch_hierarchy_path(self) -> Path:
        return self.get_json_path(self.branch_hierarchy_json)

    @property
    def branch_codelist_path(self) -> Path:
        return self.get_json_path(self.branch_codelist_json)


# Global default configuration
_default_config: Optional[Config] = None


def get_config() -> Config:
    """Get the default configuration."""
    global _default_config
    if _default_config is None:
        _default_config = Config()
    return _default_config


def set_config(config: Config) -> None:
    """Set the default configuration."""
    global _default_config
    _default_config = config
