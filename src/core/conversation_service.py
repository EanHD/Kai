"""Conversation service for session management and persistence."""

import logging
from typing import Any

from src.models.conversation import ConversationSession
from src.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


class ConversationService:
    """Manages conversation sessions with persistence."""

    def __init__(self, storage: SQLiteStore):
        """Initialize conversation service.

        Args:
            storage: SQLite storage instance
        """
        self.storage = storage

    def create_conversation(
        self, user_id: str, cost_limit: float = 1.0, source: str = "cli"
    ) -> ConversationSession:
        """Create a new conversation session.

        Args:
            user_id: User ID for the conversation
            cost_limit: Cost limit for the session
            source: Request source - "cli" or "api"

        Returns:
            New ConversationSession
        """
        session = ConversationSession(user_id=user_id, cost_limit=cost_limit, request_source=source)

        # Persist to database
        self.storage.create_conversation(
            session_id=session.session_id,
            user_id=user_id,
            cost_limit=cost_limit,
        )

        logger.info(
            f"Created conversation {session.session_id} for user {user_id} (source={source})"
        )
        return session

    def get_conversation(self, session_id: str) -> ConversationSession | None:
        """Retrieve conversation session.

        Args:
            session_id: Session ID to retrieve

        Returns:
            ConversationSession if found, None otherwise
        """
        data = self.storage.get_conversation(session_id)
        if not data:
            return None

        # Reconstruct session from storage
        from datetime import datetime

        session = ConversationSession(
            session_id=data["session_id"],
            user_id=data["user_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            ended_at=datetime.fromisoformat(data["ended_at"]) if data["ended_at"] else None,
            total_cost=data["total_cost"],
            cost_limit=data["cost_limit"],
            message_count=data["message_count"],
        )

        # Load context from recent messages
        messages = self.storage.get_messages(session_id, limit=10)
        for msg in reversed(messages):  # Oldest first
            session.add_to_context(
                {
                    "role": msg["role"],
                    "content": msg["content"],
                    "token_count": msg.get("token_count", 0),
                }
            )

        return session

    def end_conversation(self, session_id: str) -> None:
        """End a conversation session.

        Args:
            session_id: Session ID to end
        """
        self.storage.end_conversation(session_id)
        logger.info(f"Ended conversation {session_id}")

    def update_cost(self, session_id: str, cost_increment: float) -> None:
        """Update conversation cost.

        Args:
            session_id: Session ID
            cost_increment: Cost to add
        """
        self.storage.update_conversation_cost(session_id, cost_increment)

    def save_message(self, message_data: dict[str, Any]) -> None:
        """Save a message to conversation.

        Args:
            message_data: Message dict with all fields
        """
        self.storage.save_message(message_data)

    def get_messages(self, session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Get messages for a conversation.

        Args:
            session_id: Session ID
            limit: Maximum number of messages to return

        Returns:
            List of message dicts
        """
        return self.storage.get_messages(session_id, limit)
    
    def prune_old_conversations(self, days_old: int = 30) -> dict[str, int]:
        """Prune conversations older than specified days.
        
        Args:
            days_old: Delete conversations older than this many days
            
        Returns:
            Dict with counts of deleted conversations and messages
        """
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        try:
            # Get old conversations
            old_sessions = self.storage.get_old_conversations(cutoff_date.isoformat())
            
            deleted_conversations = 0
            deleted_messages = 0
            
            for session in old_sessions:
                session_id = session.get("session_id")
                
                # Delete messages first
                msg_count = self.storage.delete_messages(session_id)
                deleted_messages += msg_count
                
                # Delete conversation
                self.storage.delete_conversation(session_id)
                deleted_conversations += 1
            
            logger.info(
                f"Pruned {deleted_conversations} conversations ({deleted_messages} messages) "
                f"older than {days_old} days"
            )
            
            return {
                "conversations_deleted": deleted_conversations,
                "messages_deleted": deleted_messages,
                "cutoff_date": cutoff_date.isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to prune old conversations: {e}")
            return {
                "conversations_deleted": 0,
                "messages_deleted": 0,
                "error": str(e),
            }
