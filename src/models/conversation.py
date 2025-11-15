"""Conversation model for session management."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

logger = logging.getLogger(__name__)

# Tiktoken for accurate token counting
try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not available, using simple token estimation")


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens in text using tiktoken or simple estimation.

    Args:
        text: Text to count tokens for
        model: Model name for tiktoken encoding (default: gpt-3.5-turbo)

    Returns:
        Token count
    """
    if TIKTOKEN_AVAILABLE:
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"tiktoken failed, using estimation: {e}")

    # Fallback: rough estimation (1 token ≈ 4 characters)
    return len(text) // 4


@dataclass
class ConversationSession:
    """Represents a single conversation session with context and cost tracking."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    last_activity: datetime = field(default_factory=datetime.utcnow)
    request_source: str = "cli"  # "cli" or "api"
    total_cost: float = 0.0
    cost_limit: float = 1.0
    message_count: int = 0
    active_tools: list[str] = field(default_factory=list)
    context_window: list[dict[str, Any]] = field(default_factory=list)
    current_topic_embedding: list[float] | None = None  # For topic shift detection

    def add_cost(self, cost: float) -> None:
        """Add cost to session total.

        Args:
            cost: Cost to add in USD
        """
        self.total_cost += cost
        self.message_count += 1

    def is_within_limit(self) -> bool:
        """Check if session is within cost limit.

        Returns:
            True if under limit, False otherwise
        """
        return self.total_cost < self.cost_limit

    def approaching_limit(self, threshold: float = 0.8) -> bool:
        """Check if approaching cost limit.

        Args:
            threshold: Percentage threshold (default 80%)

        Returns:
            True if at or above threshold
        """
        return self.total_cost >= (self.cost_limit * threshold)

    def end_session(self) -> None:
        """Mark session as ended."""
        self.ended_at = datetime.now(UTC)

    def is_active(self) -> bool:
        """Check if session is still active.

        Returns:
            True if active, False if ended
        """
        return self.ended_at is None

    def add_to_context(
        self, message: dict[str, Any], max_tokens: int = 4096, model: str = "gpt-3.5-turbo"
    ) -> None:
        """Add message to context window with token and time-aware management.

        Uses tiktoken for accurate token counting if available.

        Args:
            message: Message dict with role, content, token_count (optional), timestamp (optional)
            max_tokens: Maximum context window size
            model: Model name for token counting (default: gpt-3.5-turbo)
        """
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.now(UTC).isoformat()

        # Calculate accurate token count if not provided
        if "token_count" not in message and "content" in message:
            message["token_count"] = count_tokens(message["content"], model)

        self.context_window.append(message)
        self.last_activity = datetime.now(UTC)

        # Token management - remove oldest messages if over limit
        total_tokens = sum(msg.get("token_count", 0) for msg in self.context_window)

        while total_tokens > max_tokens and len(self.context_window) > 1:
            removed = self.context_window.pop(0)
            total_tokens -= removed.get("token_count", 0)

    def get_context_messages(
        self, include_old: bool = False, time_threshold_minutes: int = 30
    ) -> list[dict[str, str]]:
        """Get context window as simple message list with time-based filtering.

        Args:
            include_old: If False, filter out messages older than threshold
            time_threshold_minutes: Age threshold in minutes (default 30)

        Returns:
            List of {role, content} dicts
        """
        messages = []
        now = datetime.now(UTC)

        for msg in self.context_window:
            # Parse timestamp
            msg_time = msg.get("timestamp")
            if msg_time and not include_old:
                if isinstance(msg_time, str):
                    msg_time = datetime.fromisoformat(msg_time)

                # Skip old messages (>30min) - will be handled by topic relevance later
                age_minutes = (now - msg_time).total_seconds() / 60
                if age_minutes > time_threshold_minutes:
                    continue

            messages.append({"role": msg["role"], "content": msg["content"]})

        return messages

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage.

        Returns:
            Dict representation
        """
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "last_activity": self.last_activity.isoformat(),
            "request_source": self.request_source,
            "total_cost": self.total_cost,
            "cost_limit": self.cost_limit,
            "message_count": self.message_count,
            "active_tools": self.active_tools,
        }
