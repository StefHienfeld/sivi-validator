"""JSON reporter for validation findings."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from engines.base import Finding


class JSONReporter:
    """Generate JSON output for validation findings."""

    def __init__(self, pretty: bool = True):
        self.pretty = pretty

    def generate(
        self,
        findings: List[Finding],
        source_file: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate JSON report string."""
        report = self._build_report(findings, source_file, metadata)

        if self.pretty:
            return json.dumps(report, indent=2, ensure_ascii=False)
        else:
            return json.dumps(report, ensure_ascii=False)

    def write(
        self,
        findings: List[Finding],
        output_path: Union[str, Path],
        source_file: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write JSON report to file."""
        json_content = self.generate(findings, source_file, metadata)

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(json_content)

    def _build_report(
        self,
        findings: List[Finding],
        source_file: str,
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build the report dictionary."""
        report = {
            "validator": "sivi-validator",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "source_file": source_file,
            "summary": self._build_summary(findings),
            "findings": [f.to_dict() for f in findings],
        }

        if metadata:
            report["metadata"] = metadata

        return report

    def _build_summary(self, findings: List[Finding]) -> Dict[str, Any]:
        """Build summary statistics."""
        from collections import Counter

        severity_counts = Counter(f.severity.value for f in findings)
        engine_counts = Counter(f.engine.value for f in findings)
        contract_counts = Counter(f.contract for f in findings)
        criticality_counts = Counter(
            f.criticality.value if f.criticality else "AANDACHT"
            for f in findings
        )

        return {
            "total": len(findings),
            "by_severity": dict(severity_counts),
            "by_criticality": dict(criticality_counts),
            "by_engine": dict(engine_counts),
            "contracts_with_findings": len(contract_counts),
            "findings_per_contract": dict(contract_counts),
        }


def report_to_json(
    findings: List[Finding],
    output_path: Optional[Union[str, Path]] = None,
    source_file: str = "",
) -> str:
    """Convenience function to generate JSON report."""
    reporter = JSONReporter()

    if output_path:
        reporter.write(findings, output_path, source_file)

    return reporter.generate(findings, source_file)
