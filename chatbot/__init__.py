"""
RAG Chatbot for SIVI AFD Validator

This module provides a conversational interface for asking questions about
validation findings and SIVI AFD documentation.
"""

# Imports are done lazily to avoid circular dependencies
# Use: from chatbot.chat.engine import ChatEngine

__all__ = ["ChatEngine", "VectorStore", "Retriever"]
