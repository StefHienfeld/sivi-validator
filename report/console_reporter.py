"""Console reporter with Rich formatting."""

from collections import defaultdict
from typing import Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from engines.base import Engine, Finding, Severity


class ConsoleReporter:
    """Generate rich console output for validation findings."""

    # Severity colors
    SEVERITY_COLORS = {
        Severity.FOUT: "red",
        Severity.WAARSCHUWING: "yellow",
        Severity.INFO: "blue",
    }

    # Severity symbols
    SEVERITY_SYMBOLS = {
        Severity.FOUT: "[red]X[/red]",
        Severity.WAARSCHUWING: "[yellow]![/yellow]",
        Severity.INFO: "[blue]i[/blue]",
    }

    def __init__(self):
        self.console = Console()

    def report(self, findings: List[Finding], source_file: str = "") -> None:
        """Generate and print the report."""
        self._print_header(source_file, len(findings))

        if not findings:
            self.console.print("[green]Geen bevindingen - validatie geslaagd![/green]")
            return

        # Print summary by severity
        self._print_summary(findings)

        # Print findings grouped by contract
        self._print_findings_by_contract(findings)

    def _print_header(self, source_file: str, finding_count: int) -> None:
        """Print report header."""
        title = "SIVI AFD XML Validator - Rapport"
        if source_file:
            title += f"\n[dim]{source_file}[/dim]"

        self.console.print()
        self.console.print(Panel(title, style="bold blue"))
        self.console.print()

    def _print_summary(self, findings: List[Finding]) -> None:
        """Print summary statistics."""
        # Count by severity
        severity_counts: Dict[Severity, int] = defaultdict(int)
        for f in findings:
            severity_counts[f.severity] += 1

        # Count by engine
        engine_counts: Dict[Engine, int] = defaultdict(int)
        for f in findings:
            engine_counts[f.engine] += 1

        # Create summary table
        table = Table(title="Samenvatting", show_header=True)
        table.add_column("Categorie", style="bold")
        table.add_column("Aantal", justify="right")

        # Severity rows
        for severity in [Severity.FOUT, Severity.WAARSCHUWING, Severity.INFO]:
            count = severity_counts[severity]
            color = self.SEVERITY_COLORS[severity]
            table.add_row(
                f"[{color}]{severity.value}[/{color}]",
                str(count),
            )

        table.add_section()

        # Engine rows
        engine_names = {
            Engine.SCHEMA: "Engine 1: Schema",
            Engine.RULES: "Engine 2: Business Rules",
            Engine.LLM: "Engine 3: LLM Semantiek",
        }
        for engine, name in engine_names.items():
            count = engine_counts[engine]
            if count > 0:
                table.add_row(name, str(count))

        table.add_section()
        table.add_row("[bold]Totaal[/bold]", f"[bold]{len(findings)}[/bold]")

        self.console.print(table)
        self.console.print()

    def _print_findings_by_contract(self, findings: List[Finding]) -> None:
        """Print findings grouped by contract."""
        # Group by contract
        by_contract: Dict[str, List[Finding]] = defaultdict(list)
        for f in findings:
            by_contract[f.contract].append(f)

        # Print each contract's findings
        for contract, contract_findings in sorted(by_contract.items()):
            self._print_contract_findings(contract, contract_findings)

    def _print_contract_findings(
        self, contract: str, findings: List[Finding]
    ) -> None:
        """Print findings for a single contract."""
        # Get branche from first finding
        branche = findings[0].branche if findings else ""
        header = f"Contract: {contract}"
        if branche:
            header += f" (branche {branche})"

        self.console.print(f"[bold]{header}[/bold]")
        self.console.print("-" * len(header))

        # Create table for findings
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        table.add_column("", width=3)  # Severity symbol
        table.add_column("Code", style="cyan")
        table.add_column("Entiteit")
        table.add_column("Label")
        table.add_column("Probleem")

        for f in findings:
            symbol = self.SEVERITY_SYMBOLS[f.severity]
            problem = f.omschrijving
            if len(problem) > 60:
                problem = problem[:57] + "..."

            table.add_row(symbol, f.code, f.entiteit, f.label, problem)

        self.console.print(table)
        self.console.print()

    def report_detailed(self, findings: List[Finding]) -> None:
        """Print detailed report with full information per finding."""
        if not findings:
            self.console.print("[green]Geen bevindingen.[/green]")
            return

        for i, f in enumerate(findings, 1):
            color = self.SEVERITY_COLORS[f.severity]

            panel_content = f"""
[bold]Contract:[/bold] {f.contract}
[bold]Branche:[/bold] {f.branche}
[bold]Entiteit:[/bold] {f.entiteit}
[bold]Label:[/bold] {f.label}
[bold]Waarde:[/bold] {f.waarde}

[bold]Omschrijving:[/bold]
{f.omschrijving}

[bold]Verwacht:[/bold]
{f.verwacht}

[dim]Bron: {f.bron}[/dim]
"""
            title = f"[{color}]{f.severity.value}[/{color}] {f.code} - {f.regeltype}"
            self.console.print(Panel(panel_content.strip(), title=title))
            self.console.print()


def report_to_console(findings: List[Finding], source_file: str = "") -> None:
    """Convenience function to report findings to console."""
    reporter = ConsoleReporter()
    reporter.report(findings, source_file)
