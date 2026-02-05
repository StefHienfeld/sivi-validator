"""Engine for XPath-based business rules validation (verbandscontroles).

This engine implements SIVI AFD XPath Library validation rules.
The afdXPathLibrary.xml contains relationship controls in XPath 2.0 format:
    if ('logical expression') then 'logical expression' else true()

Since afdXPathLibrary.xml is not included in the standard SIVI downloads,
this module provides:
1. A parser for the XPath library XML format
2. An XPath evaluation engine using lxml
3. Built-in verbandscontroles based on SIVI documentation
4. Support for custom rules via configuration
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from lxml import etree

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


@dataclass
class XPathRule:
    """A single XPath-based validation rule."""

    id: str
    name: str
    description: str
    xpath_condition: str  # The if-condition
    xpath_then: str  # The then-expression (must be true)
    severity: Severity = Severity.FOUT
    category: str = ""  # e.g., "premie", "dekking", "relatie"
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "xpath_condition": self.xpath_condition,
            "xpath_then": self.xpath_then,
            "severity": self.severity.value,
            "category": self.category,
            "enabled": self.enabled,
        }


@dataclass
class XPathRuleResult:
    """Result of evaluating an XPath rule."""

    rule: XPathRule
    passed: bool
    condition_matched: bool  # Did the if-condition match?
    then_result: Optional[bool] = None  # Result of then-expression
    error_message: Optional[str] = None
    context_values: Dict[str, Any] = field(default_factory=dict)


class XPathRuleLibrary:
    """
    Library of XPath-based validation rules.

    Supports loading from:
    1. afdXPathLibrary.xml (if available)
    2. Built-in rules based on SIVI documentation
    3. Custom rules from configuration
    """

    def __init__(self):
        self.rules: Dict[str, XPathRule] = {}
        self._load_builtin_rules()

    def _load_builtin_rules(self) -> None:
        """Load built-in verbandscontroles based on SIVI documentation."""
        # These rules are derived from SIVI AFD documentation and ADN protocol

        # Premium-related rules
        self.add_rule(XPathRule(
            id="VB-001",
            name="Verzekerde som bij uitgebreide dekking",
            description="Bij verzekerde som > 50000 en gebied Europa moet eigen risico > 1000",
            xpath_condition="//CA_VERZSOM > 50000 and //CA_GEBIED = 'E'",
            xpath_then="//CA_ERB > 1000",
            category="premie",
        ))

        self.add_rule(XPathRule(
            id="VB-002",
            name="Minimale verzekerde som Europa",
            description="Bij gebied Europa moet verzekerde som > 30000 en eigen risico > 1000",
            xpath_condition="//CA_GEBIED = 'E'",
            xpath_then="//CA_VERZSOM > 30000 and //CA_ERB > 1000",
            category="premie",
        ))

        # Coverage combination rules
        self.add_rule(XPathRule(
            id="VB-003",
            name="WA-dekking verplicht bij Casco",
            description="Als Casco dekking (CA) aanwezig is, moet ook WA dekking (WA) aanwezig zijn",
            xpath_condition="count(//CA) > 0",
            xpath_then="count(//WA) > 0",
            category="dekking",
        ))

        self.add_rule(XPathRule(
            id="VB-004",
            name="Rechtsbijstand bij motorrijtuig",
            description="Bij branche 20-25 (motor) mag rechtsbijstand (DR) niet als hoofd-dekking",
            xpath_condition="//PP_BRANCHE >= 20 and //PP_BRANCHE <= 25",
            xpath_then="count(//DR[DR_CODE = '6001']) = 0",
            category="dekking",
            severity=Severity.WAARSCHUWING,
        ))

        # Object-type rules
        self.add_rule(XPathRule(
            id="VB-005",
            name="Voertuig verplicht bij motorbranche",
            description="Bij motorrijtuigverzekering (branche 20-25) moet PV-entiteit aanwezig zijn",
            xpath_condition="//PP_BRANCHE >= 20 and //PP_BRANCHE <= 25",
            xpath_then="count(//PV) > 0",
            category="object",
        ))

        self.add_rule(XPathRule(
            id="VB-006",
            name="Geen voertuig bij inboedel",
            description="Bij inboedelverzekering (branche 30-35) mag geen PV-entiteit aanwezig zijn",
            xpath_condition="//PP_BRANCHE >= 30 and //PP_BRANCHE <= 35",
            xpath_then="count(//PV) = 0",
            category="object",
            severity=Severity.WAARSCHUWING,
        ))

        # Relationship rules
        self.add_rule(XPathRule(
            id="VB-007",
            name="Verzekeringnemer aanwezig",
            description="Elke polis moet minimaal één verzekeringnemer (VP met relatiecode VN) hebben",
            xpath_condition="true()",
            xpath_then="count(//VP[VP_RELCODE = 'VN' or VP_RELCODE = '01']) > 0",
            category="relatie",
        ))

        self.add_rule(XPathRule(
            id="VB-008",
            name="Premiebetaler bij incasso",
            description="Bij incasso (betaalwijze I) moet premiebetaler adres hebben",
            xpath_condition="//PP_BETWIJZ = 'I'",
            xpath_then="count(//AD) > 0",
            category="relatie",
        ))

        # Date-related rules
        self.add_rule(XPathRule(
            id="VB-009",
            name="Prolongatiedatum na ingangsdatum",
            description="Prolongatiedatum moet na of gelijk aan ingangsdatum liggen",
            xpath_condition="//PP_PROLDAT and //PP_INGDAT",
            xpath_then="//PP_PROLDAT >= //PP_INGDAT",
            category="datum",
        ))

        self.add_rule(XPathRule(
            id="VB-010",
            name="Einddatum dekking",
            description="Als einddatum dekking gevuld, moet deze na ingangsdatum liggen",
            xpath_condition="//DA_EINDDAT",
            xpath_then="//DA_EINDDAT >= //DA_INGDAT",
            category="datum",
        ))

        # Premium consistency rules
        self.add_rule(XPathRule(
            id="VB-011",
            name="Positieve bruto premie",
            description="Bruto premie moet positief zijn (behalve bij royement)",
            xpath_condition="//PP_MUTEFG != 'R'",
            xpath_then="//PP_BTP >= 0",
            category="premie",
        ))

        self.add_rule(XPathRule(
            id="VB-012",
            name="Assurantiebelasting bij verzekeringnemer NL",
            description="Bij Nederlandse verzekeringnemer moet assurantiebelasting gevuld zijn",
            xpath_condition="//VP_LAND = 'NL' or //VP_LAND = 'NLD' or not(//VP_LAND)",
            xpath_then="//PP_TASS or //PP_TASS = 0",
            category="premie",
            severity=Severity.WAARSCHUWING,
        ))

    def add_rule(self, rule: XPathRule) -> None:
        """Add a rule to the library."""
        self.rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> None:
        """Remove a rule from the library."""
        if rule_id in self.rules:
            del self.rules[rule_id]

    def get_rule(self, rule_id: str) -> Optional[XPathRule]:
        """Get a rule by ID."""
        return self.rules.get(rule_id)

    def get_rules_by_category(self, category: str) -> List[XPathRule]:
        """Get all rules in a category."""
        return [r for r in self.rules.values() if r.category == category and r.enabled]

    def get_enabled_rules(self) -> List[XPathRule]:
        """Get all enabled rules."""
        return [r for r in self.rules.values() if r.enabled]

    def load_from_xml(self, xml_path: Path) -> int:
        """
        Load rules from afdXPathLibrary.xml format.

        Returns number of rules loaded.
        """
        if not xml_path.exists():
            return 0

        try:
            tree = etree.parse(str(xml_path))
            root = tree.getroot()
            count = 0

            # Parse XPath rules from the XML
            for rule_elem in root.findall(".//rule"):
                rule_id = rule_elem.get("id", f"XML-{count + 1:03d}")
                name = rule_elem.findtext("name", "")
                description = rule_elem.findtext("description", "")
                condition = rule_elem.findtext("condition", "")
                then_expr = rule_elem.findtext("then", "")
                category = rule_elem.findtext("category", "")
                severity_str = rule_elem.findtext("severity", "FOUT")

                if condition and then_expr:
                    severity = Severity.FOUT
                    if severity_str.upper() == "WAARSCHUWING":
                        severity = Severity.WAARSCHUWING
                    elif severity_str.upper() == "INFO":
                        severity = Severity.INFO

                    self.add_rule(XPathRule(
                        id=rule_id,
                        name=name,
                        description=description,
                        xpath_condition=condition,
                        xpath_then=then_expr,
                        severity=severity,
                        category=category,
                    ))
                    count += 1

            return count
        except etree.XMLSyntaxError:
            return 0


class XPathEvaluator:
    """
    Evaluates XPath expressions against XML documents.

    Uses lxml for XPath 1.0 evaluation. XPath 2.0 expressions are
    simplified to XPath 1.0 where possible.
    """

    def __init__(self):
        self._namespaces = {
            "afd": "http://www.sivi.org/berichtschema",
            "fm": "http://schemas.sivi.org/AFD/Formaten/2026/2/1",
            "cl": "http://schemas.sivi.org/AFD/Codelijsten/2026/2/1",
        }

    def evaluate(
        self,
        xml_doc: etree._Element,
        xpath: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Evaluate an XPath expression against an XML document.

        Returns the result of the expression (bool, number, string, or nodeset).
        """
        try:
            # Simplify XPath 2.0 to 1.0 if needed
            simplified_xpath = self._simplify_xpath(xpath)
            result = xml_doc.xpath(simplified_xpath, namespaces=self._namespaces)

            # Convert result to Python type
            if isinstance(result, list):
                if len(result) == 0:
                    return None
                elif len(result) == 1:
                    return self._convert_result(result[0])
                else:
                    return [self._convert_result(r) for r in result]
            else:
                return self._convert_result(result)
        except etree.XPathEvalError:
            return None

    def _simplify_xpath(self, xpath: str) -> str:
        """Simplify XPath 2.0 expressions to XPath 1.0."""
        # Replace some common XPath 2.0 constructs
        simplified = xpath

        # Handle if-then-else (not supported in 1.0)
        # Convert: if (cond) then val1 else val2
        # We just evaluate the condition separately
        if_match = re.match(r"if\s*\((.+?)\)\s*then\s+(.+?)\s+else\s+(.+)", simplified)
        if if_match:
            # Return just the condition for now
            simplified = if_match.group(1)

        return simplified

    def _convert_result(self, result: Any) -> Any:
        """Convert XPath result to Python type."""
        if isinstance(result, etree._Element):
            # Return text content of element
            return result.text
        elif isinstance(result, etree._ElementUnicodeResult):
            return str(result)
        elif isinstance(result, bool):
            return result
        elif isinstance(result, (int, float)):
            return result
        else:
            return str(result) if result is not None else None

    def evaluate_rule(
        self,
        xml_doc: etree._Element,
        rule: XPathRule,
    ) -> XPathRuleResult:
        """
        Evaluate an XPath rule against an XML document.

        Implements: if (condition) then (then_expr) else true()
        """
        try:
            # First evaluate the condition
            condition_result = self.evaluate(xml_doc, rule.xpath_condition)
            condition_matched = bool(condition_result)

            if not condition_matched:
                # Condition not matched, rule passes (else true())
                return XPathRuleResult(
                    rule=rule,
                    passed=True,
                    condition_matched=False,
                    then_result=None,
                )

            # Condition matched, evaluate the then expression
            then_result = self.evaluate(xml_doc, rule.xpath_then)
            passed = bool(then_result)

            return XPathRuleResult(
                rule=rule,
                passed=passed,
                condition_matched=True,
                then_result=passed,
            )
        except Exception as e:
            return XPathRuleResult(
                rule=rule,
                passed=True,  # Don't fail on evaluation errors
                condition_matched=False,
                error_message=str(e),
            )


class XPathBusinessRulesEngine(ValidationEngine):
    """
    XPath-based business rules validation engine.

    This engine evaluates XPath verbandscontroles from the SIVI afdXPathLibrary
    and built-in rules. It validates relationship controls between entities
    and values in the XML document.

    Error codes:
    - EX-001: Verbandscontrole gefaald (relationship control failed)
    - EX-002: XPath evaluatiefout (evaluation error)
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.library = XPathRuleLibrary()
        self.evaluator = XPathEvaluator()

        # Try to load afdXPathLibrary.xml if available
        xpath_library_path = self.config.sivi_dir / "afdXPathLibrary.xml"
        self.library.load_from_xml(xpath_library_path)

    @property
    def engine_type(self) -> Engine:
        return Engine.RULES  # Share engine type with business rules

    def validate(self, batch: BatchData) -> List[Finding]:
        """Validate a batch using XPath rules."""
        findings = []

        for contract in batch.contracts:
            findings.extend(self._validate_contract(contract))

        return findings

    def _validate_contract(self, contract: ContractData) -> List[Finding]:
        """Validate a single contract using XPath rules."""
        findings = []

        # Build XML document from contract data
        xml_doc = self._build_xml_from_contract(contract)
        if xml_doc is None:
            return findings

        # Evaluate all enabled rules
        for rule in self.library.get_enabled_rules():
            result = self.evaluator.evaluate_rule(xml_doc, rule)

            if result.error_message:
                # Log evaluation error (as warning, not as validation failure)
                findings.append(Finding(
                    severity=Severity.INFO,
                    engine=Engine.RULES,
                    code="EX-002",
                    regeltype="xpath_evaluatie_fout",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit="",
                    label=rule.id,
                    waarde=rule.xpath_condition[:50],
                    omschrijving=f"XPath evaluatiefout in regel {rule.id}: {result.error_message}",
                    verwacht="Geldige XPath expressie",
                    bron="afdXPathLibrary",
                ))

            elif not result.passed and result.condition_matched:
                # Rule failed
                findings.append(Finding(
                    severity=rule.severity,
                    engine=Engine.RULES,
                    code="EX-001",
                    regeltype="verbandscontrole_gefaald",
                    contract=contract.contract_nummer,
                    branche=contract.branche,
                    entiteit="",
                    label=rule.id,
                    waarde=f"conditie: {rule.xpath_condition[:40]}",
                    omschrijving=f"Verbandscontrole {rule.id} ({rule.name}) gefaald: {rule.description}",
                    verwacht=f"then: {rule.xpath_then[:40]}",
                    bron="afdXPathLibrary",
                ))

        return findings

    def _build_xml_from_contract(self, contract: ContractData) -> Optional[etree._Element]:
        """Build an XML document from contract data for XPath evaluation."""
        try:
            # If we have raw XML, parse it directly
            if contract.raw_xml:
                return etree.fromstring(contract.raw_xml.encode())

            # Otherwise, build a simplified XML structure
            root = etree.Element("Contract")

            # Add contract-level attributes
            etree.SubElement(root, "AL_CNTRNUM").text = contract.contract_nummer
            etree.SubElement(root, "PP_BRANCHE").text = contract.branche

            # Add all entities
            self._add_entities_to_xml(root, contract.entities)

            return root
        except Exception:
            return None

    def _add_entities_to_xml(
        self,
        parent: etree._Element,
        entities: List[EntityData],
    ) -> None:
        """Recursively add entities to XML element."""
        for entity in entities:
            entity_elem = etree.SubElement(parent, entity.entity_type)

            # Add VOLGNUM
            if entity.volgnum is not None:
                volgnum_elem = etree.SubElement(
                    entity_elem, f"{entity.entity_type}_VOLGNUM"
                )
                volgnum_elem.text = str(entity.volgnum)

            # Add attributes
            for attr_name, attr_value in entity.attributes.items():
                attr_elem = etree.SubElement(entity_elem, attr_name)
                attr_elem.text = attr_value

            # Add children recursively
            if entity.children:
                self._add_entities_to_xml(entity_elem, entity.children)

    def add_custom_rule(self, rule: XPathRule) -> None:
        """Add a custom XPath rule."""
        self.library.add_rule(rule)

    def disable_rule(self, rule_id: str) -> None:
        """Disable a rule by ID."""
        rule = self.library.get_rule(rule_id)
        if rule:
            rule.enabled = False

    def enable_rule(self, rule_id: str) -> None:
        """Enable a rule by ID."""
        rule = self.library.get_rule(rule_id)
        if rule:
            rule.enabled = True

    def get_rule_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded rules."""
        rules = self.library.rules.values()
        return {
            "total_rules": len(rules),
            "enabled_rules": sum(1 for r in rules if r.enabled),
            "by_category": {
                cat: sum(1 for r in rules if r.category == cat)
                for cat in set(r.category for r in rules)
            },
            "by_severity": {
                sev.value: sum(1 for r in rules if r.severity == sev)
                for sev in Severity
            },
        }


# Convenience function for getting an XPath engine instance
_xpath_engine: Optional[XPathBusinessRulesEngine] = None


def get_xpath_engine(config: Optional[Config] = None) -> XPathBusinessRulesEngine:
    """Get a cached XPath engine instance."""
    global _xpath_engine
    if _xpath_engine is None:
        _xpath_engine = XPathBusinessRulesEngine(config)
    return _xpath_engine
