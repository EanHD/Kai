"""Tool invocation model for tracking tool execution."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ToolInvocation:
    """Represents a tool execution with tracking and results."""

    invocation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_message_id: str = ""
    tool_name: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    parameters: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    execution_time_ms: int = 0
    status: str = "pending"  # pending, running, success, failed, timeout
    fallback_used: bool = False

    def is_successful(self) -> bool:
        """Check if invocation was successful.

        Returns:
            True if status is success
        """
        return self.status == "success"

    def is_failed(self) -> bool:
        """Check if invocation failed.

        Returns:
            True if status is failed or timeout
        """
        return self.status in ["failed", "timeout"]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage.

        Returns:
            Dict representation
        """
        return {
            "invocation_id": self.invocation_id,
            "query_message_id": self.query_message_id,
            "tool_name": self.tool_name,
            "timestamp": self.timestamp.isoformat(),
            "parameters": self.parameters,
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "status": self.status,
            "fallback_used": self.fallback_used,
        }
