"""
Chat engine orchestration for the RAG chatbot.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..history import ChatHistory
from ..models.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    FindingContext,
    KnowledgeStatus,
    Source,
    SuggestResponse,
)
from ..vectorstore.retriever import Retriever
from ..vectorstore.store import VectorStore
from .context_builder import ContextBuilder
from .prompts import CHAT_SYSTEM_PROMPT, CHAT_USER_TEMPLATE, SUGGESTION_PROMPT

logger = logging.getLogger(__name__)


class ChatEngine:
    """Main chat engine orchestrating RAG responses."""

    def __init__(
        self,
        sivi_dir: Path,
        data_dir: Optional[Path] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the chat engine.

        Args:
            sivi_dir: Path to SIVI directory with XSD and codelist files.
            data_dir: Path to data directory for vector store and history.
            api_key: Optional Anthropic API key (uses env var if not provided).
        """
        self.sivi_dir = sivi_dir
        self.data_dir = data_dir or Path("data")
        self.api_key = api_key

        # Initialize components lazily
        self._vector_store: Optional[VectorStore] = None
        self._retriever: Optional[Retriever] = None
        self._context_builder: Optional[ContextBuilder] = None
        self._history: Optional[ChatHistory] = None
        self._client = None

    @property
    def vector_store(self) -> VectorStore:
        """Get the vector store instance."""
        if self._vector_store is None:
            chroma_dir = self.data_dir / "chroma"
            self._vector_store = VectorStore(persist_directory=chroma_dir)
        return self._vector_store

    @property
    def retriever(self) -> Retriever:
        """Get the retriever instance."""
        if self._retriever is None:
            self._retriever = Retriever(self.vector_store)
        return self._retriever

    @property
    def context_builder(self) -> ContextBuilder:
        """Get the context builder instance."""
        if self._context_builder is None:
            self._context_builder = ContextBuilder(self.retriever)
        return self._context_builder

    @property
    def history(self) -> ChatHistory:
        """Get the chat history instance."""
        if self._history is None:
            db_path = self.data_dir / "chat_history.db"
            self._history = ChatHistory(db_path)
        return self._history

    @property
    def client(self):
        """Get the Anthropic client."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Process a chat request and return a response.

        Args:
            request: The chat request.

        Returns:
            Chat response with answer and sources.
        """
        # Get or create conversation
        if request.conversation_id:
            conversation_id = request.conversation_id
        else:
            conversation_id = await self.history.create_conversation(
                validation_file=request.validation_file
            )

        # Build context
        context, documents = self.context_builder.build_context(
            query=request.message,
            finding=request.finding_context,
        )

        # Format finding context if present
        finding_text = ""
        if request.finding_context:
            finding_text = self.context_builder.format_finding_context(
                request.finding_context
            )

        # Build user prompt
        user_prompt = CHAT_USER_TEMPLATE.format(
            context=context,
            finding_context=finding_text,
            question=request.message,
        )

        # Get conversation history for context
        history_messages = await self.history.get_conversation_messages(
            conversation_id, limit=6
        )

        # Build messages for Claude
        messages = []
        for msg in history_messages:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_prompt,
        })

        # Call Claude API
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                system=CHAT_SYSTEM_PROMPT,
                messages=messages,
            )
            answer = response.content[0].text
        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            answer = f"Sorry, er is een fout opgetreden bij het genereren van het antwoord: {str(e)}"

        # Build source list
        sources = self.retriever.build_sources(documents)

        # Save messages to history
        finding_dict = request.finding_context.model_dump() if request.finding_context else None
        await self.history.add_message(
            conversation_id=conversation_id,
            role="user",
            content=request.message,
            finding_context=finding_dict,
        )

        source_dicts = [s.model_dump() for s in sources]
        await self.history.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            sources=source_dicts,
        )

        # Generate suggested follow-up questions
        suggestions = await self._generate_suggestions(
            question=request.message,
            answer=answer,
            finding=request.finding_context,
        )

        # Build response
        message = ChatMessage(
            role="assistant",
            content=answer,
            sources=sources,
            timestamp=datetime.now(),
        )

        return ChatResponse(
            conversation_id=conversation_id,
            message=message,
            suggested_questions=suggestions,
        )

    async def suggest_questions(self, finding: FindingContext) -> SuggestResponse:
        """
        Generate suggested questions for a finding.

        Args:
            finding: The finding to generate suggestions for.

        Returns:
            List of suggested questions.
        """
        prompt = SUGGESTION_PROMPT.format(
            code=finding.code or "Onbekend",
            severity=finding.severity or "Onbekend",
            entiteit=finding.entiteit or "Onbekend",
            omschrijving=finding.omschrijving or "Geen omschrijving",
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text

            # Parse questions (one per line)
            questions = [q.strip() for q in text.split("\n") if q.strip()]
            questions = questions[:4]  # Limit to 4

        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            # Fallback suggestions
            questions = [
                f"Waarom krijg ik deze {finding.code} fout?",
                f"Hoe los ik deze bevinding op?",
                f"Welke waarden zijn geldig voor {finding.entiteit}?",
            ]

        return SuggestResponse(questions=questions)

    async def _generate_suggestions(
        self,
        question: str,
        answer: str,
        finding: Optional[FindingContext] = None,
    ) -> list[str]:
        """Generate follow-up question suggestions."""
        if finding:
            response = await self.suggest_questions(finding)
            return response.questions[:3]

        # Generic follow-ups based on answer
        return [
            "Kun je dit verder toelichten?",
            "Zijn er nog andere oorzaken mogelijk?",
            "Hoe voorkom ik dit in de toekomst?",
        ]

    async def rebuild_knowledge_base(self) -> dict:
        """
        Rebuild the knowledge base from all sources.

        Returns:
            Statistics about the rebuild.
        """
        from ..ingestion import (
            CodelistProcessor,
            ExpertProcessor,
            PDFProcessor,
            XSDProcessor,
        )

        logger.info("Starting knowledge base rebuild...")

        # Clear existing data
        self.vector_store.delete_all()

        stats = {
            "pdf": 0,
            "xsd": 0,
            "codelist": 0,
            "expert": 0,
            "total": 0,
        }

        # Process XSD files
        logger.info("Processing XSD files...")
        xsd_processor = XSDProcessor(self.sivi_dir)
        xsd_docs = xsd_processor.process_all()
        if xsd_docs:
            self.vector_store.add_documents(xsd_docs)
            stats["xsd"] = len(xsd_docs)

        # Process codelist JSON files
        logger.info("Processing codelist files...")
        codelist_processor = CodelistProcessor(self.sivi_dir)
        codelist_docs = codelist_processor.process_all()
        if codelist_docs:
            self.vector_store.add_documents(codelist_docs)
            stats["codelist"] = len(codelist_docs)

        # Process expert knowledge
        logger.info("Processing expert knowledge...")
        knowledge_dir = self.sivi_dir.parent / "sivi-validator" / "knowledge"
        if knowledge_dir.exists():
            expert_processor = ExpertProcessor(knowledge_dir)
            expert_docs = expert_processor.process_all()
            if expert_docs:
                self.vector_store.add_documents(expert_docs)
                stats["expert"] = len(expert_docs)

        # Process PDF documents (if any in data directory)
        logger.info("Processing PDF documents...")
        pdf_dir = self.data_dir / "pdfs"
        if pdf_dir.exists():
            pdf_processor = PDFProcessor()
            pdf_docs = pdf_processor.process_directory(pdf_dir)
            if pdf_docs:
                self.vector_store.add_documents(pdf_docs)
                stats["pdf"] = len(pdf_docs)

        # Also check sivi directory for PDFs
        sivi_pdf_docs = []
        for pdf_path in self.sivi_dir.glob("*.pdf"):
            pdf_processor = PDFProcessor()
            pdf_docs = pdf_processor.process(pdf_path)
            sivi_pdf_docs.extend(pdf_docs)

        if sivi_pdf_docs:
            self.vector_store.add_documents(sivi_pdf_docs)
            stats["pdf"] += len(sivi_pdf_docs)

        stats["total"] = sum(stats.values()) - stats["total"]
        self.vector_store.set_rebuild_timestamp()

        logger.info(f"Knowledge base rebuild complete: {stats}")
        return stats

    def get_knowledge_status(self) -> KnowledgeStatus:
        """
        Get the current status of the knowledge base.

        Returns:
            Knowledge base status.
        """
        store_stats = self.vector_store.get_stats()

        return KnowledgeStatus(
            initialized=store_stats["total_documents"] > 0,
            total_documents=store_stats["total_documents"],
            documents_by_type=store_stats["documents_by_type"],
            last_rebuild=store_stats.get("last_rebuild"),
            embedding_model="paraphrase-multilingual-mpnet-base-v2",
        )
