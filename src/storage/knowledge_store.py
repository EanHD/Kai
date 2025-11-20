# src/storage/knowledge_store.py
import logging
import uuid
import time
from typing import Any, List, Optional
from src.models.knowledge import KnowledgeObject
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)

class KnowledgeStore:
    def __init__(
        self,
        sqlite_store: SQLiteStore,
        vector_store: VectorStore,
        embeddings_provider=None
    ):
        self.sqlite_store = sqlite_store
        self.vector_store = vector_store
        self.embeddings_provider = embeddings_provider

    def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text."""
        if self.embeddings_provider:
            try:
                embeddings = self.embeddings_provider.embed([text])
                return embeddings[0] if embeddings else self._mock_embedding(text)
            except Exception as e:
                logger.warning(f"Embedding generation failed, using mock: {e}")
                return self._mock_embedding(text)
        else:
            return self._mock_embedding(text)

    def _mock_embedding(self, text: str, dimensions: int = 1536) -> list[float]:
        import random
        random.seed(hash(text) % (2**32))
        return [random.random() for _ in range(dimensions)]

    def store(self, ko: KnowledgeObject) -> str:
        """Store a Knowledge Object."""
        knowledge_id = str(uuid.uuid4())
        
        # 1. Store in SQLite (structured data)
        self.sqlite_store.store_knowledge_object(
            knowledge_id=knowledge_id,
            ko_data=ko.model_dump()
        )
        
        # 2. Generate embedding
        # We embed the query + summary to capture the "question and answer" essence
        embedding_text = f"{ko.query}\n{ko.summary}"
        vector = self._generate_embedding(embedding_text)
        
        # 3. Store in VectorStore (semantic search)
        self.vector_store.store_knowledge_embedding(
            knowledge_id=knowledge_id,
            query=ko.query,
            summary=ko.summary,
            vector=vector,
            kind=ko.kind,
            timestamp=ko.created_at.isoformat(),
            metadata=ko.metadata
        )
        
        logger.info(f"Stored Knowledge Object {knowledge_id} for query: {ko.query[:50]}...")
        return knowledge_id

    def retrieve(self, knowledge_id: str) -> Optional[KnowledgeObject]:
        """Retrieve a Knowledge Object by ID."""
        data = self.sqlite_store.get_knowledge_object(knowledge_id)
        if data:
            self.sqlite_store.increment_knowledge_access(knowledge_id)
            return KnowledgeObject(**data)
        return None

    def search(
        self, 
        query: str, 
        kind: Optional[str] = None, 
        top_k: int = 3,
        similarity_threshold: float = 0.8
    ) -> List[KnowledgeObject]:
        """Search for Knowledge Objects semantically."""
        vector = self._generate_embedding(query)
        
        results = self.vector_store.search_knowledge_objects(
            query_vector=vector,
            top_k=top_k,
            kind=kind,
            similarity_threshold=similarity_threshold
        )
        
        objects = []
        for res in results:
            ko = self.retrieve(res["knowledge_id"])
            if ko:
                objects.append(ko)
                
        return objects
