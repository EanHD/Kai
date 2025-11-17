"""ChromaDB vector store implementation for embeddings and semantic search."""

import json
import logging
from pathlib import Path
from typing import Any

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None

logger = logging.getLogger(__name__)


class VectorStore:
    """Manages ChromaDB vector database operations."""

    def __init__(self, db_path: str):
        """Initialize vector store.

        Args:
            db_path: Path to ChromaDB database directory
        """
        if not CHROMADB_AVAILABLE:
            logger.warning(
                "ChromaDB not available. Vector storage disabled - using fallback memory storage."
            )
            self.client = None
            self.db_path = None
            return

        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )
        
        self._init_collections()
        logger.info(f"Vector store initialized at {self.db_path}")

    def _init_collections(self):
        """Initialize ChromaDB collections if they don't exist."""
        if not self.client:
            return

        # Get or create collections
        self.user_memory = self.client.get_or_create_collection(
            name="user_memory",
            metadata={"description": "User memories and preferences"}
        )
        
        self.conversation_history = self.client.get_or_create_collection(
            name="conversation_history",
            metadata={"description": "Conversation history for context"}
        )
        
        self.tool_results = self.client.get_or_create_collection(
            name="tool_results",
            metadata={"description": "Cached tool execution results"}
        )
        
        logger.info("Vector store collections initialized")

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
        if not self.client:
            logger.debug("Vector store not available, skipping memory storage")
            return

        meta = {
            "user_id": user_id,
            "memory_type": memory_type,
            "timestamp": timestamp,
            **(metadata or {}),
        }
        
        self.user_memory.add(
            ids=[memory_id],
            embeddings=[vector],
            documents=[content],
            metadatas=[meta]
        )
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
            similarity_threshold: Minimum similarity score (ChromaDB uses distance, lower is better)
            memory_type: Optional filter by memory type

        Returns:
            List of matching memories with scores
        """
        if not self.client:
            return []

        # Build where filter
        where_filter = {"user_id": user_id}
        if memory_type:
            where_filter["memory_type"] = memory_type

        # Execute search
        results = self.user_memory.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where_filter
        )

        # Convert ChromaDB results to our format
        # ChromaDB returns distances (lower is better), we want similarity (higher is better)
        # Convert distance to similarity: similarity = 1 / (1 + distance)
        # Flatten metadata to top level for compatibility with existing code
        formatted_results = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i, id_val in enumerate(results['ids'][0]):
                distance = results['distances'][0][i]
                similarity = 1.0 / (1.0 + distance)
                
                if similarity >= similarity_threshold:
                    metadata = results['metadatas'][0][i]
                    result = {
                        "memory_id": id_val,
                        "content": results['documents'][0][i],
                        "_distance": distance,
                        "_similarity": similarity,
                        # Flatten metadata fields to top level for compatibility
                        "user_id": metadata.get("user_id"),
                        "memory_type": metadata.get("memory_type"),
                        "timestamp": metadata.get("timestamp"),
                    }
                    # Include any additional metadata fields
                    for key, value in metadata.items():
                        if key not in ["user_id", "memory_type", "timestamp"]:
                            result[key] = value
                    formatted_results.append(result)

        return formatted_results

    def delete_user_memory(self, memory_id: str) -> None:
        """Delete specific user memory."""
        if not self.client:
            return
            
        self.user_memory.delete(ids=[memory_id])

    def get_user_memories(
        self, user_id: str, memory_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Get all memories for a user, optionally filtered by type."""
        if not self.client:
            return []

        where_filter = {"user_id": user_id}
        if memory_type:
            where_filter["memory_type"] = memory_type

        results = self.user_memory.get(where=where_filter)
        
        # Convert to our format with flattened metadata
        formatted_results = []
        if results['ids']:
            for i, id_val in enumerate(results['ids']):
                metadata = results['metadatas'][i]
                result = {
                    "memory_id": id_val,
                    "content": results['documents'][i],
                    "user_id": metadata.get("user_id"),
                    "memory_type": metadata.get("memory_type"),
                    "timestamp": metadata.get("timestamp"),
                }
                # Include any additional metadata fields
                for key, value in metadata.items():
                    if key not in ["user_id", "memory_type", "timestamp"]:
                        result[key] = value
                formatted_results.append(result)

        return formatted_results

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
        if not self.client:
            logger.debug("Vector store not available, skipping conversation storage")
            return

        meta = {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "timestamp": timestamp,
            **(metadata or {}),
        }
        
        self.conversation_history.add(
            ids=[message_id],
            embeddings=[vector],
            documents=[content],
            metadatas=[meta]
        )

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
        if not self.client:
            return []

        where_filter = {"user_id": user_id}
        if session_id:
            where_filter["session_id"] = session_id

        results = self.conversation_history.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where_filter
        )

        # Convert to our format with flattened metadata
        formatted_results = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i, id_val in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                result = {
                    "message_id": id_val,
                    "content": results['documents'][0][i],
                    "_distance": results['distances'][0][i],
                    # Flatten metadata fields
                    "session_id": metadata.get("session_id"),
                    "user_id": metadata.get("user_id"),
                    "role": metadata.get("role"),
                    "timestamp": metadata.get("timestamp"),
                }
                # Include any additional metadata fields
                for key, value in metadata.items():
                    if key not in ["session_id", "user_id", "role", "timestamp"]:
                        result[key] = value
                formatted_results.append(result)

        return formatted_results

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
        if not self.client:
            logger.debug("Vector store not available, skipping tool cache")
            return

        meta = {
            "tool_name": tool_name,
            "parameters_hash": parameters_hash,
            "timestamp": timestamp,
            **(metadata or {}),
        }
        
        self.tool_results.add(
            ids=[result_id],
            embeddings=[vector],
            documents=[result],
            metadatas=[meta]
        )

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
        if not self.client:
            return []

        results = self.tool_results.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where={"tool_name": tool_name}
        )

        # High threshold for cache hits - must be very similar
        formatted_results = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i, id_val in enumerate(results['ids'][0]):
                distance = results['distances'][0][i]
                similarity = 1.0 / (1.0 + distance)
                
                if similarity >= similarity_threshold:
                    metadata = results['metadatas'][0][i]
                    result = {
                        "result_id": id_val,
                        "result": results['documents'][0][i],
                        "_distance": distance,
                        "_similarity": similarity,
                        # Flatten metadata fields
                        "tool_name": metadata.get("tool_name"),
                        "parameters_hash": metadata.get("parameters_hash"),
                        "timestamp": metadata.get("timestamp"),
                    }
                    # Include any additional metadata fields
                    for key, value in metadata.items():
                        if key not in ["tool_name", "parameters_hash", "timestamp"]:
                            result[key] = value
                    formatted_results.append(result)

        return formatted_results

    def get_cached_result_by_hash(
        self, tool_name: str, parameters_hash: str
    ) -> dict[str, Any] | None:
        """Get exact cache hit by parameter hash."""
        if not self.client:
            return None

        results = self.tool_results.get(
            where={
                "tool_name": tool_name,
                "parameters_hash": parameters_hash
            }
        )
        
        if results['ids'] and len(results['ids']) > 0:
            metadata = results['metadatas'][0]
            result = {
                "result_id": results['ids'][0],
                "result": results['documents'][0],
                # Flatten metadata fields
                "tool_name": metadata.get("tool_name"),
                "parameters_hash": metadata.get("parameters_hash"),
                "timestamp": metadata.get("timestamp"),
            }
            # Include any additional metadata fields
            for key, value in metadata.items():
                if key not in ["tool_name", "parameters_hash", "timestamp"]:
                    result[key] = value
            return result
        
        return None
