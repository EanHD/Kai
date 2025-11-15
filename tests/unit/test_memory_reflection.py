"""Unit tests for memory and reflection agents."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import shutil
import tempfile
from unittest.mock import Mock

import pytest

from src.agents.reflection_agent import ReflectionAgent
from src.core.llm_connector import LLMResponse
from src.storage.memory_vault import MemoryVault


@pytest.fixture
def temp_memory_dir():
    """Create temporary memory directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def memory_vault(temp_memory_dir):
    """Create memory vault with temp directory."""
    return MemoryVault(user_id="test_user", base_dir=temp_memory_dir)


@pytest.fixture
def mock_llm():
    """Create mock LLM connector."""
    mock = Mock()

    async def mock_generate(messages, temperature=0.7, max_tokens=None):
        return LLMResponse(
            content="Good reflection: The response was clear and concise.",
            token_count=15,
            cost=0.0001,
            model_used="test-model",
            finish_reason="stop",
            metadata={},
        )

    mock.generate = mock_generate
    return mock


def test_memory_vault_add_episode(memory_vault):
    """Test adding episodic memory."""
    record = memory_vault.add_episode(
        session_id="test_session",
        user_text="What is Python?",
        assistant_text="Python is a programming language.",
        success=True,
        summary="Question about Python",
        confidence=0.9,
        tags=["python", "programming"],
    )

    assert record.id is not None
    assert record.type == "episodic"
    assert record.summary == "Question about Python"
    assert record.confidence == 0.9
    assert "python" in record.tags


@pytest.mark.asyncio
async def test_memory_vault_write_episodic(memory_vault):
    """Test async write_episodic method."""
    record = await memory_vault.write_episodic(
        session_id="api_session",
        user_text="Hello world",
        assistant_text="Hello! How can I help?",
        success=True,
        summary="Greeting",
        confidence=0.8,
        tags=["greeting"],
    )

    assert record is not None
    assert record.type == "episodic"
    assert record.payload["session_id"] == "api_session"


def test_memory_vault_list_episodes(memory_vault):
    """Test listing episodic memories."""
    # Add multiple episodes
    for i in range(3):
        memory_vault.add_episode(
            session_id=f"session_{i}",
            user_text=f"Query {i}",
            assistant_text=f"Response {i}",
            tags=["test"],
        )

    # List all episodes
    episodes = memory_vault.list(mtype="episodic")
    assert len(episodes) >= 3

    # Filter by tag
    tagged = memory_vault.list(mtype="episodic", tag="test")
    assert len(tagged) >= 3


def test_memory_vault_add_reflection(memory_vault):
    """Test adding reflection memory."""
    record = memory_vault.add(
        "reflection",
        payload={
            "episode_id": "ep_123",
            "reflection": "Good interaction",
            "learnings": {"rules": ["Be concise"]},
        },
        summary="Reflection on episode 123",
        confidence=0.7,
        tags=["auto-generated"],
    )

    assert record.type == "reflection"
    assert record.payload["episode_id"] == "ep_123"


def test_memory_vault_prune(memory_vault):
    """Test pruning low-confidence old memories."""
    # Add low confidence memory
    memory_vault.add(
        "semantic",
        payload={"rule": "Low confidence rule"},
        confidence=0.1,  # Very low
        ttl_days=1,  # Short TTL
        tags=["test"],
    )

    # Add high confidence memory
    memory_vault.add(
        "semantic",
        payload={"rule": "High confidence rule"},
        confidence=0.9,
        tags=["test"],
    )

    # Prune (low confidence should be removed after TTL)
    removed = memory_vault.prune()

    # Check that pruning ran
    assert isinstance(removed, dict)


@pytest.mark.asyncio
async def test_reflection_agent_reflect_on_episode(mock_llm, memory_vault):
    """Test reflection agent generates reflections."""
    agent = ReflectionAgent(mock_llm, memory_vault)

    reflection = await agent.reflect_on_episode(
        episode_id="ep_001",
        user_text="How do I use pytest?",
        assistant_text="Pytest is a testing framework...",
        success=True,
        mode="expert",
        tools_used=["web_search"],
    )

    assert reflection is not None
    assert "episode_id" in reflection["payload"]
    assert reflection["payload"]["episode_id"] == "ep_001"
    assert "reflection" in reflection["payload"]


@pytest.mark.asyncio
async def test_reflection_agent_handles_failure(mock_llm, memory_vault):
    """Test reflection agent handles LLM failures gracefully."""

    # Mock LLM that raises an error
    async def failing_generate(messages, temperature=0.7, max_tokens=None):
        raise RuntimeError("LLM failed")

    mock_llm.generate = failing_generate

    agent = ReflectionAgent(mock_llm, memory_vault)

    # Should return None on failure, not raise
    reflection = await agent.reflect_on_episode(
        episode_id="ep_fail",
        user_text="Test",
        assistant_text="Test response",
        success=False,
    )

    assert reflection is None


def test_memory_vault_export_markdown(memory_vault, temp_memory_dir):
    """Test exporting memories to markdown."""
    # Add some memories
    memory_vault.add_episode(
        session_id="test",
        user_text="Test query",
        assistant_text="Test response",
        tags=["test"],
    )

    # Export
    out_path = Path(temp_memory_dir) / "export.md"
    result = memory_vault.export_markdown(str(out_path))

    assert Path(result).exists()
    content = Path(result).read_text()
    assert "Memory Vault Export" in content
    assert "test_user" in content


@pytest.mark.asyncio
async def test_reflection_distillation_insufficient_data(mock_llm, memory_vault):
    """Test distillation sweep skips when insufficient data."""
    agent = ReflectionAgent(mock_llm, memory_vault)

    # Run distillation with no episodes
    result = await agent.distillation_sweep(days_back=7, min_episodes=5)

    assert result["status"] == "skipped"
    assert "insufficient" in result["reason"]


@pytest.mark.asyncio
async def test_reflection_distillation_with_data(mock_llm, memory_vault):
    """Test distillation sweep with sufficient data."""
    # Add multiple episodes and reflections
    for i in range(6):
        ep = memory_vault.add_episode(
            session_id=f"s_{i}",
            user_text=f"Query {i}",
            assistant_text=f"Response {i}",
            tags=["test"],
        )

        memory_vault.add(
            "reflection",
            payload={
                "episode_id": ep.id,
                "reflection": "Good interaction",
                "learnings": {
                    "rules": [f"Rule {i}"],
                    "improvements": ["Be clear"],
                },
            },
            summary=f"Reflection {i}",
            tags=["auto-generated"],
        )

    agent = ReflectionAgent(mock_llm, memory_vault)

    # Mock LLM to return structured distillation
    async def mock_distill_generate(messages, temperature=0.7, max_tokens=None):
        return LLMResponse(
            content='{"rules": ["Always be clear"], "prompts": ["Use simple language"], "procedures": ["Check understanding"]}',
            token_count=30,
            cost=0.0002,
            model_used="test-model",
            finish_reason="stop",
            metadata={},
        )

    mock_llm.generate = mock_distill_generate

    result = await agent.distillation_sweep(days_back=7, min_episodes=5)

    assert result["status"] == "completed"
    assert result["episodes_analyzed"] >= 5
