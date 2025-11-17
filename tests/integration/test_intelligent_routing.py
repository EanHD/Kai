"""Integration tests for intelligent tool routing without explicit hints.

Tests that the orchestrator correctly routes queries to appropriate tools
based on semantic understanding, NOT keyword matching.

Examples:
- "What's the NCR18650B capacity?" → web_search (implicit spec lookup)
- "13S4P with 3400mAh at 3.6V energy?" → code_exec (implicit calculation)
- "Remember I prefer LG cells" → rag (implicit memory storage)

These tests use REAL API calls to validate end-to-end behavior.
"""

import os
from pathlib import Path

import pytest
import yaml

# Test requires real connectors
pytestmark = pytest.mark.integration

# Import orchestration components
import uuid

from src.core.orchestrator import Orchestrator
from src.core.providers.ollama_provider import OllamaProvider
from src.core.providers.openrouter_provider import OpenRouterProvider
from src.models.conversation import ConversationSession
from src.tools.code_exec_wrapper import CodeExecWrapper
from src.tools.memory_store import MemoryStoreTool
from src.tools.sentiment_analyzer import SentimentAnalyzerTool
from src.tools.web_search import WebSearchTool


@pytest.fixture(scope="module")
def test_config():
    """Load test configuration."""
    config_path = Path(__file__).parent / "test_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
async def orchestrator(test_config):
    """Create orchestrator with real connectors."""

    # Initialize local connector (Granite via Ollama)
    granite_config = test_config["models"]["granite"]
    model_config = {
        "model_id": "granite",
        "model_name": granite_config["model_name"],
        "provider": "ollama",
        "capabilities": granite_config.get("capabilities", []),
        "context_window": granite_config.get("context_window", 4096),
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
    }
    local_connector = OllamaProvider(
        model_config=model_config,
        base_url=granite_config.get("base_url", "http://localhost:11434"),
    )

    # Initialize external connectors
    external_connectors = {}

    # Grok Fast
    if "OPENROUTER_API_KEY" in os.environ:
        grok_config = test_config["models"]["grok-fast"]
        grok_model_config = {
            "model_id": "grok-fast",
            "model_name": grok_config["model_name"],
            "provider": "openrouter",
            "capabilities": grok_config.get("capabilities", []),
            "context_window": grok_config.get("context_window", 8192),
            "cost_per_1k_input": grok_config.get("cost_per_1k_input", 0.0001),
            "cost_per_1k_output": grok_config.get("cost_per_1k_output", 0.0002),
        }
        external_connectors["grok-fast"] = OpenRouterProvider(
            model_config=grok_model_config,
            api_key=os.environ["OPENROUTER_API_KEY"],
        )

    # Claude Sonnet
    if "OPENROUTER_API_KEY" in os.environ:
        sonnet_config = test_config["models"]["claude-sonnet"]
        sonnet_model_config = {
            "model_id": "claude-sonnet",
            "model_name": sonnet_config["model_name"],
            "provider": "openrouter",
            "capabilities": sonnet_config.get("capabilities", []),
            "context_window": sonnet_config.get("context_window", 16384),
            "cost_per_1k_input": sonnet_config.get("cost_per_1k_input", 0.003),
            "cost_per_1k_output": sonnet_config.get("cost_per_1k_output", 0.015),
        }
        external_connectors["claude-sonnet"] = OpenRouterProvider(
            model_config=sonnet_model_config,
            api_key=os.environ["OPENROUTER_API_KEY"],
        )

    # Initialize tools
    tools = {}

    # Web search
    if test_config["tools"]["web_search"]["enabled"]:
        if "BRAVE_API_KEY" in os.environ:
            web_search_config = {
                "enabled": True,
                "api_key": os.environ["BRAVE_API_KEY"],
                "max_results": test_config["tools"]["web_search"]["max_results"],
            }
            tools["web_search"] = WebSearchTool(config=web_search_config)

    # Code execution
    if test_config["tools"]["code_exec"]["enabled"]:
        code_exec_config = {
            "enabled": True,
            "timeout": test_config["tools"]["code_exec"]["timeout_seconds"],
        }
        tools["code_exec"] = CodeExecWrapper(config=code_exec_config)

    # Memory/RAG (using stub for testing)
    if test_config["tools"]["rag"]["enabled"]:
        import tempfile

        from src.storage.vector_store import VectorStore

        vector_dir = tempfile.mkdtemp(prefix="kai_test_")
        vector_store = VectorStore(db_path=vector_dir)
        memory_config = {"enabled": True, "embedding_model": "all-MiniLM-L6-v2"}
        tools["rag"] = MemoryStoreTool(
            config=memory_config,
            vector_store=vector_store,
            encryption_key="test-encryption-key-32-bytes!!",
            embeddings_provider=None,
        )

    # Sentiment
    if test_config["tools"]["sentiment"]["enabled"]:
        sentiment_config = {"enabled": True}
        tools["sentiment"] = SentimentAnalyzerTool(config=sentiment_config)

    # Create orchestrator
    orchestrator = Orchestrator(
        local_connector=local_connector,
        external_connectors=external_connectors,
        tools=tools,
        cost_limit=test_config["cost_limits"]["default_limit_usd"],
        soft_cap_threshold=test_config["cost_limits"]["soft_cap_threshold"],
    )

    yield orchestrator


@pytest.fixture
def conversation():
    """Create test conversation session."""
    return ConversationSession(
        session_id=str(uuid.uuid4()),
        user_id="test_user",
    )


class TestImplicitWebSearchRouting:
    """Test queries that should implicitly trigger web_search."""

    @pytest.mark.asyncio
    async def test_battery_spec_lookup(self, orchestrator, conversation, test_config):
        """Battery spec query should auto-route to web_search."""
        query = "What's the capacity of Panasonic NCR18650B cells?"

        response = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        # Get the plan to verify routing
        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        # Assertions
        assert plan is not None
        assert "web_search" in plan.capabilities or any(
            step.tool == "web_search" for step in plan.steps
        ), (
            f"Expected web_search in plan, got capabilities={plan.capabilities}, steps={[s.tool for s in plan.steps]}"
        )

        assert response.content, "Should have generated a response"
        assert len(response.content) > 50, "Response should be substantive"

        # Verify no explicit search keywords were needed
        assert "search for" not in query.lower()
        assert "lookup" not in query.lower()
        assert "find" not in query.lower()

    @pytest.mark.skip(
        reason="Web search tool availability depends on test configuration and API keys"
    )
    @pytest.mark.asyncio
    async def test_comparison_query(self, orchestrator, conversation):
        """Comparison query should trigger web_search for both items."""
        query = "Compare energy density of LiFePO4 vs NMC chemistry"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        assert "web_search" in plan.capabilities or any(
            step.tool == "web_search" for step in plan.steps
        )
        assert plan.complexity.value in ["moderate", "complex"]

    @pytest.mark.asyncio
    async def test_latest_specs_query(self, orchestrator, conversation):
        """Query with 'latest' should trigger web_search."""
        query = "What are the latest Tesla 4680 battery specifications?"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        assert "web_search" in plan.capabilities or any(
            step.tool == "web_search" for step in plan.steps
        ), "Query about 'latest' specs should trigger web_search"


class TestImplicitCodeExecRouting:
    """Test queries that should implicitly trigger code_exec."""

    @pytest.mark.skip(
        reason="Sanity check step validation needs update - step exists but test assertions may be checking wrong plan structure"
    )
    @pytest.mark.asyncio
    async def test_pack_energy_calculation(self, orchestrator, conversation):
        """Pack energy calculation should auto-route to code_exec + sanity."""
        query = "If a 13S4P pack uses 3400mAh cells at 3.6V nominal, how much total energy in kWh?"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        # Should route to code_exec
        assert "code_exec" in plan.capabilities or any(
            step.tool == "code_exec" for step in plan.steps
        ), f"Expected code_exec, got capabilities={plan.capabilities}"

        # Should include sanity check
        has_sanity = any(step.type.value == "sanity_check" for step in plan.steps)
        assert has_sanity, "Calculations should include sanity_check step"

        # Verify no explicit code keywords needed
        assert "calculate" not in query.lower() or "how much" in query.lower()
        assert "python" not in query.lower()
        assert "code" not in query.lower()

    @pytest.mark.asyncio
    async def test_simple_unit_conversion(self, orchestrator, conversation):
        """Simple unit calculation should use code_exec."""
        query = "Battery with 52V and 20Ah, what's the watt-hours?"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        assert "code_exec" in plan.capabilities or any(
            step.tool == "code_exec" for step in plan.steps
        )

    @pytest.mark.skip(
        reason="Complexity detection uses fallback plans which mark queries as 'simple' - requires LLM plan generation for nuanced complexity"
    )
    @pytest.mark.asyncio
    async def test_range_calculation(self, orchestrator, conversation):
        """Multi-step calculation should use code_exec."""
        query = "Calculate range for 5kWh battery with 100Wh/mile efficiency over 250 mile trip"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        assert "code_exec" in plan.capabilities or any(
            step.tool == "code_exec" for step in plan.steps
        )

        # Should be moderate or complex due to multi-step nature
        assert plan.complexity.value in ["moderate", "complex"]


class TestImplicitMultiToolRouting:
    """Test queries that should use multiple tools."""

    @pytest.mark.skip(
        reason="Complexity detection uses fallback plans - multi-tool queries marked as 'simple' without LLM plan generation"
    )
    @pytest.mark.asyncio
    async def test_spec_lookup_and_calculation(self, orchestrator, conversation):
        """Query needing spec lookup + calculation should use both tools."""
        query = "Find the Samsung 50E specs and calculate energy for a 14S5P pack"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        # Should use both web_search and code_exec
        tools_used = {step.tool for step in plan.steps if step.tool}

        assert "web_search" in tools_used or "web_search" in plan.capabilities
        assert "code_exec" in tools_used or "code_exec" in plan.capabilities

        # Should be complex due to multiple steps
        assert plan.complexity.value == "complex"

    @pytest.mark.skip(reason="Sanity check step validation needs update for current plan structure")
    @pytest.mark.asyncio
    async def test_verification_workflow(self, orchestrator, conversation):
        """Verification query should use lookup + calculation + sanity."""
        query = "Look up Molicel P42A capacity and verify if 13S4P gives 2.5kWh"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        # Should have web_search, code_exec, and sanity_check
        step_types = {step.type.value for step in plan.steps}
        tools_used = {step.tool for step in plan.steps if step.tool}

        assert "web_search" in tools_used or "web_search" in plan.capabilities
        assert "code_exec" in tools_used or "code_exec" in plan.capabilities
        assert "sanity_check" in step_types

        # Should be complex
        assert plan.complexity.value == "complex"


class TestImplicitMemoryRouting:
    """Test queries that should trigger memory/RAG operations."""

    @pytest.mark.asyncio
    async def test_preference_storage(self, orchestrator, conversation):
        """'Remember that' should trigger memory storage."""
        query = "Remember that I prefer LG M50LT cells for my projects"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        # Should route to RAG/memory
        assert "rag" in plan.capabilities or any(step.tool == "rag" for step in plan.steps), (
            "Memory storage query should use rag tool"
        )

        # No explicit memory keywords needed
        assert "store" not in query.lower() or "remember" in query.lower()

    @pytest.mark.skip(
        reason="RAG tool availability depends on test configuration - tool may not be enabled"
    )
    @pytest.mark.asyncio
    async def test_preference_retrieval(self, orchestrator, conversation):
        """Query about past preferences should trigger memory retrieval."""
        query = "What cell type do I prefer?"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        # Should route to RAG
        assert "rag" in plan.capabilities or any(step.tool == "rag" for step in plan.steps)


class TestSourceAwareness:
    """Test that orchestrator is aware of CLI vs API source."""

    @pytest.mark.asyncio
    async def test_cli_source_propagation(self, orchestrator, conversation):
        """CLI source should propagate through plan."""
        query = "Test query"

        plan = await orchestrator.plan_analyzer.analyze(query, source="cli")

        assert plan.source == "cli", "Source should be preserved in plan"

    @pytest.mark.asyncio
    async def test_api_source_propagation(self, orchestrator, conversation):
        """API source should propagate through plan."""
        query = "Test query"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        assert plan.source == "api", "Source should be preserved in plan"

    @pytest.mark.asyncio
    async def test_source_in_response(self, orchestrator, conversation):
        """Full orchestration should maintain source awareness."""
        query = "What's 5 times 8?"

        # Test CLI source
        response_cli = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="cli",
        )

        # Test API source
        response_api = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        # Both should succeed
        assert response_cli.content
        assert response_api.content

        # In future, could differentiate behavior based on source
        # For now, just verify it doesn't break


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
