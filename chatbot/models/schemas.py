"""
Pydantic models for the RAG chatbot API.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FindingContext(BaseModel):
    """Context about a specific validation finding."""
    code: str = Field(..., description="Finding code (e.g., E1-002)")
    severity: str = Field(..., description="Severity level (FOUT, WAARSCHUWING, INFO)")
    engine: int = Field(..., description="Engine number (1, 2, or 3)")
    regeltype: Optional[str] = Field(None, description="Rule type identifier")
    contract: Optional[str] = Field(None, description="Contract number")
    branche: Optional[str] = Field(None, description="Branch code")
    entiteit: Optional[str] = Field(None, description="Entity type (e.g., PV, CA)")
    label: Optional[str] = Field(None, description="Field name")
    waarde: Optional[str] = Field(None, description="Actual value found")
    omschrijving: Optional[str] = Field(None, description="Finding description")
    verwacht: Optional[str] = Field(None, description="Expected value/format")
    bron: Optional[str] = Field(None, description="Source reference")


class Source(BaseModel):
    """A source reference for an answer."""
    document_type: str = Field(..., description="Type: pdf, xsd, codelist, expert")
    title: str = Field(..., description="Source title/name")
    section: Optional[str] = Field(None, description="Section identifier")
    page: Optional[int] = Field(None, description="Page number (for PDFs)")
    relevance_score: float = Field(..., description="Relevance score 0-1")


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    sources: Optional[list[Source]] = Field(None, description="Sources for this message")
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    message: str = Field(..., min_length=1, description="User's question")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    finding_context: Optional[FindingContext] = Field(
        None, description="Context from a specific finding"
    )
    validation_file: Optional[str] = Field(
        None, description="Name of the validated file"
    )


class ChatResponse(BaseModel):
    """Response from the chat API."""
    conversation_id: str = Field(..., description="Conversation ID")
    message: ChatMessage = Field(..., description="Assistant's response")
    suggested_questions: list[str] = Field(
        default_factory=list, description="Follow-up question suggestions"
    )


class SuggestRequest(BaseModel):
    """Request for suggested questions about a finding."""
    finding: FindingContext = Field(..., description="The finding to get suggestions for")


class SuggestResponse(BaseModel):
    """Response with suggested questions."""
    questions: list[str] = Field(..., description="Suggested questions")


class KnowledgeStatus(BaseModel):
    """Status of the knowledge base."""
    initialized: bool = Field(..., description="Whether knowledge base is ready")
    total_documents: int = Field(..., description="Total documents in store")
    documents_by_type: dict[str, int] = Field(
        ..., description="Document counts by source type"
    )
    last_rebuild: Optional[datetime] = Field(
        None, description="Timestamp of last rebuild"
    )
    embedding_model: str = Field(..., description="Name of embedding model")


class Document(BaseModel):
    """A document chunk for the vector store."""
    id: str = Field(..., description="Unique document ID")
    content: str = Field(..., description="Document text content")
    metadata: dict = Field(default_factory=dict, description="Document metadata")

    class Config:
        extra = "allow"


class ConversationHistory(BaseModel):
    """Full conversation history."""
    id: str = Field(..., description="Conversation ID")
    validation_file: Optional[str] = Field(None, description="Associated validation file")
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
