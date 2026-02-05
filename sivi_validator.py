#!/usr/bin/env python3
"""
SIVI AFD XML Validator - CLI Entry Point

Validates SIVI AFD XML files (Dutch insurance ADN batch format) at multiple levels:
0. Engine 0: Native XSD validation (hierarchy, structure)
1. Engine 1: Schema-derived validation (labels, codes, formats, decimal precision)
2. Engine 2: Business rules (VOLGNUM, premiums, dates, BSN, XD forbidden, branch-coverage)
3. Engine 3: LLM semantic analysis (branch-coverage match, context logic)
4. Engine 4: XPath verbandscontroles (relationship controls)
5. Engine 5: Encoding & data quality validation (UTF-8, BOM, placeholders)
F. Final: Certification engine (send-ready guarantee)

Usage:
    python sivi_validator.py input.xml
    python sivi_validator.py input.xml --engines 0,1,2,4,5 --output json --output-file report.json
"""

import sys
from pathlib import Path
from typing import List, Optional, Set

import click

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import Config, set_config
from engines.base import BatchData, Engine, Finding, ValidationResult
from engines.engine0_xsd import XSDValidationEngine
from engines.engine1_schema import SchemaValidationEngine
from engines.engine2_rules import BusinessRulesEngine
from engines.engine3_llm import LLMSemanticEngine
from engines.engine_xpath import XPathBusinessRulesEngine
from engines.engine_encoding import EncodingValidationEngine
from engines.engine_final import FinalValidationEngine, SIVICertificationIntegration
from parser.xml_parser import XMLParser
from parser.version_manager import detect_xml_version, get_version_manager
from report.console_reporter import ConsoleReporter
from report.json_reporter import JSONReporter
from report.xlsx_reporter import XLSXReporter


def parse_engines(engines_str: str) -> Set[int]:
    """Parse engines string like '0,1,2,3,4,5' into set of integers."""
    if not engines_str:
        return {0, 1, 2, 4, 5}  # Default: all except LLM (3) which needs API key

    engines = set()
    for part in engines_str.split(","):
        try:
            engine_num = int(part.strip())
            if engine_num in (0, 1, 2, 3, 4, 5):
                engines.add(engine_num)
        except ValueError:
            pass

    return engines if engines else {0, 1, 2, 4, 5}


def validate_batch(
    batch: BatchData,
    engines: Set[int],
    config: Config,
    api_key: Optional[str] = None,
    certify: bool = True,
) -> ValidationResult:
    """Run validation engines on a batch and optionally certify."""
    findings = []

    # Engine 0: XSD validation
    if 0 in engines:
        engine0 = XSDValidationEngine(config)
        findings.extend(engine0.validate(batch))

    # Engine 5: Encoding & data quality (run early to catch encoding issues)
    if 5 in engines:
        engine5 = EncodingValidationEngine(config)
        findings.extend(engine5.validate(batch))

    # Engine 1: Schema validation (includes decimal precision)
    if 1 in engines:
        engine1 = SchemaValidationEngine(config)
        findings.extend(engine1.validate(batch))

    # Engine 2: Business rules (extended with branch-coverage, etc.)
    if 2 in engines:
        engine2 = BusinessRulesEngine(config)
        findings.extend(engine2.validate(batch))

    # Engine 4: XPath verbandscontroles
    if 4 in engines:
        engine4 = XPathBusinessRulesEngine(config)
        findings.extend(engine4.validate(batch))

    # Engine 3: LLM semantic analysis
    if 3 in engines:
        engine3 = LLMSemanticEngine(config, api_key=api_key)
        findings.extend(engine3.validate(batch))

    # Final validation and certification
    certificate = None
    if certify and config.enable_final_certification:
        final_engine = FinalValidationEngine(config)
        final_findings, certificate = final_engine.validate_and_certify(batch, findings)
        findings.extend(final_findings)

    return ValidationResult(findings=findings, certificate=certificate)


def output_report(
    findings: List[Finding],
    output_format: str,
    output_file: Optional[str],
    source_file: str,
) -> None:
    """Output the validation report in the specified format."""
    if output_format == "console":
        reporter = ConsoleReporter()
        reporter.report(findings, source_file)

    elif output_format == "json":
        reporter = JSONReporter()
        if output_file:
            reporter.write(findings, output_file, source_file)
            click.echo(f"JSON rapport geschreven naar: {output_file}")
        else:
            print(reporter.generate(findings, source_file))

    elif output_format == "xlsx":
        if not output_file:
            output_file = Path(source_file).stem + "_rapport.xlsx"
        reporter = XLSXReporter()
        reporter.write(findings, output_file, source_file)
        click.echo(f"Excel rapport geschreven naar: {output_file}")

    else:
        click.echo(f"Onbekend output formaat: {output_format}", err=True)


@click.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "--engines",
    "-e",
    default="0,1,2,4,5",
    help="Comma-separated list of engines (0=XSD, 1=Schema, 2=Rules, 3=LLM, 4=XPath, 5=Encoding). Default: 0,1,2,4,5",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["console", "json", "xlsx"]),
    default="console",
    help="Output format. Default: console",
)
@click.option(
    "--output-file",
    "-f",
    type=click.Path(),
    help="Output file path (for json/xlsx formats)",
)
@click.option(
    "--sivi-dir",
    type=click.Path(exists=True),
    help="Path to SIVI schema directory",
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    help="Anthropic API key for Engine 3 (LLM)",
)
@click.option(
    "--detailed",
    "-d",
    is_flag=True,
    help="Show detailed findings (console output only)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose output",
)
@click.option(
    "--no-certify",
    is_flag=True,
    help="Skip final certification (for faster validation)",
)
@click.option(
    "--no-hierarchy",
    is_flag=True,
    help="Disable hierarchy validation",
)
@click.option(
    "--show-version",
    is_flag=True,
    help="Show detected SIVI version of the XML file",
)
@click.option(
    "--sivi-cert-info",
    is_flag=True,
    help="Show SIVI official certification information",
)
@click.option(
    "--all-engines",
    is_flag=True,
    help="Run all engines including LLM (requires ANTHROPIC_API_KEY)",
)
def main(
    input_file: str,
    engines: str,
    output: str,
    output_file: Optional[str],
    sivi_dir: Optional[str],
    api_key: Optional[str],
    detailed: bool,
    verbose: bool,
    no_certify: bool,
    no_hierarchy: bool,
    show_version: bool,
    sivi_cert_info: bool,
    all_engines: bool,
) -> None:
    """
    Validate a SIVI AFD XML file.

    INPUT_FILE: Path to the ADN batch XML file to validate.

    Examples:

        python sivi_validator.py batch.xml

        python sivi_validator.py batch.xml --engines 0,1,2,4,5 --output json

        python sivi_validator.py batch.xml -o xlsx -f report.xlsx

        python sivi_validator.py batch.xml --all-engines  # includes LLM

        python sivi_validator.py batch.xml --show-version  # show SIVI version
    """
    # Show SIVI certification info if requested
    if sivi_cert_info:
        integration = SIVICertificationIntegration()
        info = integration.get_certification_info()
        click.echo("\n" + "=" * 60)
        click.echo("SIVI OFFICIAL CERTIFICATION INFORMATION")
        click.echo("=" * 60)
        click.echo(f"\nPortal URL: {info['portal_url']}")
        click.echo(f"Downloads: {info['downloads_url']}")
        click.echo(f"API available: {info['api_available']}")
        click.echo("\nManual process:")
        for step in info['manual_process']:
            click.echo(f"  {step}")
        click.echo(f"\nNote: {info['note']}")
        click.echo("=" * 60 + "\n")
        if not Path(input_file).exists():
            return

    # Configure
    config = Config()
    if sivi_dir:
        config.sivi_dir = Path(sivi_dir)
    if no_hierarchy:
        config.enable_hierarchy_validation = False
    if no_certify:
        config.enable_final_certification = False
    set_config(config)

    # Show version info if requested
    if show_version:
        try:
            version = detect_xml_version(Path(input_file))
            click.echo(f"\nSIVI Version detected: {version}")
            if version.namespace_uri:
                click.echo(f"Namespace: {version.namespace_uri}")
            click.echo("")
        except Exception as e:
            click.echo(f"Could not detect version: {e}", err=True)

    # Parse engines
    if all_engines:
        engine_set = {0, 1, 2, 3, 4, 5}
    else:
        engine_set = parse_engines(engines)

    if verbose:
        engine_names = {
            0: "XSD",
            1: "Schema",
            2: "Business Rules",
            3: "LLM",
            4: "XPath",
            5: "Encoding"
        }
        enabled = [engine_names[e] for e in sorted(engine_set)]
        click.echo(f"Engines: {', '.join(enabled)}")
        click.echo(f"Input: {input_file}")
        if not no_certify:
            click.echo("Final certification: enabled")

    # Parse input file
    try:
        parser = XMLParser(hierarchical=True)
        batch = parser.parse_file(input_file)
    except Exception as e:
        click.echo(f"Fout bij het parsen van {input_file}: {e}", err=True)
        sys.exit(1)

    if verbose:
        click.echo(f"Contracten gevonden: {len(batch.contracts)}")

    # Skip LLM engine if no API key
    if 3 in engine_set and not api_key:
        if verbose:
            click.echo("Engine 3 (LLM) overgeslagen: geen ANTHROPIC_API_KEY")
        engine_set.discard(3)

    # Validate
    try:
        result = validate_batch(
            batch,
            engine_set,
            config,
            api_key,
            certify=not no_certify
        )
    except Exception as e:
        click.echo(f"Fout tijdens validatie: {e}", err=True)
        sys.exit(1)

    if verbose:
        click.echo(f"Bevindingen: {len(result.findings)}")
        if result.certificate:
            click.echo(f"Certificaat: {result.certificate.is_valid}")

    # Output report
    if output == "console" and detailed:
        reporter = ConsoleReporter()
        reporter.report_detailed(result.findings)
    else:
        output_report(result.findings, output, output_file, input_file)

    # Print certification summary
    if result.certificate:
        click.echo("\n" + result.get_summary())
    elif not no_certify and result.findings:
        click.echo("\n" + result.get_summary())

    # Exit code based on findings
    has_errors = any(f.severity.value == "FOUT" for f in result.findings)
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
