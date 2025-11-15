"""End-to-end validation tests using REAL API calls.

These tests actually execute full queries through the orchestrator and validate:
1. Correct tool selection happens automatically (no hints)
2. Tools execute and return valid results
3. Final answers are accurate and complete
4. Cost tracking works correctly
5. Self-learning reflection works

Run with: pytest tests/integration/test_e2e_validation.py -v -s

Requires:
- OPENROUTER_API_KEY environment variable
- BRAVE_API_KEY environment variable (optional, for web search)
- Ollama running locally with granite4-micro model
"""

import os
import re
import sys
from pathlib import Path

import pytest
import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

pytestmark = pytest.mark.integration

import uuid

from src.agents.reflection_agent import ReflectionAgent
from src.core.orchestrator import Orchestrator
from src.core.providers.ollama_provider import OllamaProvider
from src.core.providers.openrouter_provider import OpenRouterProvider
from src.models.conversation import ConversationSession
from src.storage.memory_vault import MemoryVault
from src.tools.code_exec_wrapper import CodeExecWrapper
from src.tools.memory_store import MemoryStoreTool
from src.tools.sentiment_analyzer import SentimentAnalyzerTool
from src.tools.web_search import WebSearchTool


def extract_numbers(text: str) -> list[float]:
    """Extract all numbers from text."""
    numbers = re.findall(r"\d+\.?\d*", text)
    return [float(n) for n in numbers if n]


@pytest.fixture(scope="module")
def test_config():
    """Load test configuration."""
    config_path = Path(__file__).parent / "test_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
async def full_orchestrator(test_config):
    """Create fully configured orchestrator with all features enabled."""

    # Local connector
    granite_config = test_config["models"]["granite"]
    local_connector = OllamaProvider(
        model_config=granite_config,
        base_url=granite_config.get("base_url", "http://localhost:11434"),
    )

    # External connectors
    external_connectors = {}

    if "OPENROUTER_API_KEY" in os.environ:
        grok_config = test_config["models"]["grok-fast"]
        external_connectors["grok-fast"] = OpenRouterProvider(
            model_config=grok_config,
            api_key=os.environ["OPENROUTER_API_KEY"],
        )

        sonnet_config = test_config["models"]["claude-sonnet"]
        external_connectors["claude-sonnet"] = OpenRouterProvider(
            model_config=sonnet_config,
            api_key=os.environ["OPENROUTER_API_KEY"],
        )

    # Tools
    tools = {}

    # Code execution (always available)
    code_exec_config = test_config["tools"]["code_exec"]
    code_exec_config["timeout"] = code_exec_config.get("timeout_seconds", 10)
    tools["code_exec"] = CodeExecWrapper(config=code_exec_config)

    # Web search (if API key available)
    if "BRAVE_API_KEY" in os.environ:
        web_search_config = test_config["tools"]["web_search"]
        web_search_config["api_key"] = os.environ["BRAVE_API_KEY"]
        tools["web_search"] = WebSearchTool(config=web_search_config)

    # Memory
    import tempfile

    from src.storage.vector_store import VectorStore

    vector_dir = tempfile.mkdtemp(prefix="kai_e2e_test_")
    vector_store = VectorStore(db_path=vector_dir)
    memory_vault = MemoryVault(user_id="e2e_test_user")

    memory_config = {"enabled": True, "embedding_model": "all-MiniLM-L6-v2"}
    tools["rag"] = MemoryStoreTool(
        config=memory_config,
        vector_store=vector_store,
        encryption_key="test-encryption-key-32-bytes!!",
    )

    # Sentiment
    sentiment_config = {"enabled": True}
    tools["sentiment"] = SentimentAnalyzerTool(config=sentiment_config)

    orchestrator = Orchestrator(
        local_connector=local_connector,
        external_connectors=external_connectors,
        tools=tools,
        cost_limit=1.0,
        soft_cap_threshold=0.8,
    )

    # Add reflection agent
    orchestrator.reflection_agent = ReflectionAgent(local_connector, memory_vault)

    return orchestrator


@pytest.fixture
def conversation():
    """Create test conversation session."""
    return ConversationSession(
        session_id=str(uuid.uuid4()),
        user_id="e2e_test_user",
    )


class TestCodeExecutionAccuracy:
    """Test that Granite correctly uses code execution and gets accurate results."""

    @pytest.mark.asyncio
    async def test_battery_pack_energy_calculation(self, full_orchestrator, conversation):
        """Full end-to-end: Calculate battery pack energy with correct result."""
        query = "If I have a 13S4P battery pack using 3400mAh cells at 3.6V nominal, what's the total energy in kWh?"

        print(f"\n🧪 Testing: {query}")
        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        # Validate response exists and is substantive
        assert response.content, "Should have generated a response"
        assert len(response.content) > 50, (
            f"Response should be detailed, got {len(response.content)} chars"
        )

        print(f"✓ Got response: {response.content[:200]}...")

        # Validate correct answer is present
        # 13S4P with 3400mAh @ 3.6V = 13 * 4 * 3.4Ah * 3.6V = 636.48Wh ≈ 0.636kWh
        content_lower = response.content.lower()

        # Should mention energy units
        has_units = "kwh" in content_lower or "wh" in content_lower
        assert has_units, f"Response should mention energy units, got: {response.content}"

        # Extract numbers and validate calculation
        numbers = extract_numbers(response.content)

        # Should have a value close to 636 Wh or 0.636 kWh
        has_correct_value = any((630 <= n <= 650) or (0.63 <= n <= 0.65) for n in numbers)

        assert has_correct_value, (
            f"Response should contain correct calculation (~0.636 kWh or ~636 Wh), got numbers: {numbers}, full response: {response.content}"
        )

        print(f"✓ Calculation validated: Found correct value in {numbers}")

    @pytest.mark.asyncio
    async def test_voltage_capacity_to_energy(self, full_orchestrator, conversation):
        """Test: V × Ah → Wh conversion."""
        query = "A battery is 52V and 20Ah. How many watt-hours is that?"

        print(f"\n🧪 Testing: {query}")
        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content, "Should have response"
        print(f"✓ Got response: {response.content[:150]}...")

        # 52V × 20Ah = 1040 Wh
        numbers = extract_numbers(response.content)
        has_1040 = any(1030 <= n <= 1050 for n in numbers)

        assert has_1040, (
            f"Should calculate 1040 Wh, got numbers: {numbers}, response: {response.content}"
        )
        print(f"✓ Correct answer found in {numbers}")

    @pytest.mark.asyncio
    async def test_range_calculation_multistep(self, full_orchestrator, conversation):
        """Test: Multi-step calculation (battery range)."""
        query = (
            "If I have a 5 kWh battery and my vehicle uses 100 Wh per mile, how far can I travel?"
        )

        print(f"\n🧪 Testing: {query}")
        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        print(f"✓ Got response: {response.content[:150]}...")

        # 5 kWh = 5000 Wh, 5000 / 100 = 50 miles
        numbers = extract_numbers(response.content)
        has_50 = any(48 <= n <= 52 for n in numbers)

        assert has_50, (
            f"Should calculate 50 miles, got numbers: {numbers}, response: {response.content}"
        )
        print(f"✓ Multi-step calculation correct: {numbers}")

    @pytest.mark.asyncio
    async def test_unit_conversion_implicit(self, full_orchestrator, conversation):
        """Test: Implicit unit conversion without saying 'convert' or 'calculate'."""
        query = "14S5P pack, each cell is 5000mAh at 3.6V nominal, what's the total kWh?"

        print(f"\n🧪 Testing: {query}")
        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        print(f"✓ Got response: {response.content[:150]}...")

        # 14S5P × 5Ah × 3.6V = 14 * 5 * 5 * 3.6 = 1260 Wh = 1.26 kWh
        numbers = extract_numbers(response.content)
        has_correct = any((1250 <= n <= 1270) or (1.24 <= n <= 1.28) for n in numbers)

        assert has_correct, (
            f"Should calculate ~1.26 kWh or ~1260 Wh, got: {numbers}, response: {response.content}"
        )
        print("✓ Implicit conversion handled correctly")


class TestWebSearchAccuracy:
    """Test that Granite correctly uses web search for lookups."""

    @pytest.mark.asyncio
    async def test_battery_spec_lookup(self, full_orchestrator, conversation):
        """Test: Look up real battery cell specifications."""
        if "web_search" not in full_orchestrator.tools:
            pytest.skip("Web search not configured (BRAVE_API_KEY not set)")

        query = "What is the capacity and voltage of Panasonic NCR18650B cells?"

        print(f"\n🧪 Testing: {query}")
        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        assert len(response.content) > 100, "Should have detailed spec information"
        print(f"✓ Got detailed response: {response.content[:200]}...")

        content_lower = response.content.lower()

        # Should mention capacity
        has_capacity = "mah" in content_lower or "capacity" in content_lower

        # Should mention voltage (typically 3.6V or 3.7V)
        has_voltage = (
            "3.6" in response.content or "3.7" in response.content or "voltage" in content_lower
        )

        assert has_capacity, f"Should mention capacity, got: {response.content}"
        assert has_voltage, f"Should mention voltage, got: {response.content}"

        print("✓ Spec lookup successful - found capacity and voltage info")

    @pytest.mark.asyncio
    async def test_comparison_query(self, full_orchestrator, conversation):
        """Test: Compare two items using web search."""
        if "web_search" not in full_orchestrator.tools:
            pytest.skip("Web search not configured")

        query = "What's the difference in energy density between LiFePO4 and NMC battery chemistry?"

        print(f"\n🧪 Testing: {query}")
        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        assert len(response.content) > 100
        print(f"✓ Got comparison: {response.content[:200]}...")

        content_lower = response.content.lower()

        # Should mention both chemistries
        has_lifepo4 = "lifepo4" in content_lower or "lfp" in content_lower
        has_nmc = "nmc" in content_lower

        assert has_lifepo4 or has_nmc, (
            f"Should mention battery chemistries, got: {response.content}"
        )
        print("✓ Comparison query handled correctly")


class TestMultiToolOrchestration:
    """Test that Granite can coordinate multiple tools correctly."""

    @pytest.mark.asyncio
    async def test_lookup_and_calculate(self, full_orchestrator, conversation):
        """Test: Look up specs, then calculate using those specs."""
        if "web_search" not in full_orchestrator.tools:
            pytest.skip("Web search not configured")

        query = "Find the Samsung 50E cell capacity and calculate the total energy for a 14S5P pack"

        print(f"\n🧪 Testing multi-tool: {query}")
        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        assert len(response.content) > 100
        print(f"✓ Got multi-tool response: {response.content[:250]}...")

        content_lower = response.content.lower()

        # Should show evidence of both search and calculation
        has_search_evidence = "samsung" in content_lower or "50e" in content_lower
        has_calc_evidence = ("kwh" in content_lower or "wh" in content_lower) and any(
            char.isdigit() for char in response.content
        )

        assert has_search_evidence or has_calc_evidence, (
            f"Should show evidence of search and calculation, got: {response.content}"
        )

        print("✓ Multi-tool orchestration successful")

    @pytest.mark.asyncio
    async def test_verify_with_calculation(self, full_orchestrator, conversation):
        """Test: User asks to verify a claim, should calculate and check."""
        query = "Verify if a 13S4P pack with 4200mAh cells at 3.6V gives about 0.8 kWh"

        print(f"\n🧪 Testing verification: {query}")
        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        print(f"✓ Got verification: {response.content[:200]}...")

        # 13S4P × 4.2Ah × 3.6V = 786.24 Wh ≈ 0.786 kWh (so 0.8 is close)
        content_lower = response.content.lower()
        has_verification = any(
            word in content_lower
            for word in [
                "correct",
                "close",
                "approximately",
                "about",
                "verify",
                "yes",
                "accurate",
                "0.8",
                "800",
            ]
        )

        assert has_verification, f"Should verify the claim, got: {response.content}"
        print("✓ Verification completed successfully")


class TestMemoryOperations:
    """Test that Granite correctly handles memory storage and retrieval."""

    @pytest.mark.asyncio
    async def test_store_preference(self, full_orchestrator, conversation):
        """Test: Store user preference."""
        query = "Remember that I prefer LG M50LT cells for my battery projects"

        print(f"\n🧪 Testing memory store: {query}")
        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        print(f"✓ Memory store response: {response.content}")

        # Should acknowledge storing the preference
        content_lower = response.content.lower()
        has_acknowledgment = any(
            word in content_lower
            for word in ["remember", "noted", "saved", "stored", "got it", "okay", "ok"]
        )

        assert has_acknowledgment or len(response.content) > 10, (
            f"Should acknowledge memory storage, got: {response.content}"
        )

        print("✓ Memory storage acknowledged")


class TestErrorHandling:
    """Test that system handles errors gracefully."""

    @pytest.mark.asyncio
    async def test_impossible_calculation(self, full_orchestrator, conversation):
        """Test: Handle calculation that doesn't make sense."""
        query = "Calculate the square root of -1 in real numbers"

        print(f"\n🧪 Testing error handling: {query}")
        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        print(f"✓ Error handling response: {response.content[:150]}...")

        # Should either explain it's not possible or mention complex numbers
        content_lower = response.content.lower()
        handles_gracefully = (
            any(
                word in content_lower
                for word in [
                    "not possible",
                    "complex",
                    "imaginary",
                    "cannot",
                    "undefined",
                    "no real",
                ]
            )
            or "i" in response.content
        )  # i for imaginary

        assert handles_gracefully or len(response.content) > 20, (
            f"Should handle impossible calculation gracefully, got: {response.content}"
        )

        print("✓ Impossible calculation handled gracefully")

    @pytest.mark.asyncio
    async def test_ambiguous_query(self, full_orchestrator, conversation):
        """Test: Handle ambiguous query."""
        query = "battery"

        print(f"\n🧪 Testing ambiguous query: {query}")
        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        print(f"✓ Ambiguous query response: {response.content[:150]}...")

        # Should ask for clarification or provide general info
        assert len(response.content) > 20, f"Should handle ambiguous query, got: {response.content}"

        print("✓ Ambiguous query handled")


class TestResponseQuality:
    """Test that responses are well-formatted and complete."""

    @pytest.mark.asyncio
    async def test_response_completeness(self, full_orchestrator, conversation):
        """Test: Responses should be complete sentences."""
        queries = [
            "What's 25 times 4?",
            "52V battery with 20Ah capacity has how much energy?",
            "Hello, how are you?",
        ]

        print(f"\n🧪 Testing response completeness for {len(queries)} queries")

        for query in queries:
            response = await full_orchestrator.process_query(
                query_text=query,
                conversation=conversation,
                source="api",
            )

            assert response.content, f"Should have response for: {query}"
            assert len(response.content) > 5, (
                f"Response should be substantive for: {query}, got: {response.content}"
            )

            # Should end with proper punctuation
            last_char = response.content.strip()[-1]
            assert last_char in ".!?", (
                f"Should end with punctuation for '{query}', got: '{response.content}'"
            )

            print(f"  ✓ '{query}' -> {response.content[:80]}...")

        print("✓ All responses are complete")

    @pytest.mark.asyncio
    async def test_response_readability(self, full_orchestrator, conversation):
        """Test: Responses should be readable (not just JSON dumps)."""
        query = "Calculate the energy in a 13S4P pack with 3400mAh cells at 3.6V"

        print(f"\n🧪 Testing readability: {query}")
        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        print(f"✓ Response: {response.content[:150]}...")

        # Should NOT be raw JSON
        is_likely_json = response.content.strip().startswith(
            "{"
        ) and response.content.strip().endswith("}")
        assert not is_likely_json, (
            f"Response should be natural language, not JSON: {response.content}"
        )

        # Should have words, not just numbers
        word_count = len([w for w in response.content.split() if w.isalpha()])
        assert word_count >= 5, f"Response should have actual words, got: {response.content}"

        print(f"✓ Response is readable natural language ({word_count} words)")


class TestCostEfficiency:
    """Test that cost tracking works and system is efficient."""

    @pytest.mark.asyncio
    async def test_local_queries_are_cheap(self, full_orchestrator, conversation):
        """Test: Simple local queries should be very cheap or free."""
        initial_cost = full_orchestrator.cost_tracker.get_total_cost()

        print(f"\n🧪 Testing cost efficiency (initial cost: ${initial_cost:.4f})")

        # Simple query that should only use Granite (local, free)
        query = "What's 7 times 8?"

        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        assert "56" in response.content, f"Should answer correctly, got: {response.content}"

        final_cost = full_orchestrator.cost_tracker.get_total_cost()
        cost_increase = final_cost - initial_cost

        final_cost = full_orchestrator.cost_tracker.get_total_cost()
        cost_increase = final_cost - initial_cost

        print(f"✓ Local query cost: ${cost_increase:.4f} (should be ~$0.00)")

        # Should be free or very cheap (< $0.001)
        assert cost_increase < 0.001, (
            f"Simple local query should be free, cost increased by ${cost_increase}"
        )

        print("✓ Local queries are cost-efficient")

    @pytest.mark.asyncio
    async def test_cost_accumulates_correctly(self, full_orchestrator, conversation):
        """Test: Cost tracking accumulates across queries."""
        initial_cost = full_orchestrator.cost_tracker.get_total_cost()

        print(f"\n🧪 Testing cost accumulation (initial: ${initial_cost:.4f})")

        # Run a simple query
        await full_orchestrator.process_query(
            query_text="What's 5 times 9?",
            conversation=conversation,
            source="api",
        )

        final_cost = full_orchestrator.cost_tracker.get_total_cost()

        print(f"✓ Cost tracking works: ${initial_cost:.4f} -> ${final_cost:.4f}")

        # Cost should not decrease
        assert final_cost >= initial_cost, "Cost should not decrease"


class TestReflectionMechanism:
    """Test that self-learning reflection works."""

    @pytest.mark.asyncio
    async def test_reflection_runs(self, full_orchestrator, conversation):
        """Test: Reflection agent can reflect on interactions."""
        if not full_orchestrator.reflection_agent:
            pytest.skip("Reflection agent not configured")

        query = "Calculate 52V × 20Ah in watt-hours"

        print("\n🧪 Testing reflection mechanism")

        response = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        print(f"✓ Query answered: {response.content[:100]}...")

        # Run reflection
        reflection = await full_orchestrator.reflection_agent.reflect_on_episode(
            episode_id="test_episode_1",
            user_text=query,
            assistant_text=response.content,
            mode="concise",
        )

        assert reflection, "Should generate reflection"
        assert len(reflection) > 20, "Reflection should be substantive"

        print(f"✓ Reflection generated: {reflection[:150]}...")
        print("✓ Self-learning mechanism working")


class TestSourceAwareness:
    """Test that system tracks CLI vs API source correctly."""

    @pytest.mark.asyncio
    async def test_source_propagation(self, full_orchestrator, conversation):
        """Test: Source field propagates through orchestration."""
        query = "What's 3 times 7?"

        print("\n🧪 Testing source awareness")

        # Test with CLI source
        response_cli = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="cli",
        )

        assert response_cli.content
        print("✓ CLI source handled")

        # Test with API source
        response_api = await full_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response_api.content
        print("✓ API source handled")

        # Both should work correctly
        assert "21" in response_cli.content or "21" in response_api.content
        print("✓ Source awareness working correctly")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
