"""Engine 3: LLM semantic analysis."""

import json
import os
from typing import Any, Dict, List, Optional

from config import Config, get_config
from engines.base import (
    BatchData,
    ContractData,
    Engine,
    EntityData,
    Finding,
    Severity,
    ValidationEngine,
)
from knowledge.prompts import SYSTEM_PROMPT, get_analysis_prompt


class LLMSemanticEngine(ValidationEngine):
    """
    Engine 3: LLM semantic analysis.

    Uses Claude to analyze contracts for semantic issues:
    - E3-001: Branche-dekking mismatch
    - E3-002: Gezinssamenstelling bij rechtspersoon
    - E3-003: Nulwaarde in verplicht veld
    - E3-004: Data-kwaliteit problemen
    """

    # Maximum contracts per LLM call to fit context window
    MAX_CONTRACTS_PER_CALL = 20

    def __init__(self, config: Optional[Config] = None, api_key: Optional[str] = None):
        self.config = config or get_config()
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    @property
    def engine_type(self) -> Engine:
        return Engine.LLM

    @property
    def client(self):
        """Get or create Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. Run: pip install anthropic"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to create Anthropic client: {e}")
        return self._client

    def validate(self, batch: BatchData) -> List[Finding]:
        """Validate a batch using LLM analysis."""
        if not self.api_key:
            return []  # Skip LLM validation if no API key

        findings = []

        # Process contracts in chunks
        for i in range(0, len(batch.contracts), self.MAX_CONTRACTS_PER_CALL):
            chunk = batch.contracts[i : i + self.MAX_CONTRACTS_PER_CALL]
            chunk_findings = self._analyze_contracts(chunk)
            findings.extend(chunk_findings)

        return findings

    def _analyze_contracts(self, contracts: List[ContractData]) -> List[Finding]:
        """Analyze a chunk of contracts with LLM."""
        # Build XML representation for analysis
        contracts_xml = self._build_contracts_xml(contracts)

        # Get analysis prompt
        prompt = get_analysis_prompt(contracts_xml)

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.config.llm_model,
                max_tokens=self.config.llm_max_tokens,
                temperature=self.config.llm_temperature,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            response_text = response.content[0].text
            return self._parse_llm_response(response_text)

        except Exception as e:
            # Return error finding if LLM call fails
            return [
                Finding(
                    severity=Severity.INFO,
                    engine=Engine.LLM,
                    code="E3-ERR",
                    regeltype="llm_error",
                    contract="BATCH",
                    branche="",
                    entiteit="",
                    label="",
                    waarde="",
                    omschrijving=f"LLM analyse mislukt: {str(e)}",
                    verwacht="Succesvolle LLM analyse",
                    bron="engine3_llm",
                )
            ]

    def _build_contracts_xml(self, contracts: List[ContractData]) -> str:
        """Build XML representation of contracts for LLM."""
        xml_parts = []

        for contract in contracts:
            if contract.raw_xml:
                xml_parts.append(contract.raw_xml)
            else:
                # Build simplified representation
                xml_parts.append(self._build_contract_summary(contract))

        return "\n\n".join(xml_parts)

    def _build_contract_summary(self, contract: ContractData) -> str:
        """Build a text summary of a contract for LLM analysis."""
        lines = [
            f"<Contract nummer='{contract.contract_nummer}' branche='{contract.branche}'>"
        ]

        for entity in contract.entities:
            entity_lines = [f"  <{entity.entity_type}>"]
            for attr, value in entity.attributes.items():
                if value:  # Only include non-empty values
                    entity_lines.append(f"    <{attr}>{value}</{attr}>")
            entity_lines.append(f"  </{entity.entity_type}>")
            lines.extend(entity_lines)

        lines.append("</Contract>")
        return "\n".join(lines)

    def _parse_llm_response(self, response_text: str) -> List[Finding]:
        """Parse LLM response into findings."""
        findings = []

        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = response_text
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(json_text.strip())

            for item in data.get("findings", []):
                finding = self._create_finding_from_dict(item)
                if finding:
                    findings.append(finding)

        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract information manually
            pass
        except Exception:
            pass

        return findings

    def _create_finding_from_dict(self, data: Dict[str, Any]) -> Optional[Finding]:
        """Create a Finding from a dictionary."""
        try:
            code = data.get("code", "E3-000")
            severity = self._get_severity_for_code(code)

            return Finding(
                severity=severity,
                engine=Engine.LLM,
                code=code,
                regeltype=self._get_regeltype_for_code(code),
                contract=data.get("contract", ""),
                branche=data.get("branche", ""),
                entiteit=data.get("entiteit", ""),
                label=data.get("label", ""),
                waarde=data.get("waarde", ""),
                omschrijving=data.get("omschrijving", ""),
                verwacht=data.get("verwacht", ""),
                bron="LLM semantic analysis",
            )
        except Exception:
            return None

    def _get_severity_for_code(self, code: str) -> Severity:
        """Get severity for a finding code."""
        severity_map = {
            "E3-001": Severity.WAARSCHUWING,
            "E3-002": Severity.WAARSCHUWING,
            "E3-003": Severity.WAARSCHUWING,
            "E3-004": Severity.INFO,
        }
        return severity_map.get(code, Severity.INFO)

    def _get_regeltype_for_code(self, code: str) -> str:
        """Get regeltype for a finding code."""
        regeltype_map = {
            "E3-001": "branche_dekking_mismatch",
            "E3-002": "gezinssamenstelling_rechtspersoon",
            "E3-003": "nulwaarde_verplicht_veld",
            "E3-004": "data_kwaliteit",
        }
        return regeltype_map.get(code, "semantisch_probleem")


def create_llm_engine(
    config: Optional[Config] = None, api_key: Optional[str] = None
) -> LLMSemanticEngine:
    """Create an LLM semantic analysis engine."""
    return LLMSemanticEngine(config=config, api_key=api_key)
