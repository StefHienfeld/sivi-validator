"""
Codelist processor for indexing JSON codelist files.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CodelistProcessor:
    """Processor for converting JSON codelists to searchable documents."""

    def __init__(self, sivi_dir: Path):
        """
        Initialize the codelist processor.

        Args:
            sivi_dir: Path to the SIVI directory containing JSON files.
        """
        self.sivi_dir = sivi_dir

    def process_all(self) -> list[dict]:
        """
        Process all JSON codelist files.

        Returns:
            List of document chunks.
        """
        all_docs = []

        # Find hierarchy and codelist JSON files
        json_files = list(self.sivi_dir.glob("*_hierarchy_*.json"))
        json_files.extend(self.sivi_dir.glob("*_codelist_*.json"))

        logger.info(f"Found {len(json_files)} JSON codelist files")

        for filepath in json_files:
            logger.info(f"Processing JSON: {filepath.name}")
            if "hierarchy" in filepath.name:
                docs = self._process_hierarchy(filepath)
            else:
                docs = self._process_codelist(filepath)
            all_docs.extend(docs)
            logger.info(f"Created {len(docs)} documents from {filepath.name}")

        return all_docs

    def _process_hierarchy(self, filepath: Path) -> list[dict]:
        """Process a hierarchy JSON file."""
        docs = []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
            return docs

        common = data.get("commonFunctional", {})
        table_name = common.get("tableName", "")
        table_desc = common.get("tableDescription", "")

        # Create overview document
        afs_table = data.get("afsTable", {})
        code_values = afs_table.get("codeValues", [])

        overview_content = f"Codelijst: {table_name}\n"
        overview_content += f"Beschrijving: {table_desc}\n\n"
        overview_content += f"Dit is een hierarchische codelijst met {len(code_values)} hoofdcategorieën.\n"

        docs.append({
            "id": f"codelist_hierarchy_{hashlib.md5(table_name.encode()).hexdigest()[:8]}",
            "content": overview_content,
            "metadata": {
                "source_type": "codelist",
                "source_file": filepath.name,
                "title": table_name,
                "codelist_type": "hierarchy",
            },
        })

        # Process each branch code recursively
        for code_data in code_values:
            branch_docs = self._process_branch_code(code_data, filepath.name, table_name, [])
            docs.extend(branch_docs)

        return docs

    def _process_branch_code(
        self,
        code_data: dict,
        filename: str,
        table_name: str,
        path: list[str],
    ) -> list[dict]:
        """Process a single branch code and its children."""
        docs = []

        value = code_data.get("value", "")
        description = code_data.get("description", "")
        short_desc = code_data.get("shortDescription", "")
        node_desc = code_data.get("nodeDescription", "")

        if not value:
            return docs

        # Build path for this node
        current_path = path + [value]
        path_str = " > ".join(current_path)

        # Create document for this branch
        content = f"Branchecode: {value}\n"
        content += f"Beschrijving: {description}\n"
        if short_desc and short_desc != description:
            content += f"Korte beschrijving: {short_desc}\n"
        if node_desc:
            content += f"Node beschrijving: {node_desc}\n"
        content += f"\nHierarchie pad: {path_str}\n"

        # Add information about parent branch
        if path:
            content += f"Onderdeel van: {path[-1]} ({' > '.join(path)})\n"

        # Add children summary
        children = code_data.get("code", [])
        if children:
            child_codes = [c.get("value", "") for c in children if c.get("value")]
            content += f"\nSubbranches ({len(children)}): {', '.join(child_codes[:10])}"
            if len(child_codes) > 10:
                content += f"... (en {len(child_codes) - 10} meer)"

        doc_id = f"branch_{value}_{hashlib.md5(value.encode()).hexdigest()[:8]}"
        docs.append({
            "id": doc_id,
            "content": content,
            "metadata": {
                "source_type": "codelist",
                "source_file": filename,
                "title": f"Branche {value}: {short_desc or description[:50]}",
                "codelist_type": "branch",
                "branch_code": value,
                "parent_branch": path[-1] if path else None,
            },
        })

        # Process children recursively
        for child_data in children:
            child_docs = self._process_branch_code(child_data, filename, table_name, current_path)
            docs.extend(child_docs)

        return docs

    def _process_codelist(self, filepath: Path) -> list[dict]:
        """Process a flat codelist JSON file."""
        docs = []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
            return docs

        common = data.get("commonFunctional", {})
        table_name = common.get("tableName", "")
        table_desc = common.get("tableDescription", "")

        afs_table = data.get("afsTable", {})
        code_values = afs_table.get("codeValues", [])

        # Create overview document
        overview_content = f"Codelijst: {table_name}\n"
        overview_content += f"Beschrijving: {table_desc}\n\n"
        overview_content += f"Aantal codes: {len(code_values)}\n\n"

        # Add sample of codes
        sample_codes = []
        for code_data in code_values[:20]:
            value = code_data.get("value", "")
            desc = code_data.get("description", "")
            if value:
                sample_codes.append(f"- {value}: {desc}")

        if sample_codes:
            overview_content += "Voorbeeld codes:\n" + "\n".join(sample_codes)
            if len(code_values) > 20:
                overview_content += f"\n... en {len(code_values) - 20} meer codes"

        docs.append({
            "id": f"codelist_flat_{hashlib.md5(table_name.encode()).hexdigest()[:8]}",
            "content": overview_content,
            "metadata": {
                "source_type": "codelist",
                "source_file": filepath.name,
                "title": table_name,
                "codelist_type": "flat",
                "code_count": len(code_values),
            },
        })

        # Create documents for individual codes (batch them for efficiency)
        batch_size = 10
        for i in range(0, len(code_values), batch_size):
            batch = code_values[i : i + batch_size]

            batch_content = f"Codes uit codelijst {table_name}:\n\n"
            for code_data in batch:
                value = code_data.get("value", "")
                desc = code_data.get("description", "")
                short_desc = code_data.get("shortDescription", "")
                if value:
                    batch_content += f"Code {value}: {desc}"
                    if short_desc and short_desc != desc:
                        batch_content += f" ({short_desc})"
                    batch_content += "\n"

            batch_id = f"codelist_batch_{table_name}_{i}_{hashlib.md5(batch_content.encode()).hexdigest()[:8]}"
            docs.append({
                "id": batch_id,
                "content": batch_content,
                "metadata": {
                    "source_type": "codelist",
                    "source_file": filepath.name,
                    "title": f"{table_name} codes ({i+1}-{min(i+batch_size, len(code_values))})",
                    "codelist_type": "codes_batch",
                },
            })

        return docs
