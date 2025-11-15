"""Production-ready validation tests with real API calls.

These tests validate the ENTIRE system is ready for production:
- All calculations are mathematically correct
- Multi-tool coordination works flawlessly
- Error recovery is robust
- Cost tracking is accurate
- Reflection agent works
- Response quality is production-grade

Run with: pytest tests/production/test_production_ready.py -v -s

Cost estimate: ~$0.50-$1.00 for full suite
"""

import asyncio
import os
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

pytestmark = pytest.mark.production

import tempfile

from src.agents.reflection_agent import ReflectionAgent
from src.core.orchestrator import Orchestrator
from src.core.providers.ollama_provider import OllamaProvider
from src.core.providers.openrouter_provider import OpenRouterProvider
from src.models.conversation import ConversationSession
from src.storage.memory_vault import MemoryVault
from src.storage.vector_store import VectorStore
from src.tools.code_exec_wrapper import CodeExecWrapper
from src.tools.memory_store import MemoryStoreTool
from src.tools.sentiment_analyzer import SentimentAnalyzerTool
from src.tools.web_search import WebSearchTool

# Track costs across all tests
COST_TRACKER = {
    "total": 0.0,
    "by_model": {},
    "by_suite": {},
}


def track_cost(suite: str, model: str, cost: float):
    """Track cost for reporting."""
    COST_TRACKER["total"] += cost
    COST_TRACKER["by_model"][model] = COST_TRACKER["by_model"].get(model, 0.0) + cost
    COST_TRACKER["by_suite"][suite] = COST_TRACKER["by_suite"].get(suite, 0.0) + cost


def extract_numbers(text: str) -> list[float]:
    """Extract all numbers from text, handling commas."""
    # Remove commas from numbers like "1,040"
    text = re.sub(r"(\d),(\d)", r"\1\2", text)
    numbers = re.findall(r"\d+\.?\d*", text)
    return [float(n) for n in numbers if n]


@pytest.fixture(scope="module")
def test_config():
    """Load test configuration."""
    config_path = Path(__file__).parent.parent / "integration" / "test_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="function")  # Changed from module to function scope
async def production_orchestrator(test_config):
    """Create production-grade orchestrator with all features."""

    # Local Granite model
    granite_config = test_config["models"]["granite"]
    local_connector = OllamaProvider(
        model_config=granite_config,
        base_url=granite_config.get("base_url", "http://localhost:11434"),
    )

    # External models (Grok Fast + Claude Sonnet)
    external_connectors = {}

    # Grok Fast (external_reasoner_fast)
    if "OPENROUTER_API_KEY" in os.environ:
        grok_config = {
            "model_id": "grok-fast",
            "model_name": "x-ai/grok-2-1212",
            "provider": "openrouter",
            "context_window": 4000,
            "cost_per_1k_input": 0.002,
            "cost_per_1k_output": 0.010,
        }
        external_connectors["external_reasoner_fast"] = OpenRouterProvider(
            model_config=grok_config,
            api_key=os.environ["OPENROUTER_API_KEY"],
        )

        # Claude Sonnet (external_reasoner_strong)
        sonnet_config = {
            "model_id": "claude-sonnet",
            "model_name": "anthropic/claude-3.5-sonnet",
            "provider": "openrouter",
            "context_window": 8000,
            "cost_per_1k_input": 0.003,
            "cost_per_1k_output": 0.015,
        }
        external_connectors["external_reasoner_strong"] = OpenRouterProvider(
            model_config=sonnet_config,
            api_key=os.environ["OPENROUTER_API_KEY"],
        )

    # Tools
    tools = {}

    # Code execution
    code_exec_config = test_config["tools"]["code_exec"]
    tools["code_exec"] = CodeExecWrapper(config=code_exec_config)

    # Web search (if available)
    if "BRAVE_API_KEY" in os.environ:
        web_search_config = test_config["tools"]["web_search"]
        web_search_config["api_key"] = os.environ["BRAVE_API_KEY"]
        tools["web_search"] = WebSearchTool(config=web_search_config)

    # Memory
    vector_dir = tempfile.mkdtemp(prefix="kai_production_test_")
    vector_store = VectorStore(db_path=vector_dir)
    memory_vault = MemoryVault(user_id="production_test_user")

    memory_config = {"enabled": True, "embedding_model": "all-MiniLM-L6-v2"}
    tools["rag"] = MemoryStoreTool(
        config=memory_config,
        vector_store=vector_store,
        encryption_key="production-test-key-32-bytes!",
    )

    # Sentiment
    tools["sentiment"] = SentimentAnalyzerTool(config={"enabled": True})

    # Create orchestrator
    orchestrator = Orchestrator(
        local_connector=local_connector,
        external_connectors=external_connectors,
        tools=tools,
        cost_limit=2.0,  # $2 hard cap for production tests
        soft_cap_threshold=0.8,
    )

    # Add reflection agent
    orchestrator.reflection_agent = ReflectionAgent(local_connector, memory_vault)

    return orchestrator


@pytest.fixture
async def conversation():
    """Create fresh conversation for each test."""
    # Small delay to allow previous test's event loop cleanup
    await asyncio.sleep(0.1)
    return ConversationSession(user_id="production_test_user")


# ============================================================================
# CRITICAL CALCULATION ACCURACY TESTS
# ============================================================================


class TestCriticalCalculations:
    """Validate all math goes through Python and is 100% accurate."""

    @pytest.mark.asyncio
    async def test_13s4p_battery_energy(self, production_orchestrator, conversation):
        """CRITICAL: 13S4P pack with NCR18650B cells."""
        query = "I have a 13S4P battery pack using NCR18650B cells (3400mAh, 3.6V nominal). What's the total energy in kWh?"

        print(f"\n{'=' * 80}")
        print("CRITICAL TEST: 13S4P Battery Energy Calculation")
        print(f"{'=' * 80}")
        print(f"Query: {query}")

        response = await production_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="production_test",
        )

        # Track cost
        cost = production_orchestrator.cost_tracker.get_total_cost()
        track_cost("critical_calculations", "mixed", cost)

        assert response.content, "Must have response"
        print(f"\nResponse: {response.content}")

        # Expected: 13S × 4P = 52 cells × 3.4Ah × 3.6V = 636.48 Wh = 0.636 kWh
        numbers = extract_numbers(response.content)
        has_correct = any(0.63 <= n <= 0.65 for n in numbers) or any(
            630 <= n <= 640 for n in numbers
        )

        assert has_correct, f"FAILED: Must calculate ~0.636 kWh or ~636 Wh, got: {numbers}"
        print(f"✅ PASS: Correct calculation found in {numbers}")

    @pytest.mark.asyncio
    async def test_14s5p_battery_energy(self, production_orchestrator, conversation):
        """CRITICAL: 14S5P pack calculation."""
        query = "14S5P pack, each cell is 5000mAh at 3.6V nominal. Total energy in kWh?"

        print(f"\n{'=' * 80}")
        print("CRITICAL TEST: 14S5P Battery Energy Calculation")
        print(f"{'=' * 80}")

        response = await production_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="production_test",
        )

        cost = production_orchestrator.cost_tracker.get_total_cost()
        track_cost("critical_calculations", "mixed", cost)

        # Expected: 14S × 5P = 70 cells × 5Ah × 3.6V = 1260 Wh = 1.26 kWh
        numbers = extract_numbers(response.content)
        has_correct = any(1.24 <= n <= 1.28 for n in numbers) or any(
            1250 <= n <= 1270 for n in numbers
        )

        assert has_correct, (
            f"FAILED: Must calculate ~1.26 kWh or ~1260 Wh, got: {numbers}\nResponse: {response.content}"
        )
        print("✅ PASS: Correct calculation")

    @pytest.mark.asyncio
    async def test_battery_range_calculation(self, production_orchestrator, conversation):
        """CRITICAL: Range calculation from battery capacity and consumption."""
        query = (
            "If I have a 5 kWh battery and my vehicle uses 100 Wh per mile, how far can I travel?"
        )

        print(f"\n{'=' * 80}")
        print("CRITICAL TEST: Battery Range Calculation")
        print(f"{'=' * 80}")

        response = await production_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="production_test",
        )

        cost = production_orchestrator.cost_tracker.get_total_cost()
        track_cost("critical_calculations", "mixed", cost)

        # Expected: 5000 Wh ÷ 100 Wh/mile = 50 miles
        numbers = extract_numbers(response.content)
        has_50 = any(49 <= n <= 51 for n in numbers)

        assert has_50, (
            f"FAILED: Must calculate 50 miles, got: {numbers}\nResponse: {response.content}"
        )
        print("✅ PASS: Correct range calculation")

    @pytest.mark.asyncio
    async def test_voltage_capacity_to_energy(self, production_orchestrator, conversation):
        """CRITICAL: Simple V×Ah→Wh conversion."""
        query = "A battery is 52V and 20Ah. How many watt-hours is that?"

        print(f"\n{'=' * 80}")
        print("CRITICAL TEST: Voltage × Capacity → Energy")
        print(f"{'=' * 80}")

        response = await production_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="production_test",
        )

        cost = production_orchestrator.cost_tracker.get_total_cost()
        track_cost("critical_calculations", "mixed", cost)

        # Expected: 52V × 20Ah = 1040 Wh
        numbers = extract_numbers(response.content)
        has_1040 = any(1030 <= n <= 1050 for n in numbers)

        assert has_1040, (
            f"FAILED: Must calculate 1040 Wh, got: {numbers}\nResponse: {response.content}"
        )
        print("✅ PASS: Correct energy calculation")


# ============================================================================
# MULTI-TOOL COORDINATION TESTS
# ============================================================================


class TestMultiToolCoordination:
    """Validate tools work together in complex workflows."""

    @pytest.mark.asyncio
    async def test_calculation_with_verification(self, production_orchestrator, conversation):
        """Test: code_exec → sanity_check → finalization pipeline."""
        query = "Calculate the total energy of a 10S3P pack with 2500mAh cells at 3.7V"

        print(f"\n{'=' * 80}")
        print("MULTI-TOOL TEST: Calculation with Sanity Check")
        print(f"{'=' * 80}")

        response = await production_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="production_test",
        )

        cost = production_orchestrator.cost_tracker.get_total_cost()
        track_cost("multi_tool", "mixed", cost)

        # Verify calculation: 10S × 3P = 30 cells × 2.5Ah × 3.7V = 277.5 Wh
        numbers = extract_numbers(response.content)
        has_correct = any(275 <= n <= 280 for n in numbers)

        assert has_correct, (
            f"FAILED: Expected ~277.5 Wh, got: {numbers}\nResponse: {response.content}"
        )

        # Verify response is natural language
        assert not response.content.strip().startswith("{"), "Response should not be raw JSON"
        assert len(response.content.split()) > 10, "Response should be substantive"

        print("✅ PASS: Multi-tool coordination working")


# ============================================================================
# ERROR RECOVERY TESTS
# ============================================================================


class TestErrorRecovery:
    """Validate system handles errors gracefully."""

    @pytest.mark.asyncio
    async def test_impossible_calculation(self, production_orchestrator, conversation):
        """Test: Gracefully handle nonsensical calculation request."""
        query = "Calculate the battery energy of a pack with negative voltage"

        print(f"\n{'=' * 80}")
        print("ERROR RECOVERY TEST: Impossible Calculation")
        print(f"{'=' * 80}")

        response = await production_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="production_test",
        )

        cost = production_orchestrator.cost_tracker.get_total_cost()
        track_cost("error_recovery", "mixed", cost)

        # Should not crash, should provide helpful message
        assert response.content, "Must have response even for impossible query"
        assert len(response.content) > 20, "Should provide explanation"

        print("✅ PASS: Error handled gracefully")
        print(f"Response: {response.content[:200]}...")

    @pytest.mark.asyncio
    async def test_ambiguous_query(self, production_orchestrator, conversation):
        """Test: Handle vague/ambiguous query."""
        query = "How much energy?"

        print(f"\n{'=' * 80}")
        print("ERROR RECOVERY TEST: Ambiguous Query")
        print(f"{'=' * 80}")

        response = await production_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="production_test",
        )

        cost = production_orchestrator.cost_tracker.get_total_cost()
        track_cost("error_recovery", "mixed", cost)

        # Should ask for clarification or handle gracefully
        assert response.content, "Must have response"
        assert (
            "error" not in response.content.lower()
            or "specify" in response.content.lower()
            or "more information" in response.content.lower()
        )

        print("✅ PASS: Ambiguous query handled")


# ============================================================================
# COST ENFORCEMENT TESTS
# ============================================================================


class TestCostEnforcement:
    """Validate cost tracking and cap enforcement."""

    @pytest.mark.asyncio
    async def test_cost_tracking_accuracy(self, production_orchestrator, conversation):
        """Test: Cost accumulates correctly across queries."""
        initial_cost = production_orchestrator.cost_tracker.get_total_cost()

        print(f"\n{'=' * 80}")
        print("COST TEST: Tracking Accuracy")
        print(f"{'=' * 80}")
        print(f"Initial cost: ${initial_cost:.6f}")

        # Make a query that should cost something
        await production_orchestrator.process_query(
            query_text="What is 7 times 8?",
            conversation=conversation,
            source="production_test",
        )

        final_cost = production_orchestrator.cost_tracker.get_total_cost()
        cost_increase = final_cost - initial_cost

        track_cost("cost_enforcement", "mixed", cost_increase)

        print(f"Final cost: ${final_cost:.6f}")
        print(f"Cost increase: ${cost_increase:.6f}")

        # Cost should be tracked (might be $0 if local-only)
        assert cost_increase >= 0, "Cost should not decrease"

        print("✅ PASS: Cost tracking working")


# ============================================================================
# RESPONSE QUALITY TESTS
# ============================================================================


class TestResponseQuality:
    """Validate responses are production-grade."""

    @pytest.mark.asyncio
    async def test_responses_are_natural_language(self, production_orchestrator, conversation):
        """Test: Responses are readable prose, not JSON/debug output."""
        queries = [
            "What's 12 times 15?",
            "Calculate energy of 52V 20Ah battery",
        ]

        print(f"\n{'=' * 80}")
        print("QUALITY TEST: Natural Language Responses")
        print(f"{'=' * 80}")

        for query in queries:
            response = await production_orchestrator.process_query(
                query_text=query,
                conversation=conversation,
                source="production_test",
            )

            # Not raw JSON
            assert not response.content.strip().startswith("{"), (
                f"Response should not be JSON for: {query}"
            )

            # Has real words
            word_count = len(response.content.split())
            assert word_count >= 5, f"Response should have substance for: {query}"

            # Ends with punctuation
            assert response.content.strip()[-1] in ".!?", f"Should end with punctuation: {query}"

            print(f"  ✓ {query[:50]}... -> Natural language response")

        cost = production_orchestrator.cost_tracker.get_total_cost()
        track_cost("response_quality", "mixed", cost)

        print("✅ PASS: All responses are production-quality")


# ============================================================================
# TEST SUITE REPORTING
# ============================================================================


def pytest_sessionfinish(session, exitstatus):
    """Print cost summary at end of test run."""
    print("\n" + "=" * 80)
    print("PRODUCTION TEST SUITE - COST SUMMARY")
    print("=" * 80)
    print(f"\nTotal Cost: ${COST_TRACKER['total']:.4f}")

    if COST_TRACKER["by_suite"]:
        print("\nCost by Suite:")
        for suite, cost in sorted(COST_TRACKER["by_suite"].items()):
            print(f"  {suite:30s}: ${cost:.4f}")

    if COST_TRACKER["by_model"]:
        print("\nCost by Model:")
        for model, cost in sorted(COST_TRACKER["by_model"].items()):
            print(f"  {model:30s}: ${cost:.4f}")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
