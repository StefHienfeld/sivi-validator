"""
Embedding model wrapper using sentence-transformers.
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Model name for multilingual embeddings (supports Dutch)
DEFAULT_MODEL = "paraphrase-multilingual-mpnet-base-v2"


class EmbeddingModel:
    """Wrapper for sentence-transformers embedding model."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        """
        Initialize the embedding model.

        Args:
            model_name: Name of the sentence-transformers model to use.
        """
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy-load the model on first use."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Embedding model loaded successfully")
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        # paraphrase-multilingual-mpnet-base-v2 has 768 dimensions
        return 768

    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        logger.debug(f"Embedding {len(texts)} texts")
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """
        Generate embedding for a search query.

        This is the same as embed_text but named separately for clarity
        in retrieval context.

        Args:
            query: Query text to embed.

        Returns:
            Embedding vector.
        """
        return self.embed_text(query)


class ChromaEmbeddingFunction:
    """
    Adapter class to use our EmbeddingModel with ChromaDB.

    ChromaDB expects an embedding function with a __call__ method.
    """

    def __init__(self, embedding_model: Optional[EmbeddingModel] = None):
        """
        Initialize the ChromaDB embedding function.

        Args:
            embedding_model: Optional EmbeddingModel instance. Creates one if not provided.
        """
        self._embedding_model = embedding_model or EmbeddingModel()

    def __call__(self, input: list[str]) -> list[list[float]]:
        """
        Generate embeddings for ChromaDB.

        Args:
            input: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        return self._embedding_model.embed_texts(input)
