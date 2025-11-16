"""Memory store tool for personal information persistence."""

import logging
import time
import uuid
from typing import Any

from src.lib.encryption import EncryptionManager
from src.storage.vector_store import VectorStore
from src.tools.base_tool import BaseTool, ToolResult, ToolStatus

logger = logging.getLogger(__name__)


class MemoryStoreTool(BaseTool):
    """Tool for storing and retrieving personal user information."""

    def __init__(
        self,
        config: dict[str, Any],
        vector_store: VectorStore,
        encryption_key: str,
    ):
        """Initialize memory store tool.

        Args:
            config: Tool configuration
            vector_store: Vector store instance
            encryption_key: Encryption key for sensitive data
        """
        super().__init__(config)
        self.vector_store = vector_store
        self.encryption = EncryptionManager(encryption_key)
        self.embedding_model = None
        self._init_embedding_model()

    def _init_embedding_model(self):
        """Initialize sentence transformer model for embeddings."""
        try:
            from sentence_transformers import SentenceTransformer

            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            self.embedding_model = SentenceTransformer(model_name)
            logger.info(f"Loaded embedding model: {model_name}")
        except ImportError:
            logger.warning("sentence-transformers not installed, using mock embeddings")
            self.embedding_model = None

    def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            384-dimensional embedding vector
        """
        if self.embedding_model:
            embedding = self.embedding_model.encode(text)
            return embedding.tolist()
        else:
            # Mock embedding for testing without sentence-transformers
            import random

            random.seed(hash(text) % (2**32))
            return [random.random() for _ in range(384)]

    async def execute(self, parameters: dict[str, Any]) -> ToolResult:
        """Execute memory operation.

        Args:
            parameters: Dict with 'action', 'user_id', and action-specific params

        Returns:
            ToolResult with operation outcome
        """
        start_time = time.time()

        try:
            action = parameters.get("action", "store")

            if action == "store":
                result = await self._store_memory(parameters)
            elif action == "search":
                result = await self._search_memory(parameters)
            elif action == "delete":
                result = await self._delete_memory(parameters)
            elif action == "update":
                result = await self._update_memory(parameters)
            else:
                raise ValueError(f"Unknown action: {action}")

            elapsed_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.SUCCESS,
                data=result,
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Memory operation failed: {e}")
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.FAILED,
                error=str(e),
                execution_time_ms=elapsed_ms,
            )

    async def _store_memory(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Store a memory.

        Args:
            parameters: Dict with user_id, memory_type, content

        Returns:
            Dict with memory_id
        """
        user_id = parameters.get("user_id", "default_user")
        memory_type = parameters.get("memory_type", "fact")
        content = parameters.get("content", "")

        # Encrypt sensitive content
        encrypted_content = self.encryption.encrypt(content)

        # Generate embedding
        vector = self._generate_embedding(content)

        # Store in vector database
        memory_id = str(uuid.uuid4())
        self.vector_store.store_user_memory(
            memory_id=memory_id,
            user_id=user_id,
            memory_type=memory_type,
            content=encrypted_content,
            vector=vector,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            metadata=parameters.get("metadata", {}),
        )

        logger.info(f"Stored memory {memory_id} for user {user_id}")
        return {"memory_id": memory_id, "status": "stored"}

    async def _search_memory(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Search memories semantically.

        Args:
            parameters: Dict with user_id, query

        Returns:
            Dict with matching memories
        """
        user_id = parameters.get("user_id", "default_user")
        query = parameters.get("query", "")
        top_k = parameters.get("top_k", 5)
        memory_type = parameters.get("memory_type")

        # Generate query embedding
        query_vector = self._generate_embedding(query)

        # Search vector store
        results = self.vector_store.search_user_memory(
            user_id=user_id,
            query_vector=query_vector,
            top_k=top_k,
            similarity_threshold=0.7,
            memory_type=memory_type,
        )

        # Decrypt results
        memories = []
        for result in results:
            try:
                decrypted_content = self.encryption.decrypt(result.get("content", ""))
                memories.append(
                    {
                        "memory_id": result.get("memory_id"),
                        "content": decrypted_content,
                        "memory_type": result.get("memory_type"),
                        "timestamp": result.get("timestamp"),
                        "score": result.get("_distance", 0),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to decrypt memory: {e}")

        logger.info(f"Found {len(memories)} memories for user {user_id}")
        return {"memories": memories, "count": len(memories)}

    async def _delete_memory(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Delete a memory by ID.

        Args:
            parameters: Dict with memory_id

        Returns:
            Dict with deletion status
        """
        memory_id = parameters.get("memory_id", "")

        if not memory_id:
            raise ValueError("memory_id is required for deletion")

        self.vector_store.delete_user_memory(memory_id)

        logger.info(f"Deleted memory {memory_id}")
        return {"memory_id": memory_id, "status": "deleted"}

    async def _update_memory(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Update existing memory or create new if similar memory exists.

        Conflict resolution strategy:
        - Search for similar memories (>0.85 similarity)
        - If found and newer info, delete old and store new
        - If no conflict, store as new memory

        Args:
            parameters: Dict with user_id, memory_type, content

        Returns:
            Dict with memory_id and conflict_resolution status
        """
        user_id = parameters.get("user_id", "default_user")
        content = parameters.get("content", "")
        memory_type = parameters.get("memory_type", "fact")

        # Search for similar existing memories
        query_vector = self._generate_embedding(content)
        existing = self.vector_store.search_user_memory(
            user_id=user_id,
            query_vector=query_vector,
            top_k=3,
            similarity_threshold=0.85,  # High threshold for conflicts
            memory_type=memory_type,
        )

        conflict_resolution = "new"

        # If very similar memory exists, replace it
        if existing and len(existing) > 0:
            # Delete the most similar one
            old_memory_id = existing[0].get("memory_id")
            self.vector_store.delete_user_memory(old_memory_id)
            logger.info(f"Replaced conflicting memory {old_memory_id}")
            conflict_resolution = "replaced"

        # Store new memory
        encrypted_content = self.encryption.encrypt(content)
        vector = self._generate_embedding(content)
        memory_id = str(uuid.uuid4())

        self.vector_store.store_user_memory(
            memory_id=memory_id,
            user_id=user_id,
            memory_type=memory_type,
            content=encrypted_content,
            vector=vector,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            metadata={
                **parameters.get("metadata", {}),
                "conflict_resolution": conflict_resolution,
            },
        )

        logger.info(f"Updated memory {memory_id} (resolution: {conflict_resolution})")
        return {
            "memory_id": memory_id,
            "status": "updated",
            "conflict_resolution": conflict_resolution,
        }

    async def fallback(self, parameters: dict[str, Any], error: Exception) -> ToolResult:
        """Fallback for memory operations.

        Args:
            parameters: Original parameters
            error: Exception that caused failure

        Returns:
            ToolResult indicating graceful failure
        """
        logger.warning(f"Memory operation fallback: {error}")
        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.FAILED,
            error=f"Memory operation failed: {error}",
            execution_time_ms=0,
            fallback_used=True,
        )
