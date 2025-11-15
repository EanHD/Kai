"""LanceDB vector store implementation for embeddings and semantic search."""

import logging
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa

logger = logging.getLogger(__name__)


# Define schemas using PyArrow (simpler than Pydantic for LanceDB)
def get_user_memory_schema() -> pa.Schema:
    """Get PyArrow schema for UserMemory table."""
    return pa.schema(
        [
            pa.field("memory_id", pa.string()),
            pa.field("user_id", pa.string()),
            pa.field("memory_type", pa.string()),
            pa.field("content", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), 384)),
            pa.field("timestamp", pa.string()),
            pa.field("metadata", pa.string()),  # JSON string
        ]
    )


def get_conversation_history_schema() -> pa.Schema:
    """Get PyArrow schema for ConversationHistory table."""
    return pa.schema(
        [
            pa.field("message_id", pa.string()),
            pa.field("session_id", pa.string()),
            pa.field("user_id", pa.string()),
            pa.field("role", pa.string()),
            pa.field("content", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), 384)),
            pa.field("timestamp", pa.string()),
            pa.field("metadata", pa.string()),  # JSON string
        ]
    )


def get_tool_results_schema() -> pa.Schema:
    """Get PyArrow schema for ToolResults table."""
    return pa.schema(
        [
            pa.field("result_id", pa.string()),
            pa.field("tool_name", pa.string()),
            pa.field("parameters_hash", pa.string()),
            pa.field("result", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), 384)),
            pa.field("timestamp", pa.string()),
            pa.field("metadata", pa.string()),  # JSON string
        ]
    )


class VectorStore:
    """Manages LanceDB vector database operations."""

    def __init__(self, db_path: str):
        """Initialize vector store.

        Args:
            db_path: Path to LanceDB database directory
        """
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(self.db_path))
        self._init_tables()
        logger.info(f"Vector store initialized at {self.db_path}")

    def _init_tables(self):
        """Initialize LanceDB tables if they don't exist."""
        # Check existing tables
        existing_tables = set(self.db.table_names())

        # Create UserMemory table if needed
        if "user_memory" not in existing_tables:
            self.db.create_table("user_memory", schema=get_user_memory_schema())
            logger.info("Created user_memory table")

        # Create ConversationHistory table if needed
        if "conversation_history" not in existing_tables:
            self.db.create_table("conversation_history", schema=get_conversation_history_schema())
            logger.info("Created conversation_history table")

        # Create ToolResults table if needed
        if "tool_results" not in existing_tables:
            self.db.create_table("tool_results", schema=get_tool_results_schema())
            logger.info("Created tool_results table")

    # User Memory operations
    def store_user_memory(
        self,
        memory_id: str,
        user_id: str,
        memory_type: str,
        content: str,
        vector: list[float],
        timestamp: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store user memory with embedding."""
        import json

        table = self.db.open_table("user_memory")
        data = [
            {
                "memory_id": memory_id,
                "user_id": user_id,
                "memory_type": memory_type,
                "content": content,
                "vector": vector,
                "timestamp": timestamp,
                "metadata": json.dumps(metadata or {}),
            }
        ]
        table.add(data)

    def search_user_memory(
        self,
        user_id: str,
        query_vector: list[float],
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search in user memories.

        Args:
            user_id: User to search memories for
            query_vector: Query embedding vector
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score
            memory_type: Optional filter by memory type

        Returns:
            List of matching memories with scores
        """
        table = self.db.open_table("user_memory")

        # Build filter
        filter_str = f"user_id = '{user_id}'"
        if memory_type:
            filter_str += f" AND memory_type = '{memory_type}'"

        # Execute search
        results = (
            table.search(query_vector).where(filter_str, prefilter=True).limit(top_k).to_list()
        )

        # Filter by similarity threshold
        filtered = [r for r in results if r.get("_distance", 0) >= similarity_threshold]
        return filtered

    def delete_user_memory(self, memory_id: str) -> None:
        """Delete specific user memory."""
        table = self.db.open_table("user_memory")
        table.delete(f"memory_id = '{memory_id}'")

    def get_user_memories(
        self, user_id: str, memory_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Get all memories for a user, optionally filtered by type."""
        table = self.db.open_table("user_memory")
        filter_str = f"user_id = '{user_id}'"
        if memory_type:
            filter_str += f" AND memory_type = '{memory_type}'"

        results = table.search().where(filter_str, prefilter=True).to_list()
        return results

    # Conversation History operations
    def store_conversation_message(
        self,
        message_id: str,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        vector: list[float],
        timestamp: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store conversation message with embedding."""
        import json

        table = self.db.open_table("conversation_history")
        data = [
            {
                "message_id": message_id,
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "vector": vector,
                "timestamp": timestamp,
                "metadata": json.dumps(metadata or {}),
            }
        ]
        table.add(data)

    def search_conversation_history(
        self,
        user_id: str,
        query_vector: list[float],
        top_k: int = 5,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search across conversation history.

        Args:
            user_id: User to search conversations for
            query_vector: Query embedding vector
            top_k: Number of results to return
            session_id: Optional filter by specific session

        Returns:
            List of matching messages
        """
        table = self.db.open_table("conversation_history")

        filter_str = f"user_id = '{user_id}'"
        if session_id:
            filter_str += f" AND session_id = '{session_id}'"

        results = (
            table.search(query_vector).where(filter_str, prefilter=True).limit(top_k).to_list()
        )
        return results

    # Tool Results caching operations
    def cache_tool_result(
        self,
        result_id: str,
        tool_name: str,
        parameters_hash: str,
        result: str,
        vector: list[float],
        timestamp: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Cache tool execution result."""
        import json

        table = self.db.open_table("tool_results")
        data = [
            {
                "result_id": result_id,
                "tool_name": tool_name,
                "parameters_hash": parameters_hash,
                "result": result,
                "vector": vector,
                "timestamp": timestamp,
                "metadata": json.dumps(metadata or {}),
            }
        ]
        table.add(data)

    def search_cached_results(
        self,
        tool_name: str,
        query_vector: list[float],
        top_k: int = 3,
        similarity_threshold: float = 0.9,
    ) -> list[dict[str, Any]]:
        """Search for similar cached tool results.

        Args:
            tool_name: Tool to search cache for
            query_vector: Embedding of current parameters
            top_k: Number of results to check
            similarity_threshold: High threshold for cache hits

        Returns:
            List of matching cached results
        """
        table = self.db.open_table("tool_results")

        results = (
            table.search(query_vector)
            .where(f"tool_name = '{tool_name}'", prefilter=True)
            .limit(top_k)
            .to_list()
        )

        # High threshold for cache hits - must be very similar
        filtered = [r for r in results if r.get("_distance", 0) >= similarity_threshold]
        return filtered

    def get_cached_result_by_hash(
        self, tool_name: str, parameters_hash: str
    ) -> dict[str, Any] | None:
        """Get exact cache hit by parameter hash."""
        table = self.db.open_table("tool_results")
        results = (
            table.search()
            .where(
                f"tool_name = '{tool_name}' AND parameters_hash = '{parameters_hash}'",
                prefilter=True,
            )
            .limit(1)
            .to_list()
        )
        return results[0] if results else None
