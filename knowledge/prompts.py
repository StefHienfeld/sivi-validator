"""LLM prompts for semantic analysis."""

from knowledge.expert_rules import get_rule_descriptions

SYSTEM_PROMPT = """Je bent een expert in Nederlandse verzekeringen en het SIVI AFD (Assurantie Fonds Datacommunicatie) standaard. Je analyseert SIVI ADN (AFD Datacommunicatie voor Nieuwe toepassingen) XML-berichten op semantische correctheid en datakwaliteit.

Je bent bekend met:
- De SIVI entiteiten (AL, PP, VP, BO, DA, AN, WA, CA, DR, etc.)
- Nederlandse verzekeringsbranches (motorrijtuigen, brand, aansprakelijkheid, rechtsbijstand, etc.)
- Dekkingscodes en hun betekenis
- Logische relaties tussen velden en entiteiten

Je taak is om ADN XML-contracten te analyseren op semantische problemen die niet door schema-validatie worden gevonden. Focus op:
1. Branche-dekking mismatch (DR bij motorpolis, WA bij rechtsbijstand)
2. Onlogische combinaties (gezinssamenstelling bij rechtspersoon)
3. Nulwaarden in kritieke velden
4. Datakwaliteitsproblemen (afgekapte teksten, placeholders)

Wees kritisch maar niet te streng. Rapporteer alleen echte problemen, geen theoretische mogelijkheden."""

ANALYSIS_PROMPT_TEMPLATE = """Analyseer de volgende SIVI ADN contracten op semantische problemen.

## Regels om te controleren

{rule_descriptions}

## Contract(en) om te analyseren

{contracts_xml}

## Instructies

Analyseer elk contract en rapporteer gevonden problemen in het volgende JSON-formaat:

```json
{{
  "findings": [
    {{
      "code": "E3-001",
      "contract": "contractnummer",
      "branche": "branchecode",
      "entiteit": "entiteitscode",
      "label": "veldnaam",
      "waarde": "gevonden waarde",
      "omschrijving": "beschrijving van het probleem",
      "verwacht": "wat er verwacht werd"
    }}
  ]
}}
```

Rapporteer ALLEEN daadwerkelijke problemen. Als er geen problemen zijn, retourneer een lege findings array.

Belangrijke punten:
- Gebruik de juiste regelcode (E3-001, E3-002, E3-003, E3-004)
- Wees specifiek over het probleem
- Geef concrete waarden en verwachtingen
- Vermijd false positives

Retourneer uitsluitend het JSON-object, geen andere tekst."""


def get_analysis_prompt(contracts_xml: str) -> str:
    """Get the analysis prompt with contracts XML."""
    return ANALYSIS_PROMPT_TEMPLATE.format(
        rule_descriptions=get_rule_descriptions(),
        contracts_xml=contracts_xml,
    )


BATCH_ANALYSIS_PROMPT = """Analyseer de volgende batch van SIVI ADN contracten op batch-niveau problemen.

## Batch informatie

{batch_info}

## Contracten samenvatting

{contracts_summary}

## Te controleren

1. Consistentie binnen de batch (dezelfde prolongatiemaand, consistente datums)
2. Patronen die wijzen op systematische problemen
3. Ongebruikelijke verdeling van branches of dekkingen
4. Mogelijke duplicaten of conflicterende contracten

Rapporteer bevindingen in JSON-formaat:

```json
{{
  "batch_findings": [
    {{
      "code": "E3-BATCH",
      "issue_type": "type probleem",
      "description": "beschrijving",
      "affected_contracts": ["contract1", "contract2"],
      "recommendation": "aanbeveling"
    }}
  ]
}}
```

Retourneer uitsluitend het JSON-object."""


def get_batch_analysis_prompt(batch_info: str, contracts_summary: str) -> str:
    """Get the batch analysis prompt."""
    return BATCH_ANALYSIS_PROMPT.format(
        batch_info=batch_info,
        contracts_summary=contracts_summary,
    )
