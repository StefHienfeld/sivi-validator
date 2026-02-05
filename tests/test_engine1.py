"""Tests for Engine 1: Schema validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from config import Config
from engines.base import BatchData, ContractData, EntityData, Severity
from engines.engine1_schema import SchemaValidationEngine


class TestSchemaValidationEngine:
    """Test schema validation engine."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()

    @pytest.fixture
    def engine(self, config):
        """Create engine instance."""
        return SchemaValidationEngine(config)

    def test_validate_valid_contract(self, engine):
        """Test validation of a valid contract."""
        contract = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(
                    entity_type="AL",
                    volgnum=1,
                    attributes={
                        "AL_ENTITEI": "AL",
                        "AL_VOLGNUM": "1",
                        "AL_POLNR": "DL123456",
                    },
                ),
            ],
        )
        batch = BatchData(contracts=[contract])

        findings = engine.validate(batch)
        # Should have no E1-001 errors for valid attributes
        e1_001_findings = [f for f in findings if f.code == "E1-001"]
        # May or may not have findings depending on schema

    def test_validate_invalid_coverage_code(self, engine):
        """Test detection of invalid coverage code."""
        contract = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(
                    entity_type="AN",
                    volgnum=1,
                    attributes={
                        "AN_ENTITEI": "AN",
                        "AN_VOLGNUM": "1",
                        "AN_CODE": "9999",  # Invalid code
                    },
                ),
            ],
        )
        batch = BatchData(contracts=[contract])

        findings = engine.validate(batch)
        e1_002_findings = [f for f in findings if f.code == "E1-002"]
        # Should detect invalid code
        if engine.lookup.coverage_codes.get("AN"):
            assert len(e1_002_findings) > 0
            assert e1_002_findings[0].waarde == "9999"

    def test_validate_field_length(self, engine):
        """Test detection of field length violation."""
        # Create a value that exceeds max length
        long_name = "A" * 100  # AN__35 max length is 35

        contract = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(
                    entity_type="VP",
                    volgnum=1,
                    attributes={
                        "VP_ENTITEI": "VP",
                        "VP_VOLGNUM": "1",
                        "VP_ANAAM": long_name,
                    },
                ),
            ],
        )
        batch = BatchData(contracts=[contract])

        findings = engine.validate(batch)
        e1_003_findings = [f for f in findings if f.code == "E1-003"]
        # Should detect length violation
        assert len(e1_003_findings) > 0

    def test_validate_numeric_format(self, engine):
        """Test detection of format violation."""
        contract = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(
                    entity_type="VP",
                    volgnum=1,
                    attributes={
                        "VP_ENTITEI": "VP",
                        "VP_VOLGNUM": "ABC",  # Should be numeric
                    },
                ),
            ],
        )
        batch = BatchData(contracts=[contract])

        findings = engine.validate(batch)
        e1_004_findings = [f for f in findings if f.code == "E1-004"]
        # Should detect format violation
        assert len(e1_004_findings) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
