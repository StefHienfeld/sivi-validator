"""Tests for Engine 2: Business rules validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from config import Config
from engines.base import BatchData, ContractData, EntityData, Severity
from engines.engine2_rules import BusinessRulesEngine


class TestBusinessRulesEngine:
    """Test business rules validation engine."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()

    @pytest.fixture
    def engine(self, config):
        """Create engine instance."""
        return BusinessRulesEngine(config)

    def test_volgnum_sequential(self, engine):
        """Test VOLGNUM sequence validation - valid case."""
        contract = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(entity_type="AN", volgnum=1, attributes={"AN_VOLGNUM": "1"}),
                EntityData(entity_type="AN", volgnum=2, attributes={"AN_VOLGNUM": "2"}),
                EntityData(entity_type="AN", volgnum=3, attributes={"AN_VOLGNUM": "3"}),
            ],
        )
        batch = BatchData(contracts=[contract])

        findings = engine.validate(batch)
        e2_001_findings = [f for f in findings if f.code == "E2-001"]
        assert len(e2_001_findings) == 0

    def test_volgnum_not_sequential(self, engine):
        """Test VOLGNUM sequence validation - missing number."""
        contract = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(entity_type="AN", volgnum=1, attributes={"AN_VOLGNUM": "1"}),
                EntityData(entity_type="AN", volgnum=3, attributes={"AN_VOLGNUM": "3"}),
                # Missing volgnum 2
            ],
        )
        batch = BatchData(contracts=[contract])

        findings = engine.validate(batch)
        e2_001_findings = [f for f in findings if f.code == "E2-001"]
        assert len(e2_001_findings) > 0

    def test_volgnum_duplicate(self, engine):
        """Test VOLGNUM sequence validation - duplicate."""
        contract = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(entity_type="AN", volgnum=1, attributes={"AN_VOLGNUM": "1"}),
                EntityData(entity_type="AN", volgnum=1, attributes={"AN_VOLGNUM": "1"}),
            ],
        )
        batch = BatchData(contracts=[contract])

        findings = engine.validate(batch)
        e2_001_findings = [f for f in findings if f.code == "E2-001"]
        assert len(e2_001_findings) > 0

    def test_premium_sum_correct(self, engine):
        """Test premium sum validation - correct."""
        contract = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(
                    entity_type="PP",
                    volgnum=1,
                    attributes={"PP_VOLGNUM": "1", "PP_BTP": "100.00"},
                ),
                EntityData(
                    entity_type="AN",
                    volgnum=1,
                    attributes={"AN_VOLGNUM": "1", "AN_BTP": "60.00"},
                ),
                EntityData(
                    entity_type="AN",
                    volgnum=2,
                    attributes={"AN_VOLGNUM": "2", "AN_BTP": "40.00"},
                ),
            ],
        )
        batch = BatchData(contracts=[contract])

        findings = engine.validate(batch)
        e2_002_findings = [f for f in findings if f.code == "E2-002"]
        assert len(e2_002_findings) == 0

    def test_premium_sum_mismatch(self, engine):
        """Test premium sum validation - mismatch."""
        contract = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(
                    entity_type="PP",
                    volgnum=1,
                    attributes={"PP_VOLGNUM": "1", "PP_BTP": "100.00"},
                ),
                EntityData(
                    entity_type="AN",
                    volgnum=1,
                    attributes={"AN_VOLGNUM": "1", "AN_BTP": "50.00"},
                ),
                # Sum is 50, but PP_BTP is 100
            ],
        )
        batch = BatchData(contracts=[contract])

        findings = engine.validate(batch)
        e2_002_findings = [f for f in findings if f.code == "E2-002"]
        assert len(e2_002_findings) > 0

    def test_multiple_prolmonths(self, engine):
        """Test multiple prolongation months detection."""
        contract1 = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(
                    entity_type="PP",
                    volgnum=1,
                    attributes={"PP_VOLGNUM": "1", "PP_PROLMND": "01"},
                ),
            ],
        )
        contract2 = ContractData(
            contract_nummer="DL789012",
            branche="037",
            entities=[
                EntityData(
                    entity_type="PP",
                    volgnum=1,
                    attributes={"PP_VOLGNUM": "1", "PP_PROLMND": "02"},
                ),
            ],
        )
        batch = BatchData(contracts=[contract1, contract2])

        findings = engine.validate(batch)
        e2_003_findings = [f for f in findings if f.code == "E2-003"]
        assert len(e2_003_findings) > 0

    def test_xd_entity_forbidden(self, engine):
        """Test XD entity detection."""
        contract = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(
                    entity_type="XD",
                    volgnum=1,
                    attributes={"XD_ENTITEI": "XD", "XD_VOLGNUM": "1"},
                ),
            ],
        )
        batch = BatchData(contracts=[contract])

        findings = engine.validate(batch)
        e2_004_findings = [f for f in findings if f.code == "E2-004"]
        assert len(e2_004_findings) > 0
        assert e2_004_findings[0].severity == Severity.FOUT

    def test_bo_brprm_match(self, engine):
        """Test BO_BRPRM vs PP_BTP validation - match."""
        contract = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(
                    entity_type="PP",
                    volgnum=1,
                    attributes={"PP_VOLGNUM": "1", "PP_BTP": "100.00"},
                ),
                EntityData(
                    entity_type="BO",
                    volgnum=1,
                    attributes={"BO_VOLGNUM": "1", "BO_BRPRM": "100.00"},
                ),
            ],
        )
        batch = BatchData(contracts=[contract])

        findings = engine.validate(batch)
        e2_005_findings = [f for f in findings if f.code == "E2-005"]
        assert len(e2_005_findings) == 0

    def test_bo_brprm_mismatch(self, engine):
        """Test BO_BRPRM vs PP_BTP validation - mismatch."""
        contract = ContractData(
            contract_nummer="DL123456",
            branche="037",
            entities=[
                EntityData(
                    entity_type="PP",
                    volgnum=1,
                    attributes={"PP_VOLGNUM": "1", "PP_BTP": "100.00"},
                ),
                EntityData(
                    entity_type="BO",
                    volgnum=1,
                    attributes={"BO_VOLGNUM": "1", "BO_BRPRM": "99.00"},
                ),
            ],
        )
        batch = BatchData(contracts=[contract])

        findings = engine.validate(batch)
        e2_005_findings = [f for f in findings if f.code == "E2-005"]
        assert len(e2_005_findings) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
