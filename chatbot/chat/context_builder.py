"""
Finding-aware context builder for chat responses.
"""

import logging
from typing import Optional

from ..models.schemas import FindingContext
from ..vectorstore.retriever import Retriever
from .prompts import FINDING_CONTEXT_TEMPLATE

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds context for chat responses based on retrieved documents and findings."""

    def __init__(self, retriever: Retriever):
        """
        Initialize the context builder.

        Args:
            retriever: Retriever instance for document retrieval.
        """
        self.retriever = retriever

    def build_context(
        self,
        query: str,
        finding: Optional[FindingContext] = None,
        max_tokens: int = 4000,
    ) -> tuple[str, list[dict]]:
        """
        Build context string for the chat LLM.

        Args:
            query: User's question.
            finding: Optional finding context.
            max_tokens: Maximum tokens for context.

        Returns:
            Tuple of (context_string, retrieved_documents).
        """
        # Retrieve relevant documents
        if finding:
            documents = self.retriever.retrieve_for_finding(finding)
        else:
            documents = self.retriever.retrieve(query, n_results=8)

        # Also search for query-specific documents
        query_docs = self.retriever.retrieve(query, n_results=5)

        # Merge and deduplicate
        seen_ids = {d["id"] for d in documents}
        for doc in query_docs:
            if doc["id"] not in seen_ids:
                documents.append(doc)
                seen_ids.add(doc["id"])

        # Sort by relevance score
        documents.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Limit to top results
        documents = documents[:10]

        # Format context
        context = self.retriever.format_context(documents, max_tokens)

        return context, documents

    def format_finding_context(self, finding: FindingContext) -> str:
        """
        Format finding information for inclusion in the prompt.

        Args:
            finding: The finding to format.

        Returns:
            Formatted finding context string.
        """
        return FINDING_CONTEXT_TEMPLATE.format(
            code=finding.code or "Onbekend",
            severity=finding.severity or "Onbekend",
            entiteit=finding.entiteit or "Onbekend",
            label=finding.label or "-",
            waarde=finding.waarde or "-",
            omschrijving=finding.omschrijving or "-",
            verwacht=finding.verwacht or "-",
        )

    def build_suggestion_context(self, finding: FindingContext) -> str:
        """
        Build context for generating question suggestions.

        Args:
            finding: The finding to generate suggestions for.

        Returns:
            Context string for suggestion generation.
        """
        # Retrieve documents specifically for this finding
        documents = self.retriever.retrieve_for_finding(finding, n_results=5)

        context_parts = []

        # Add finding details
        context_parts.append(f"Bevinding: {finding.code}")
        if finding.omschrijving:
            context_parts.append(f"Omschrijving: {finding.omschrijving}")
        if finding.entiteit:
            context_parts.append(f"Entiteit: {finding.entiteit}")

        # Add brief document context
        for doc in documents[:3]:
            meta = doc.get("metadata", {})
            title = meta.get("title", "Bron")
            content = doc.get("content", "")[:200]
            context_parts.append(f"\n[{title}]\n{content}...")

        return "\n".join(context_parts)

    def enrich_finding_context(
        self,
        finding: FindingContext,
    ) -> dict:
        """
        Enrich a finding with additional context from the knowledge base.

        Args:
            finding: The finding to enrich.

        Returns:
            Dictionary with enriched information.
        """
        enriched = {
            "finding": finding.model_dump(),
            "related_rules": [],
            "valid_codes": [],
            "handbook_refs": [],
        }

        # Search for related expert rules
        if finding.code:
            rule_docs = self.retriever.retrieve(
                f"regel {finding.code}",
                n_results=3,
                source_types=["expert"],
            )
            for doc in rule_docs:
                meta = doc.get("metadata", {})
                if meta.get("rule_id"):
                    enriched["related_rules"].append({
                        "id": meta["rule_id"],
                        "title": meta.get("title", ""),
                    })

        # Search for valid codes if it's a code-related error
        if finding.entiteit and finding.code in ["E1-002"]:
            code_docs = self.retriever.retrieve(
                f"geldige codes {finding.entiteit}",
                n_results=2,
                source_types=["xsd"],
            )
            for doc in code_docs:
                # Extract codes from content
                content = doc.get("content", "")
                if "Geldige" in content or "geldig" in content:
                    enriched["valid_codes"].append({
                        "source": doc.get("metadata", {}).get("title", "XSD"),
                        "excerpt": content[:300],
                    })

        return enriched
