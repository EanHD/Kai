"""Query model for user input representation."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Query:
    """Represents a user query with analysis and routing information."""

    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    raw_text: str = ""
    source: str = "api"  # "cli" or "api" - where the query originated
    complexity_level: str = "simple"  # simple, moderate, complex
    emotional_tone: dict[str, Any] = field(default_factory=dict)
    required_capabilities: list[str] = field(default_factory=list)
    routing_decision: str = "local"  # local, external_opus, external_other
    confidence: float = 1.0

    def is_simple(self) -> bool:
        """Check if query is simple.

        Returns:
            True if complexity is simple
        """
        return self.complexity_level == "simple"

    def is_complex(self) -> bool:
        """Check if query is complex.

        Returns:
            True if complexity is complex
        """
        return self.complexity_level == "complex"

    def needs_tools(self) -> bool:
        """Check if query needs tool execution.

        Returns:
            True if tools required
        """
        return len(self.required_capabilities) > 0

    def needs_web_search(self) -> bool:
        """Check if query needs web search.

        Returns:
            True if web search required
        """
        return "web_search" in self.required_capabilities

    def needs_rag(self) -> bool:
        """Check if query needs RAG/memory retrieval.

        Returns:
            True if RAG required
        """
        return "rag" in self.required_capabilities

    def needs_code_execution(self) -> bool:
        """Check if query needs code execution.

        Returns:
            True if code execution required
        """
        return "code_exec" in self.required_capabilities

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage.

        Returns:
            Dict representation
        """
        return {
            "message_id": self.query_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "role": "user",
            "content": self.raw_text,
            "source": self.source,
            "complexity_level": self.complexity_level,
            "emotional_tone": self.emotional_tone,
            "routing_decision": self.routing_decision,
        }


def detect_complexity(text: str, capabilities: list[str]) -> str:
    """Detect query complexity level.

    Args:
        text: Query text
        capabilities: Required capabilities list

    Returns:
        Complexity level: simple, moderate, or complex
    """
    # Complex if needs code execution or multiple tools
    if "code_exec" in capabilities or len(capabilities) >= 3:
        return "complex"

    # Moderate if needs 1-2 tools
    if len(capabilities) > 0:
        return "moderate"

    # Check text for complexity indicators
    text_lower = text.lower()

    # Complex indicators
    complex_keywords = [
        "analyze",
        "compare",
        "evaluate",
        "explain how",
        "why does",
        "break down",
        "step by step",
        "in detail",
        "comprehensive",
    ]
    if any(keyword in text_lower for keyword in complex_keywords):
        return "complex"

    # Moderate indicators
    moderate_keywords = ["what is", "how to", "can you", "show me", "find", "search"]
    if any(keyword in text_lower for keyword in moderate_keywords):
        return "moderate"

    # Default to simple for casual queries
    return "simple"
