"""Conversation service for session management and persistence."""

from typing import Optional, List, Dict, Any
from src.models.conversation import ConversationSession
from src.storage.sqlite_store import SQLiteStore
import logging

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
        self, 
        user_id: str, 
        cost_limit: float = 1.0,
        source: str = "cli"
    ) -> ConversationSession:
        """Create a new conversation session.
        
        Args:
            user_id: User ID for the conversation
            cost_limit: Cost limit for the session
            source: Request source - "cli" or "api"
            
        Returns:
            New ConversationSession
        """
        session = ConversationSession(
            user_id=user_id, 
            cost_limit=cost_limit,
            request_source=source
        )
        
        # Persist to database
        self.storage.create_conversation(
            session_id=session.session_id,
            user_id=user_id,
            cost_limit=cost_limit,
        )
        
        logger.info(f"Created conversation {session.session_id} for user {user_id} (source={source})")
        return session

    def get_conversation(self, session_id: str) -> Optional[ConversationSession]:
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
            session.add_to_context({
                "role": msg["role"],
                "content": msg["content"],
                "token_count": msg.get("token_count", 0),
            })
        
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

    def save_message(self, message_data: Dict[str, Any]) -> None:
        """Save a message to conversation.
        
        Args:
            message_data: Message dict with all fields
        """
        self.storage.save_message(message_data)

    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get messages for a conversation.
        
        Args:
            session_id: Session ID
            limit: Maximum number of messages to return
            
        Returns:
            List of message dicts
        """
        return self.storage.get_messages(session_id, limit)
