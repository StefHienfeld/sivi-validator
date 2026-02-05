"""
Expert knowledge processor for loading YAML expert rules.
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class ExpertProcessor:
    """Processor for loading expert knowledge from YAML files."""

    def __init__(self, knowledge_dir: Path):
        """
        Initialize the expert processor.

        Args:
            knowledge_dir: Path to the knowledge directory containing YAML files.
        """
        self.knowledge_dir = knowledge_dir

    def process(self, filename: str = "expert_knowledge.yaml") -> list[dict]:
        """
        Process the expert knowledge YAML file.

        Args:
            filename: Name of the YAML file to process.

        Returns:
            List of document chunks.
        """
        filepath = self.knowledge_dir / filename
        if not filepath.exists():
            logger.warning(f"Expert knowledge file not found: {filepath}")
            return []

        logger.info(f"Processing expert knowledge: {filename}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
            return []

        all_docs = []

        # Process rules
        rules = data.get("rules", [])
        for rule in rules:
            docs = self._process_rule(rule, filename)
            all_docs.extend(docs)

        # Process FAQ
        faq = data.get("faq", [])
        for faq_item in faq:
            doc = self._process_faq(faq_item, filename)
            if doc:
                all_docs.append(doc)

        logger.info(f"Created {len(all_docs)} documents from expert knowledge")
        return all_docs

    def _process_rule(self, rule: dict, filename: str) -> list[dict]:
        """Process a single expert rule."""
        docs = []

        rule_id = rule.get("id", "")
        title = rule.get("title", "")
        description = rule.get("description", "")
        affected_entities = rule.get("affected_entities", [])
        severity = rule.get("severity", "")
        related_codes = rule.get("related_finding_codes", [])
        examples = rule.get("examples", [])
        handbook_refs = rule.get("handbook_references", [])

        if not rule_id or not description:
            return docs

        # Main rule document
        content = f"Expert Regel {rule_id}: {title}\n\n"
        content += f"{description}\n\n"

        if affected_entities:
            content += f"Betreffende entiteiten: {', '.join(affected_entities)}\n"
        if severity:
            content += f"Ernst niveau: {severity}\n"
        if related_codes:
            content += f"Gerelateerde foutcodes: {', '.join(related_codes)}\n"

        if handbook_refs:
            content += "\nHandboek referenties:\n"
            for ref in handbook_refs:
                content += f"- {ref.get('file', '')} sectie {ref.get('section', '')}"
                if ref.get('page'):
                    content += f" pagina {ref['page']}"
                content += "\n"

        doc_id = f"expert_rule_{rule_id}"
        docs.append({
            "id": doc_id,
            "content": content,
            "metadata": {
                "source_type": "expert",
                "source_file": filename,
                "title": f"Expert regel: {title}",
                "rule_id": rule_id,
                "severity": severity,
                "affected_entities": ",".join(affected_entities),
                "related_codes": ",".join(related_codes),
            },
        })

        # Create separate documents for examples (for better retrieval)
        for i, example in enumerate(examples, 1):
            incorrect = example.get("incorrect", "")
            correct = example.get("correct", "")
            explanation = example.get("explanation", "")

            example_content = f"Voorbeeld bij regel {rule_id} ({title}):\n\n"
            example_content += f"FOUT: {incorrect}\n"
            example_content += f"CORRECT: {correct}\n"
            if explanation:
                example_content += f"\nUitleg: {explanation}\n"

            example_id = f"expert_example_{rule_id}_{i}"
            docs.append({
                "id": example_id,
                "content": example_content,
                "metadata": {
                    "source_type": "expert",
                    "source_file": filename,
                    "title": f"Voorbeeld: {title}",
                    "rule_id": rule_id,
                    "example_index": i,
                },
            })

        return docs

    def _process_faq(self, faq_item: dict, filename: str) -> Optional[dict]:
        """Process a single FAQ item."""
        question = faq_item.get("question", "")
        answer = faq_item.get("answer", "")
        related_rules = faq_item.get("related_rules", [])

        if not question or not answer:
            return None

        content = f"Vraag: {question}\n\n"
        content += f"Antwoord:\n{answer}\n"

        if related_rules:
            content += f"\nGerelateerde regels: {', '.join(related_rules)}"

        doc_id = f"expert_faq_{hashlib.md5(question.encode()).hexdigest()[:8]}"
        return {
            "id": doc_id,
            "content": content,
            "metadata": {
                "source_type": "expert",
                "source_file": filename,
                "title": f"FAQ: {question[:50]}...",
                "faq_question": question,
                "related_rules": ",".join(related_rules),
            },
        }

    def process_all(self) -> list[dict]:
        """
        Process all YAML files in the knowledge directory.

        Returns:
            Combined list of documents from all YAML files.
        """
        all_docs = []

        yaml_files = list(self.knowledge_dir.glob("*.yaml"))
        yaml_files.extend(self.knowledge_dir.glob("*.yml"))

        # Filter to only expert knowledge files
        expert_files = [f for f in yaml_files if "expert" in f.name.lower()]

        if not expert_files:
            # Try the default file
            return self.process()

        for filepath in expert_files:
            docs = self.process(filepath.name)
            all_docs.extend(docs)

        return all_docs
