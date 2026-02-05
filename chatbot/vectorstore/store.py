"""
ChromaDB vector store wrapper for document storage and retrieval.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Collection name for SIVI knowledge base
COLLECTION_NAME = "sivi_knowledge"


class VectorStore:
    """ChromaDB-based vector store for SIVI documentation."""

    def __init__(
        self,
        persist_directory: Optional[Path] = None,
        collection_name: str = COLLECTION_NAME,
    ):
        """
        Initialize the vector store.

        Args:
            persist_directory: Directory for persistent storage. If None, uses in-memory.
            collection_name: Name of the ChromaDB collection.
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._embedding_function = None
        self._last_rebuild: Optional[datetime] = None

    @property
    def client(self):
        """Lazy-load ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings

                if self.persist_directory:
                    self.persist_directory.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Initializing persistent ChromaDB at {self.persist_directory}")
                    self._client = chromadb.PersistentClient(
                        path=str(self.persist_directory),
                        settings=Settings(anonymized_telemetry=False),
                    )
                else:
                    logger.info("Initializing in-memory ChromaDB")
                    self._client = chromadb.Client(
                        settings=Settings(anonymized_telemetry=False)
                    )
            except ImportError:
                raise ImportError(
                    "chromadb is required. Install with: pip install chromadb"
                )
        return self._client

    @property
    def embedding_function(self):
        """Get the embedding function for ChromaDB."""
        if self._embedding_function is None:
            from .embeddings import ChromaEmbeddingFunction
            self._embedding_function = ChromaEmbeddingFunction()
        return self._embedding_function

    @property
    def collection(self):
        """Get or create the collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"description": "SIVI AFD knowledge base"},
            )
            logger.info(f"Collection '{self.collection_name}' ready with {self._collection.count()} documents")
        return self._collection

    def add_documents(
        self,
        documents: list[dict],
        batch_size: int = 100,
    ) -> int:
        """
        Add documents to the vector store.

        Args:
            documents: List of dicts with 'id', 'content', and 'metadata' keys.
            batch_size: Number of documents to add per batch.

        Returns:
            Number of documents added.
        """
        if not documents:
            return 0

        total_added = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]

            ids = [doc["id"] for doc in batch]
            contents = [doc["content"] for doc in batch]
            metadatas = [doc.get("metadata", {}) for doc in batch]

            # Ensure all metadata values are primitive types
            cleaned_metadatas = []
            for meta in metadatas:
                cleaned = {}
                for k, v in meta.items():
                    if isinstance(v, (str, int, float, bool)):
                        cleaned[k] = v
                    elif v is None:
                        cleaned[k] = ""
                    else:
                        cleaned[k] = str(v)
                cleaned_metadatas.append(cleaned)

            try:
                self.collection.add(
                    ids=ids,
                    documents=contents,
                    metadatas=cleaned_metadatas,
                )
                total_added += len(batch)
                logger.debug(f"Added batch of {len(batch)} documents ({total_added} total)")
            except Exception as e:
                logger.error(f"Error adding batch: {e}")
                raise

        logger.info(f"Added {total_added} documents to collection")
        return total_added

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[dict] = None,
        where_document: Optional[dict] = None,
    ) -> list[dict]:
        """
        Query the vector store for relevant documents.

        Args:
            query_text: Query text to search for.
            n_results: Maximum number of results to return.
            where: Optional metadata filter.
            where_document: Optional document content filter.

        Returns:
            List of matching documents with scores.
        """
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"Query error: {e}")
            return []

        # Transform results into list of documents
        documents = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                doc = {
                    "id": doc_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 1.0,
                }
                # Convert distance to similarity score (ChromaDB uses L2 distance)
                # Lower distance = more similar
                doc["score"] = 1 / (1 + doc["distance"])
                documents.append(doc)

        return documents

    def delete_all(self) -> None:
        """Delete all documents from the collection."""
        # Delete and recreate the collection
        try:
            self.client.delete_collection(self.collection_name)
            self._collection = None
            logger.info(f"Deleted collection '{self.collection_name}'")
        except Exception as e:
            logger.warning(f"Could not delete collection: {e}")

    def get_stats(self) -> dict:
        """
        Get statistics about the vector store.

        Returns:
            Dict with collection statistics.
        """
        count = self.collection.count()

        # Get document type distribution
        type_counts = {}
        if count > 0:
            # Sample metadata to get types
            results = self.collection.get(
                include=["metadatas"],
                limit=count,
            )
            if results and results["metadatas"]:
                for meta in results["metadatas"]:
                    doc_type = meta.get("source_type", "unknown")
                    type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

        return {
            "total_documents": count,
            "documents_by_type": type_counts,
            "collection_name": self.collection_name,
            "last_rebuild": self._last_rebuild,
        }

    def set_rebuild_timestamp(self) -> None:
        """Set the timestamp for the last rebuild."""
        self._last_rebuild = datetime.now()

    def document_exists(self, doc_id: str) -> bool:
        """Check if a document exists in the store."""
        try:
            result = self.collection.get(ids=[doc_id])
            return bool(result and result["ids"])
        except Exception:
            return False
