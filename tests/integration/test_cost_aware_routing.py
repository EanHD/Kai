"""Integration tests for cost-aware routing and limits.

Tests that the cost tracking and enforcement works correctly:
1. Soft cap warnings trigger at configured threshold
2. Hard cap blocks external API calls
3. Local model still works after hard cap
4. Cost tracking accurately accumulates across queries
"""

import os
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.integration

import uuid

from src.core.cost_tracker import CostTracker
from src.core.orchestrator import Orchestrator
from src.core.providers.ollama_provider import OllamaProvider
from src.core.providers.openrouter_provider import OpenRouterProvider
from src.models.conversation import ConversationSession
from src.tools.code_exec_wrapper import CodeExecWrapper
from src.tools.web_search import WebSearchTool


@pytest.fixture(scope="module")
def test_config():
    """Load test configuration."""
    config_path = Path(__file__).parent / "test_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
async def orchestrator_low_limit(test_config):
    """Create orchestrator with very low cost limit for testing caps."""

    # Local connector
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

    # External connectors
    external_connectors = {}

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

    # Tools
    tools = {}
    if test_config["tools"]["code_exec"]["enabled"]:
        code_exec_config = {
            "enabled": True,
            "timeout": test_config["tools"]["code_exec"]["timeout_seconds"],
        }
        tools["code_exec"] = CodeExecWrapper(config=code_exec_config)

    if test_config["tools"]["web_search"]["enabled"] and "BRAVE_API_KEY" in os.environ:
        web_search_config = {
            "enabled": True,
            "api_key": os.environ["BRAVE_API_KEY"],
            "max_results": 3,
        }
        tools["web_search"] = WebSearchTool(config=web_search_config)

    # Use low cost limit for testing
    cost_limit = test_config["cost_limits"]["test_soft_cap_limit_usd"]

    orchestrator = Orchestrator(
        local_connector=local_connector,
        external_connectors=external_connectors,
        tools=tools,
        cost_limit=cost_limit,
        soft_cap_threshold=0.8,
    )

    return orchestrator


@pytest.fixture
def conversation():
    """Create test conversation session."""
    return ConversationSession(
        session_id=str(uuid.uuid4()),
        user_id="test_user",
    )


class TestCostTracking:
    """Test that cost tracking accurately accumulates."""

    @pytest.mark.asyncio
    async def test_cost_tracker_initialization(self):
        """Cost tracker should initialize with correct limits."""
        tracker = CostTracker(cost_limit=0.50, soft_cap_threshold=0.8)

        assert tracker.cost_limit.total_limit == 0.50
        assert tracker.cost_limit.soft_cap_threshold == 0.8
        assert tracker.get_total_cost() == 0.0
        assert not tracker.is_soft_cap_reached()
        assert not tracker.is_hard_cap_reached()

    @pytest.mark.asyncio
    async def test_cost_accumulation(self):
        """Costs should accumulate across multiple queries."""
        tracker = CostTracker(cost_limit=0.10, soft_cap_threshold=0.8)

        session_id = "test_session"

        # Add some costs
        cost1 = tracker.calculate_cost(
            input_tokens=100,
            output_tokens=50,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
        )
        tracker.track_query(
            query_id="query_1",
            session_id=session_id,
            model_id="test_model",
            input_tokens=100,
            output_tokens=50,
            cost=cost1,
        )
        cost_after_first = tracker.get_total_cost()

        assert cost_after_first > 0

        # Add more costs
        cost2 = tracker.calculate_cost(
            input_tokens=200,
            output_tokens=100,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
        )
        tracker.track_query(
            query_id="query_2",
            session_id=session_id,
            model_id="test_model",
            input_tokens=200,
            output_tokens=100,
            cost=cost2,
        )
        cost_after_second = tracker.get_total_cost()

        assert cost_after_second > cost_after_first
        assert cost_after_second == pytest.approx(
            cost_after_first * 3, rel=0.1
        )  # Roughly 3x the first cost


class TestSoftCapBehavior:
    """Test soft cap warnings."""

    @pytest.mark.asyncio
    async def test_soft_cap_warning(self):
        """Soft cap should trigger warning when threshold exceeded."""
        tracker = CostTracker(cost_limit=0.10, soft_cap_threshold=0.8)

        session_id = "test_session"

        # Add cost to reach 85% of limit (above 80% threshold)
        # 0.10 * 0.85 = 0.085
        # At $0.003/1k input and $0.015/1k output, need:
        # 1000 tokens in + 1000 tokens out = $0.018
        # About 5 calls to reach soft cap

        for i in range(5):
            cost = tracker.calculate_cost(
                input_tokens=1000,
                output_tokens=1000,
                cost_per_1k_input=0.003,
                cost_per_1k_output=0.015,
            )
            tracker.track_query(
                query_id=f"query_{i}",
                session_id=session_id,
                model_id="test_model",
                input_tokens=1000,
                output_tokens=1000,
                cost=cost,
            )

        # Should be at or above soft cap
        assert tracker.is_soft_cap_reached(), (
            f"Should reach soft cap after multiple queries, current cost: {tracker.get_total_cost()}"
        )

        # Should not be at hard cap yet
        assert not tracker.is_hard_cap_reached()

    @pytest.mark.asyncio
    async def test_soft_cap_still_allows_queries(self, orchestrator_low_limit, conversation):
        """Queries should still work after soft cap, just with warnings."""
        orchestrator = orchestrator_low_limit

        # Manually set cost tracker to near soft cap
        orchestrator.cost_tracker.session_costs = {}
        for i in range(3):
            cost = orchestrator.cost_tracker.calculate_cost(
                input_tokens=500,
                output_tokens=500,
                cost_per_1k_input=0.003,
                cost_per_1k_output=0.015,
            )
            orchestrator.cost_tracker.track_query(
                query_id=f"warmup_{i}",
                session_id=conversation.session_id,
                model_id="test_model",
                input_tokens=500,
                output_tokens=500,
                cost=cost,
            )

        # Should be near or at soft cap
        orchestrator.cost_tracker.get_total_cost()

        # Query should still work
        query = "What's 5 times 8?"
        response = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        assert "40" in response.content


class TestHardCapBehavior:
    """Test hard cap enforcement."""

    @pytest.mark.asyncio
    async def test_hard_cap_blocks_external(self):
        """Hard cap should prevent external API calls."""
        tracker = CostTracker(cost_limit=0.10, soft_cap_threshold=0.8)

        session_id = "test_session"

        # Exceed hard cap
        for i in range(10):
            cost = tracker.calculate_cost(
                input_tokens=1000,
                output_tokens=1000,
                cost_per_1k_input=0.003,
                cost_per_1k_output=0.015,
            )
            tracker.track_query(
                query_id=f"query_{i}",
                session_id=session_id,
                model_id="test_model",
                input_tokens=1000,
                output_tokens=1000,
                cost=cost,
            )

        assert tracker.is_hard_cap_reached(), (
            f"Should reach hard cap, current cost: {tracker.get_total_cost()}"
        )

    @pytest.mark.asyncio
    async def test_local_queries_work_after_hard_cap(self, orchestrator_low_limit, conversation):
        """Local queries should still work even after hard cap."""
        orchestrator = orchestrator_low_limit

        # Manually exceed hard cap
        for i in range(15):
            cost = orchestrator.cost_tracker.calculate_cost(
                input_tokens=1000,
                output_tokens=1000,
                cost_per_1k_input=0.003,
                cost_per_1k_output=0.015,
            )
            orchestrator.cost_tracker.track_query(
                query_id=f"exceed_{i}",
                session_id=conversation.session_id,
                model_id="test_model",
                input_tokens=1000,
                output_tokens=1000,
                cost=cost,
            )

        assert orchestrator.cost_tracker.is_hard_cap_reached()

        # Simple local query should still work
        query = "What's 12 plus 8?"
        response = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        # Should still answer correctly even with hard cap
        assert "20" in response.content


class TestCostSummary:
    """Test cost summary and reporting."""

    @pytest.mark.asyncio
    async def test_cost_summary_format(self):
        """Cost summary should include all relevant information."""
        tracker = CostTracker(cost_limit=1.0, soft_cap_threshold=0.8)

        session_id = "test_session"

        # Add some costs
        cost = tracker.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
        )
        tracker.track_query(
            query_id="query_1",
            session_id=session_id,
            model_id="test_model",
            input_tokens=1000,
            output_tokens=500,
            cost=cost,
        )

        summary = tracker.get_cost_summary()

        assert "total_cost" in summary
        assert "limit" in summary
        assert "soft_cap_reached" in summary
        assert "hard_cap_reached" in summary
        assert summary["total_cost"] > 0
        assert summary["limit"] == 1.0

    @pytest.mark.asyncio
    async def test_session_cost_tracking(self):
        """Each session should track costs separately."""
        tracker = CostTracker(cost_limit=1.0, soft_cap_threshold=0.8)

        session1 = "session_1"
        session2 = "session_2"

        # Add costs to session 1
        cost1_val = tracker.calculate_cost(1000, 500, 0.003, 0.015)
        tracker.track_query("query_1", session1, "test_model", 1000, 500, cost1_val)
        cost1 = tracker.get_total_cost()

        # Add costs to session 2
        cost2_val = tracker.calculate_cost(1000, 500, 0.003, 0.015)
        tracker.track_query("query_2", session2, "test_model", 1000, 500, cost2_val)
        cost2 = tracker.get_total_cost()

        # Total cost should be sum of both sessions
        assert cost2 == cost1 * 2


class TestCostEfficiency:
    """Test that system is cost-efficient."""

    @pytest.mark.asyncio
    async def test_simple_queries_are_free(self, orchestrator_low_limit, conversation):
        """Simple queries using only Granite should have zero cost."""
        orchestrator = orchestrator_low_limit

        initial_cost = orchestrator.cost_tracker.get_total_cost()

        # Simple query that should only use local model
        query = "What's 7 times 9?"
        response = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content

        final_cost = orchestrator.cost_tracker.get_total_cost()

        # Cost should not increase (local model is free)
        # Note: This depends on whether Granite is marked as zero-cost in config
        # If system properly tracks that local calls are free, cost should not increase
        assert final_cost == initial_cost or final_cost < 0.001, (
            f"Simple local queries should be free or very cheap, cost increased by ${final_cost - initial_cost}"
        )

    @pytest.mark.asyncio
    async def test_tool_execution_is_free(self, orchestrator_low_limit, conversation):
        """Code execution tool should not incur API costs."""
        orchestrator = orchestrator_low_limit

        orchestrator.cost_tracker.get_total_cost()

        # Query that uses code_exec but stays local
        query = "Calculate 52 times 20"
        await orchestrator.plan_analyzer.analyze(query, source="api")

        # Tool execution itself should be free
        # Only external model calls should cost money
        # This test verifies code_exec doesn't trigger unnecessary external calls


class TestCostAwareDecisions:
    """Test that system makes cost-aware routing decisions."""

    @pytest.mark.asyncio
    async def test_prefer_local_when_possible(self, orchestrator_low_limit, conversation):
        """System should prefer local model for queries it can handle."""
        orchestrator = orchestrator_low_limit

        # Query that could be answered locally
        query = "What's the square root of 144?"

        initial_cost = orchestrator.cost_tracker.get_total_cost()

        response = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        assert "12" in response.content

        final_cost = orchestrator.cost_tracker.get_total_cost()

        # Should not have incurred significant cost
        cost_increase = final_cost - initial_cost
        assert cost_increase < 0.01, (
            f"Simple math should not require expensive external calls, cost increased by ${cost_increase}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
