"""Response model for system output formatting."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Citation:
    """Source citation for web search results."""

    title: str
    url: str
    snippet: str
    accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PersonalContext:
    """Personal context retrieved from memory."""

    memory_id: str
    content: str
    memory_type: str  # fact, preference, schedule, goal
    relevance_score: float
    timestamp: str


@dataclass
class ToolResultData:
    """Tool execution result data."""

    tool_name: str
    data: dict[str, Any]
    execution_time_ms: int


@dataclass
class Response:
    """Represents system response with mode and metadata."""

    response_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    mode: str = "concise"  # concise, expert, advisor
    content: str = ""
    source_citations: list[Citation] = field(default_factory=list)
    personal_context: list[PersonalContext] = field(default_factory=list)
    tool_results: list[ToolResultData] = field(default_factory=list)
    confidence: float = 1.0
    token_count: int = 0
    cost: float = 0.0

    def is_concise(self) -> bool:
        """Check if response is in concise mode.

        Returns:
            True if concise mode
        """
        return self.mode == "concise"

    def is_expert(self) -> bool:
        """Check if response is in expert mode.

        Returns:
            True if expert mode
        """
        return self.mode == "expert"

    def is_advisor(self) -> bool:
        """Check if response is in advisor mode.

        Returns:
            True if advisor mode
        """
        return self.mode == "advisor"

    def has_citations(self) -> bool:
        """Check if response has source citations.

        Returns:
            True if citations present
        """
        return len(self.source_citations) > 0

    def has_personal_context(self) -> bool:
        """Check if response uses personal context.

        Returns:
            True if personal context present
        """
        return len(self.personal_context) > 0

    def format_content(self) -> str:
        """Format content based on mode.

        Returns:
            Formatted response text
        """
        if self.mode == "concise":
            return self._format_concise()
        elif self.mode == "expert":
            return self._format_expert()
        elif self.mode == "advisor":
            return self._format_advisor()
        return self.content

    def _format_concise(self) -> str:
        """Format concise response (1-2 sentences).

        Returns:
            Concise formatted text
        """
        # Ensure content is brief
        sentences = self.content.split(". ")
        if len(sentences) > 2:
            return ". ".join(sentences[:2]) + "."
        return self.content

    def _format_expert(self) -> str:
        """Format expert response (structured breakdown).

        Returns:
            Expert formatted text with headings and structure
        """
        # Expert mode provides structured, detailed analysis
        # Add structure markers if content is detailed
        if "\n" not in self.content and len(self.content) > 200:
            # Add basic structure by splitting on sentence patterns
            import re

            # Look for natural break points
            structured = self.content

            # Add breaks before "First", "Second", "Additionally", etc.
            structured = re.sub(
                r"(First|Second|Third|Additionally|Furthermore|Moreover|However|Finally)",
                r"\n\n**\1**",
                structured,
            )

            # Add breaks before numbered lists
            structured = re.sub(r"(\d+\.)\s+", r"\n\n\1 ", structured)

            return structured.strip()

        return self.content

    def _format_advisor(self) -> str:
        """Format advisor response (supportive, protective guidance).

        Returns:
            Advisor formatted text with empathetic tone
        """
        # Advisor mode is empathetic, protective, and action-oriented
        # Add supportive framing if not already present
        content = self.content.strip()

        # Check if already has supportive tone
        supportive_markers = [
            "I understand",
            "I hear you",
            "It sounds like",
            "Let me help",
            "Here's what",
            "I recommend",
        ]

        has_supportive_tone = any(marker in content for marker in supportive_markers)

        if not has_supportive_tone and len(content) > 50:
            # Add gentle framing
            if "?" in content[:100]:  # If starts with context
                return content
            else:
                # Add supportive lead-in
                return f"I understand this is important. {content}"

        return content

    def add_citation(self, title: str, url: str, snippet: str) -> None:
        """Add a source citation.

        Args:
            title: Source title
            url: Source URL
            snippet: Relevant excerpt
        """
        citation = Citation(title=title, url=url, snippet=snippet)
        self.source_citations.append(citation)

    def add_tool_result(self, tool_name: str, data: dict[str, Any], execution_time_ms: int) -> None:
        """Add tool execution result.

        Args:
            tool_name: Name of tool
            data: Result data
            execution_time_ms: Execution time
        """
        result = ToolResultData(
            tool_name=tool_name,
            data=data,
            execution_time_ms=execution_time_ms,
        )
        self.tool_results.append(result)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage.

        Returns:
            Dict representation
        """
        return {
            "message_id": self.response_id,
            "query_message_id": self.query_id,
            "timestamp": self.timestamp.isoformat(),
            "role": "assistant",
            "content": self.content,
            "mode": self.mode,
            "source_citations": [
                {
                    "title": c.title,
                    "url": c.url,
                    "snippet": c.snippet,
                    "accessed_at": c.accessed_at.isoformat(),
                }
                for c in self.source_citations
            ],
            "tool_results": [
                {
                    "tool_name": t.tool_name,
                    "data": t.data,
                    "execution_time_ms": t.execution_time_ms,
                }
                for t in self.tool_results
            ],
            "confidence": self.confidence,
            "token_count": self.token_count,
            "cost": self.cost,
        }


def select_response_mode(
    complexity: str,
    emotional_tone: dict[str, Any],
    goal_deviation: bool = False,
    explicit_override: str | None = None,
) -> str:
    """Select appropriate response mode.

    Args:
        complexity: Query complexity level
        emotional_tone: Emotional analysis dict
        goal_deviation: Whether query deviates from user goals
        explicit_override: Explicit mode request from user query

    Returns:
        Response mode: concise, expert, or advisor
    """
    # Handle explicit user override
    if explicit_override:
        return explicit_override

    emotion = emotional_tone.get("emotion", "neutral")

    # Advisor mode for distressed/frustrated users or goal deviation
    if emotion in ["distressed", "frustrated"] or goal_deviation:
        return "advisor"

    # Expert mode for complex queries
    if complexity == "complex":
        return "expert"

    # Expert mode for moderate queries with multiple tools
    if complexity == "moderate":
        return "expert"

    # Stay concise for positive/excited users on simple queries
    if emotion in ["positive", "excited"] and complexity == "simple":
        return "concise"

    # Default to concise for simple queries
    return "concise"
