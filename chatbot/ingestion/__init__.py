"""
Ingestion processors for different document types.
"""

# Imports are done lazily to avoid circular dependencies
# Use: from chatbot.ingestion.pdf_processor import PDFProcessor

__all__ = ["PDFProcessor", "XSDProcessor", "CodelistProcessor", "ExpertProcessor"]
