"""
Chat history database using SQLite.
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path("data/chat_history.db")


class ChatHistory:
    """Async SQLite database for storing chat conversations."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the chat history database.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the database schema."""
        if self._initialized:
            return

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(str(self.db_path)) as db:
            # Create conversations table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    validation_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create messages table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources JSON,
                    finding_context JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)

            # Create indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id)
            """)

            await db.commit()

        self._initialized = True
        logger.info(f"Chat history database initialized at {self.db_path}")

    async def create_conversation(
        self,
        validation_file: Optional[str] = None,
    ) -> str:
        """
        Create a new conversation.

        Args:
            validation_file: Optional name of the validated file.

        Returns:
            Conversation ID.
        """
        await self.initialize()

        conversation_id = str(uuid.uuid4())

        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """
                INSERT INTO conversations (id, validation_file)
                VALUES (?, ?)
                """,
                (conversation_id, validation_file),
            )
            await db.commit()

        logger.debug(f"Created conversation: {conversation_id}")
        return conversation_id

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        sources: Optional[list] = None,
        finding_context: Optional[dict] = None,
    ) -> int:
        """
        Add a message to a conversation.

        Args:
            conversation_id: Conversation ID.
            role: Message role ('user' or 'assistant').
            content: Message content.
            sources: Optional list of source references.
            finding_context: Optional finding context dict.

        Returns:
            Message ID.
        """
        await self.initialize()

        sources_json = json.dumps(sources) if sources else None
        finding_json = json.dumps(finding_context) if finding_context else None

        async with aiosqlite.connect(str(self.db_path)) as db:
            cursor = await db.execute(
                """
                INSERT INTO messages (conversation_id, role, content, sources, finding_context)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, role, content, sources_json, finding_json),
            )
            message_id = cursor.lastrowid

            # Update conversation timestamp
            await db.execute(
                """
                UPDATE conversations SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (conversation_id,),
            )

            await db.commit()

        logger.debug(f"Added message {message_id} to conversation {conversation_id}")
        return message_id

    async def get_conversation(self, conversation_id: str) -> Optional[dict]:
        """
        Get a conversation with all its messages.

        Args:
            conversation_id: Conversation ID.

        Returns:
            Conversation dict with messages, or None if not found.
        """
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row

            # Get conversation
            cursor = await db.execute(
                """
                SELECT id, validation_file, created_at, updated_at
                FROM conversations WHERE id = ?
                """,
                (conversation_id,),
            )
            row = await cursor.fetchone()

            if not row:
                return None

            conversation = {
                "id": row["id"],
                "validation_file": row["validation_file"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "messages": [],
            }

            # Get messages
            cursor = await db.execute(
                """
                SELECT id, role, content, sources, finding_context, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            )

            async for msg_row in cursor:
                message = {
                    "id": msg_row["id"],
                    "role": msg_row["role"],
                    "content": msg_row["content"],
                    "sources": json.loads(msg_row["sources"]) if msg_row["sources"] else None,
                    "finding_context": json.loads(msg_row["finding_context"]) if msg_row["finding_context"] else None,
                    "created_at": msg_row["created_at"],
                }
                conversation["messages"].append(message)

        return conversation

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get recent messages from a conversation.

        Args:
            conversation_id: Conversation ID.
            limit: Maximum number of messages.

        Returns:
            List of message dicts.
        """
        await self.initialize()

        messages = []

        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """
                SELECT role, content, sources, finding_context, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            )

            async for row in cursor:
                message = {
                    "role": row["role"],
                    "content": row["content"],
                    "sources": json.loads(row["sources"]) if row["sources"] else None,
                    "created_at": row["created_at"],
                }
                messages.append(message)

        # Reverse to get chronological order
        messages.reverse()
        return messages

    async def list_conversations(
        self,
        limit: int = 20,
        validation_file: Optional[str] = None,
    ) -> list[dict]:
        """
        List recent conversations.

        Args:
            limit: Maximum number of conversations.
            validation_file: Optional filter by validation file.

        Returns:
            List of conversation summaries.
        """
        await self.initialize()

        conversations = []

        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row

            if validation_file:
                cursor = await db.execute(
                    """
                    SELECT c.id, c.validation_file, c.created_at, c.updated_at,
                           COUNT(m.id) as message_count
                    FROM conversations c
                    LEFT JOIN messages m ON c.id = m.conversation_id
                    WHERE c.validation_file = ?
                    GROUP BY c.id
                    ORDER BY c.updated_at DESC
                    LIMIT ?
                    """,
                    (validation_file, limit),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT c.id, c.validation_file, c.created_at, c.updated_at,
                           COUNT(m.id) as message_count
                    FROM conversations c
                    LEFT JOIN messages m ON c.id = m.conversation_id
                    GROUP BY c.id
                    ORDER BY c.updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            async for row in cursor:
                conversations.append({
                    "id": row["id"],
                    "validation_file": row["validation_file"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "message_count": row["message_count"],
                })

        return conversations

    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation and all its messages.

        Args:
            conversation_id: Conversation ID.

        Returns:
            True if deleted, False if not found.
        """
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            # Delete messages first
            await db.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            )

            # Delete conversation
            cursor = await db.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation_id,),
            )

            await db.commit()

            return cursor.rowcount > 0

    async def get_stats(self) -> dict:
        """
        Get database statistics.

        Returns:
            Dict with stats.
        """
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM conversations")
            row = await cursor.fetchone()
            conversation_count = row[0]

            cursor = await db.execute("SELECT COUNT(*) FROM messages")
            row = await cursor.fetchone()
            message_count = row[0]

        return {
            "conversation_count": conversation_count,
            "message_count": message_count,
            "database_path": str(self.db_path),
        }
