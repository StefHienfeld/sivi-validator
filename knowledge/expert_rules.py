"""Expert business rules for semantic validation."""

from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass
class ExpertRule:
    """Definition of an expert validation rule."""

    code: str
    name: str
    description: str
    severity: str  # "FOUT", "WAARSCHUWING", "INFO"
    check_description: str
    examples: List[str]


# Expert rules for LLM semantic analysis
EXPERT_RULES = [
    ExpertRule(
        code="E3-001",
        name="branche_dekking_mismatch",
        description="Dekkingsentiteit past niet bij de branche",
        severity="WAARSCHUWING",
        check_description="""
        Controleer of de gebruikte dekkingsentiteiten passen bij de branche van het contract.
        Bijvoorbeeld:
        - DR (Rechtsbijstand) entiteit bij branche 050 (Aansprakelijkheid) is verdacht
        - WA (Wettelijke Aansprakelijkheid motor) bij branche 060 (Rechtsbijstand) is verdacht
        - AO (Arbeidsongeschiktheid) bij branche 030 (Brand) is verdacht
        """,
        examples=[
            "Contract DL123 branche 050 heeft DR-entiteit - rechtsbijstanddekking bij aansprakelijkheidspolis",
            "Contract DL456 branche 020 heeft AO-entiteit - arbeidsongeschiktheid bij motorpolis",
        ],
    ),
    ExpertRule(
        code="E3-002",
        name="gezinssamenstelling_rechtspersoon",
        description="Gezinssamenstelling ingevuld bij rechtspersoon",
        severity="WAARSCHUWING",
        check_description="""
        Controleer of gezinssamenstelling-velden (VP_GEZINS, VP_KINDEREN, etc.)
        zijn ingevuld terwijl de verzekeringnemer een rechtspersoon is.
        Een rechtspersoon (bedrijf) heeft geen gezinssamenstelling.

        Indicatoren voor rechtspersoon:
        - VP_RECHTSP = 'J'
        - VP_BEDRNM is ingevuld
        - KVK-nummer is ingevuld
        """,
        examples=[
            "VP met RECHTSP=J heeft GEZINS=1 - rechtspersoon met gezinssamenstelling",
            "Bedrijf 'ABC BV' heeft KINDEREN=2 ingevuld",
        ],
    ),
    ExpertRule(
        code="E3-003",
        name="nulwaarde_verplicht_veld",
        description="Nulwaarde in veld waar dat niet logisch is",
        severity="WAARSCHUWING",
        check_description="""
        Controleer op nulwaarden in velden waar een nul niet logisch is:
        - DA_VRZSOMJ = 0 (verzekerd bedrag per jaar = 0)
        - PP_BTP = 0 (bruto termijnpremie = 0) bij actieve polis
        - AN_VRZSOMJ = 0 bij actieve dekking

        Een nul kan wijzen op ontbrekende of foutieve data.
        """,
        examples=[
            "DA_VRZSOMJ = 0 terwijl dekking actief is",
            "PP_BTP = 0 bij lopend contract",
        ],
    ),
    ExpertRule(
        code="E3-004",
        name="data_kwaliteit",
        description="Mogelijke datakwaliteitsproblemen",
        severity="INFO",
        check_description="""
        Controleer op mogelijke datakwaliteitsproblemen:
        - Afgekapte teksten (eindigen op '...' of exact op maximale lengte)
        - Onlogische combinaties (einddatum voor ingangsdatum)
        - Verdachte patronen (alle letters uppercase, rare karakters)
        - Placeholder waarden ('TEST', 'XXX', '000000')
        """,
        examples=[
            "VP_ANAAM = 'JANSEN VAN DEN B...' - mogelijk afgekap",
            "VP_STRAAT = 'XXXXXXXXXXX' - placeholder waarde",
        ],
    ),
]


def get_rule_by_code(code: str) -> Optional[ExpertRule]:
    """Get an expert rule by its code."""
    for rule in EXPERT_RULES:
        if rule.code == code:
            return rule
    return None


def get_rule_descriptions() -> str:
    """Get formatted descriptions of all rules for LLM prompt."""
    descriptions = []
    for rule in EXPERT_RULES:
        desc = f"""
## {rule.code}: {rule.name}
Severity: {rule.severity}
Beschrijving: {rule.description}

Wat te controleren:
{rule.check_description}

Voorbeelden:
{chr(10).join('- ' + ex for ex in rule.examples)}
"""
        descriptions.append(desc)
    return "\n".join(descriptions)
