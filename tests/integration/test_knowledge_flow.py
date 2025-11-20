import pytest
import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from src.core.orchestrator import Orchestrator
from src.core.llm_connector import LLMConnector, LLMResponse, Message
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.models.knowledge import KnowledgeObject
from src.models.conversation import ConversationSession

# Mock LLM Connector
class MockConnector(LLMConnector):
    def __init__(self, name="mock", responses=None):
        self.model_name = name
        self.responses = responses or []
        self.calls = []
        self.model_config = {"model_name": name, "provider": "mock"}

    async def generate(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        if self.responses:
            content = self.responses.pop(0)
        else:
            content = "Mock response"
        
        return LLMResponse(
            content=content,
            token_count=10,
            cost=0.0,
            model_used=self.model_name,
            finish_reason="stop"
        )

    async def generate_stream(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        yield "Mock "
        yield "stream "
        yield "response"

    async def check_health(self):
        return True

@pytest.fixture
def temp_dir():
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir)

@pytest.mark.asyncio
async def test_knowledge_architecture_flow(temp_dir):
    print(f"\nTesting in {temp_dir}")
    
    # 1. Setup Stores
    sqlite_db = str(Path(temp_dir) / "kai.db")
    vector_db = str(Path(temp_dir) / "vectors")
    
    storage = SQLiteStore(db_path=sqlite_db)
    # Mock vector store to avoid chromadb dependency in test env if missing
    # But we want to test the logic. Let's try real one, if it fails we mock.
    # For this test, let's use the real VectorStore but mock the internal client if needed.
    # Actually, the code handles missing chromadb gracefully.
    vector_store = VectorStore(db_path=vector_db)
    
    # 2. Setup Connectors
    
    # Mock Cloud Reasoner Response (Valid Knowledge Object)
    ko_data = {
        "query": "Explain quantum entanglement",
        "summary": "Spooky action at a distance.",
        "detailed_points": [
            {"title": "Definition", "body": "Entangled particles share state."}
        ],
        "kind": "explanation",
        "confidence": 0.95
    }
    cloud_response = json.dumps(ko_data)
    
    external_connector = MockConnector(name="claude-mock", responses=[cloud_response])
    local_connector = MockConnector(name="smollm-mock")
    
    # 3. Initialize Orchestrator
    orchestrator = Orchestrator(
        local_connector=local_connector,
        external_connectors={"claude": external_connector},
        sqlite_store=storage,
        vector_store=vector_store,
        cost_limit=10.0
    )
    
    # Mock QueryAnalyzer to force "Complex" path
    orchestrator.query_analyzer.analyze = AsyncMock(return_value={
        "complexity_score": 0.9, # High complexity
        "capabilities": ["reasoning"]
    })
    
    # Mock PlanAnalyzer to return empty steps (Pure Reasoning path)
    orchestrator.plan_analyzer.analyze = AsyncMock(return_value=MagicMock(
        steps=[], 
        intent="explain", 
        complexity=MagicMock(value="complex")
    ))

    # 4. Test Scenario A: Cold Cache (Should call Cloud)
    print("\n--- Scenario A: Cold Cache ---")
    session = ConversationSession(session_id="test-session", user_id="test-user")
    query = "Explain quantum entanglement"
    
    response_chunks = []
    async for chunk in orchestrator.process_query_stream(query, session):
        response_chunks.append(chunk)
    
    full_response = "".join(response_chunks)
    print(f"Response: {full_response}")
    
    # Assertions
    assert len(external_connector.calls) == 1, "Cloud Reasoner should be called once"
    assert "Mock stream response" in full_response
    
    # Verify Storage (Check SQLite directly to avoid vector search issues with mock embeddings)
    # stored_ko = orchestrator.knowledge_store.search(query, top_k=1)
    # assert len(stored_ko) == 1, "Knowledge Object should be stored"
    
    # Direct SQLite check
    with orchestrator.knowledge_store.sqlite_store._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM knowledge_objects WHERE query = ?", (query,))
        row = cursor.fetchone()
        assert row is not None, "Knowledge Object should be in SQLite"
        assert row["summary"] == "Spooky action at a distance."
    
    print("✅ Cold Cache Test Passed")

    # 5. Test Scenario B: Warm Cache (Should NOT call Cloud)
    print("\n--- Scenario B: Warm Cache ---")
    # Reset calls
    external_connector.calls = []
    
    # Mock KnowledgeStore.search to return a hit (simulating vector match)
    original_search = orchestrator.knowledge_store.search
    orchestrator.knowledge_store.search = MagicMock(return_value=[
        KnowledgeObject(
            query=query,
            summary="Spooky action at a distance.",
            detailed_points=[],
            kind="explanation",
            confidence=0.95
        )
    ])
    
    # Same query
    response_chunks = []
    async for chunk in orchestrator.process_query_stream(query, session):
        response_chunks.append(chunk)
        
    # Assertions
    assert len(external_connector.calls) == 0, "Cloud Reasoner should NOT be called on cache hit"
    assert "Mock stream response" in "".join(response_chunks)
    print("✅ Warm Cache Test Passed")
    
    # Restore search
    orchestrator.knowledge_store.search = original_search
    
    # 6. Test Scenario C: Simple Query (Fast Path)
    print("\n--- Scenario C: Simple Query ---")
    orchestrator.query_analyzer.analyze = AsyncMock(return_value={
        "complexity_score": 0.1, # Low complexity
        "capabilities": []
    })
    
    query_simple = "Hi there"
    response_chunks = []
    async for chunk in orchestrator.process_query_stream(query_simple, session):
        response_chunks.append(chunk)
        
    assert len(external_connector.calls) == 0, "Cloud Reasoner should NOT be called for simple query"
    print("✅ Simple Query Test Passed")

if __name__ == "__main__":
    # Manual run helper
    asyncio.run(test_knowledge_architecture_flow(tempfile.mkdtemp()))
