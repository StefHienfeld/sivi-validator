"""Tests for XSD parser."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from config import Config
from parser.xsd_parser import XSDParser, SchemaLookup


class TestXSDParser:
    """Test XSD parsing functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()

    @pytest.fixture
    def parser(self, config):
        """Create parser instance."""
        return XSDParser(config)

    def test_parse_formaten(self, parser):
        """Test parsing formaten.xsd."""
        lookup = SchemaLookup()
        parser._parse_formaten(lookup)

        assert "AN__35" in lookup.formats
        assert lookup.formats["AN__35"].max_length == 35
        assert "N__3" in lookup.formats
        assert lookup.formats["N__3"].max_length == 3
        assert "codeD1" in lookup.formats

    def test_parse_codelist(self, parser):
        """Test parsing codelist.xsd."""
        lookup = SchemaLookup()
        parser._parse_codelist(lookup)

        assert "ADNENT" in lookup.codelists or len(lookup.codelists) > 0
        # Check some codelist has values
        for name, values in lookup.codelists.items():
            assert isinstance(values, set)
            break

    def test_parse_attributen(self, parser):
        """Test parsing attributen.xsd."""
        lookup = SchemaLookup()
        parser._parse_attributen(lookup)

        assert "_ENTITEI" in lookup.attributes
        assert "_VOLGNUM" in lookup.attributes

    def test_parse_entiteiten(self, parser):
        """Test parsing entiteiten.xsd."""
        lookup = SchemaLookup()
        parser._parse_entiteiten(lookup)

        # Check some entities exist
        assert len(lookup.entities) > 0
        # Check AL entity has attributes
        if "AL" in lookup.entities:
            assert "AL_POLNR" in lookup.entities["AL"] or len(lookup.entities["AL"]) > 0

    def test_parse_dekkingcodes(self, parser):
        """Test parsing dekkingcodesgroup.xsd."""
        lookup = SchemaLookup()
        parser._parse_dekkingcodes(lookup)

        # Check AN coverage codes
        if "AN" in lookup.coverage_codes:
            assert "3004" in lookup.coverage_codes["AN"]

    def test_parse_all(self, parser):
        """Test parsing all XSD files."""
        lookup = parser.parse_all()

        assert len(lookup.formats) > 0
        assert len(lookup.codelists) > 0
        assert len(lookup.attributes) > 0
        assert len(lookup.entities) > 0

    def test_is_valid_coverage_code(self, parser):
        """Test coverage code validation."""
        lookup = parser.parse_all()

        # Valid code for AN
        if "AN" in lookup.coverage_codes:
            valid_code = next(iter(lookup.coverage_codes["AN"]))
            assert lookup.is_valid_coverage_code("AN", valid_code)
            assert not lookup.is_valid_coverage_code("AN", "99999")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
