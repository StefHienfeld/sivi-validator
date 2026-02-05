"""
Retrieval logic for finding relevant documents.
"""

import logging
from typing import Optional

from ..models.schemas import FindingContext, Source

logger = logging.getLogger(__name__)


class Retriever:
    """Retriever for finding relevant documents from the vector store."""

    def __init__(self, vector_store):
        """
        Initialize the retriever.

        Args:
            vector_store: VectorStore instance to query.
        """
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        n_results: int = 5,
        source_types: Optional[list[str]] = None,
        min_score: float = 0.3,
    ) -> list[dict]:
        """
        Retrieve relevant documents for a query.

        Args:
            query: Search query.
            n_results: Maximum number of results.
            source_types: Optional list of source types to filter by.
            min_score: Minimum relevance score (0-1).

        Returns:
            List of relevant documents with scores.
        """
        # Build metadata filter if source types specified
        where = None
        if source_types:
            if len(source_types) == 1:
                where = {"source_type": source_types[0]}
            else:
                where = {"source_type": {"$in": source_types}}

        # Query the vector store
        results = self.vector_store.query(
            query_text=query,
            n_results=n_results,
            where=where,
        )

        # Filter by minimum score
        filtered = [r for r in results if r.get("score", 0) >= min_score]

        logger.debug(f"Retrieved {len(filtered)} documents for query: {query[:50]}...")
        return filtered

    def retrieve_for_finding(
        self,
        finding: FindingContext,
        n_results: int = 8,
    ) -> list[dict]:
        """
        Retrieve documents relevant to a specific validation finding.

        This uses finding metadata to construct targeted queries.

        Args:
            finding: The finding context.
            n_results: Maximum results per query.

        Returns:
            Deduplicated list of relevant documents.
        """
        all_results = []
        seen_ids = set()

        # Build queries based on finding context
        queries = self._build_finding_queries(finding)

        for query, source_filter in queries:
            results = self.retrieve(
                query=query,
                n_results=n_results // len(queries) + 1,
                source_types=source_filter,
                min_score=0.25,
            )

            for doc in results:
                if doc["id"] not in seen_ids:
                    seen_ids.add(doc["id"])
                    all_results.append(doc)

        # Sort by score and limit
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return all_results[:n_results]

    def _build_finding_queries(
        self,
        finding: FindingContext,
    ) -> list[tuple[str, Optional[list[str]]]]:
        """
        Build targeted queries based on finding context.

        Returns list of (query, source_types) tuples.
        """
        queries = []

        # Query 1: Direct description search
        if finding.omschrijving:
            queries.append((finding.omschrijving, None))

        # Query 2: Entity-specific query
        if finding.entiteit:
            entity_query = f"entiteit {finding.entiteit}"
            if finding.label:
                entity_query += f" {finding.label}"
            if finding.code:
                entity_query += f" {finding.code}"
            queries.append((entity_query, ["xsd", "expert"]))

        # Query 3: Code-specific query (for coverage codes, branch codes, etc.)
        if finding.waarde:
            if finding.entiteit:
                code_query = f"{finding.entiteit} code {finding.waarde}"
            else:
                code_query = f"code {finding.waarde}"
            if finding.verwacht:
                code_query += f" {finding.verwacht}"
            queries.append((code_query, ["xsd", "codelist"]))

        # Query 4: Rule type query
        if finding.regeltype:
            queries.append((f"regel {finding.regeltype}", ["expert"]))

        # Query 5: Branch-specific query
        if finding.branche:
            branch_query = f"branche {finding.branche}"
            if finding.entiteit:
                branch_query += f" {finding.entiteit}"
            queries.append((branch_query, ["codelist", "pdf"]))

        # Ensure at least one query
        if not queries:
            queries.append((f"{finding.code} {finding.severity}", None))

        return queries

    def build_sources(self, documents: list[dict]) -> list[Source]:
        """
        Convert retrieved documents to Source objects for API response.

        Args:
            documents: List of retrieved documents.

        Returns:
            List of Source objects.
        """
        sources = []
        for doc in documents:
            meta = doc.get("metadata", {})

            source = Source(
                document_type=meta.get("source_type", "unknown"),
                title=meta.get("title", meta.get("source_file", "Unknown")),
                section=meta.get("section"),
                page=meta.get("page"),
                relevance_score=doc.get("score", 0),
            )
            sources.append(source)

        return sources

    def format_context(
        self,
        documents: list[dict],
        max_tokens: int = 4000,
    ) -> str:
        """
        Format retrieved documents as context for the LLM.

        Args:
            documents: List of retrieved documents.
            max_tokens: Approximate max tokens for context.

        Returns:
            Formatted context string.
        """
        if not documents:
            return ""

        context_parts = []
        estimated_tokens = 0

        for i, doc in enumerate(documents, 1):
            meta = doc.get("metadata", {})
            content = doc.get("content", "")

            # Format source header
            source_type = meta.get("source_type", "document")
            title = meta.get("title", meta.get("source_file", "Bron"))

            header = f"[Bron {i}: {title}"
            if meta.get("section"):
                header += f", sectie {meta['section']}"
            if meta.get("page"):
                header += f", pagina {meta['page']}"
            header += f" ({source_type})]"

            part = f"{header}\n{content}\n"

            # Rough token estimation (4 chars per token)
            part_tokens = len(part) // 4

            if estimated_tokens + part_tokens > max_tokens:
                # Truncate content if needed
                remaining_chars = (max_tokens - estimated_tokens) * 4
                if remaining_chars > 200:
                    truncated_content = content[: remaining_chars - len(header) - 50] + "..."
                    part = f"{header}\n{truncated_content}\n"
                    context_parts.append(part)
                break

            context_parts.append(part)
            estimated_tokens += part_tokens

        return "\n".join(context_parts)
