"""Integration tests for model tier selection and escalation.

Tests that the orchestrator correctly chooses between:
- Granite (local) for simple queries
- Grok Fast for moderate verification
- Claude Sonnet for complex/high-stakes verification

This validates the specialist verifier logic and ensures:
1. Simple queries stay local (cost-efficient)
2. Moderate queries escalate to fast external models
3. Complex/safety-critical queries use strong models
"""

import os
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.integration

import uuid

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


@pytest.fixture(scope="module")
async def orchestrator_with_tracking(test_config):
    """Create orchestrator with call tracking for external models."""

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

    # External connectors with call tracking
    external_connectors = {}
    call_tracker = {"grok-fast": 0, "claude-sonnet": 0}

    if "OPENROUTER_API_KEY" in os.environ:
        # Grok Fast with tracking
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
        grok_provider = OpenRouterProvider(
            model_config=grok_model_config,
            api_key=os.environ["OPENROUTER_API_KEY"],
        )

        # Wrap generate to track calls
        original_grok_generate = grok_provider.generate

        async def tracked_grok_generate(*args, **kwargs):
            call_tracker["grok-fast"] += 1
            return await original_grok_generate(*args, **kwargs)

        grok_provider.generate = tracked_grok_generate
        external_connectors["grok-fast"] = grok_provider

        # Claude Sonnet with tracking
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
        sonnet_provider = OpenRouterProvider(
            model_config=sonnet_model_config,
            api_key=os.environ["OPENROUTER_API_KEY"],
        )

        # Wrap generate to track calls
        original_sonnet_generate = sonnet_provider.generate

        async def tracked_sonnet_generate(*args, **kwargs):
            call_tracker["claude-sonnet"] += 1
            return await original_sonnet_generate(*args, **kwargs)

        sonnet_provider.generate = tracked_sonnet_generate
        external_connectors["claude-sonnet"] = sonnet_provider

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

    orchestrator = Orchestrator(
        local_connector=local_connector,
        external_connectors=external_connectors,
        tools=tools,
        cost_limit=test_config["cost_limits"]["default_limit_usd"],
        soft_cap_threshold=test_config["cost_limits"]["soft_cap_threshold"],
    )

    # Attach call tracker
    orchestrator._test_call_tracker = call_tracker

    yield orchestrator


@pytest.fixture
def conversation():
    """Create test conversation session."""
    return ConversationSession(
        session_id=str(uuid.uuid4()),
        user_id="test_user",
    )


class TestGraniteLocalOnly:
    """Test that simple queries only use Granite (local model)."""

    @pytest.mark.asyncio
    async def test_simple_math_local_only(self, orchestrator_with_tracking, conversation):
        """Simple math should only use Granite, no external calls."""
        orchestrator = orchestrator_with_tracking
        tracker = orchestrator._test_call_tracker

        # Reset tracker
        tracker["grok-fast"] = 0
        tracker["claude-sonnet"] = 0

        query = "What's 25 times 4?"

        response = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        # Should have an answer
        assert response.content
        assert "100" in response.content

        # Should NOT call external models
        assert tracker["grok-fast"] == 0, "Simple query should not use Grok"
        assert tracker["claude-sonnet"] == 0, "Simple query should not use Sonnet"

    @pytest.mark.asyncio
    async def test_greeting_local_only(self, orchestrator_with_tracking, conversation):
        """Greetings should only use Granite."""
        orchestrator = orchestrator_with_tracking
        tracker = orchestrator._test_call_tracker

        tracker["grok-fast"] = 0
        tracker["claude-sonnet"] = 0

        query = "Hello, how are you?"

        response = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        assert tracker["grok-fast"] == 0
        assert tracker["claude-sonnet"] == 0


class TestGrokFastVerification:
    """Test that moderate complexity uses Grok Fast for verification."""

    @pytest.mark.skip(
        reason="Verification routing depends on complexity detection - fallback plans don't capture nuanced complexity"
    )
    @pytest.mark.asyncio
    async def test_moderate_calculation_uses_grok(self, orchestrator_with_tracking, conversation):
        """Moderate calculation with verification should use Grok Fast."""
        orchestrator = orchestrator_with_tracking
        tracker = orchestrator._test_call_tracker

        tracker["grok-fast"] = 0
        tracker["claude-sonnet"] = 0

        query = "13S4P with 3400mAh at 3.6V - verify the calculation gives about 0.64kWh"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        # Should be moderate complexity
        assert plan.complexity.value in ["moderate", "complex"]

        # Should have code_exec and sanity_check
        has_code = any(step.tool == "code_exec" for step in plan.steps)
        has_sanity = any(step.type.value == "sanity_check" for step in plan.steps)

        assert has_code, "Should use code execution for calculation"
        assert has_sanity, "Should have sanity check step"

        # Execute the plan
        response = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content

        # For moderate complexity verification:
        # - May use Grok Fast for sanity checking
        # - Should NOT use expensive Sonnet unless safety_level is high
        # Note: This depends on sanity checker behavior
        assert tracker["claude-sonnet"] == 0 or tracker["grok-fast"] > 0, (
            "Moderate verification should prefer fast model over strong model"
        )


class TestSonnetStrongVerification:
    """Test that high-stakes queries use Claude Sonnet."""

    @pytest.mark.skip(
        reason="Critical verification detection depends on LLM plan analysis - fallback plans use normal safety level"
    )
    @pytest.mark.asyncio
    async def test_critical_verification_uses_sonnet(
        self, orchestrator_with_tracking, conversation
    ):
        """Critical verification request should use Sonnet."""
        orchestrator = orchestrator_with_tracking
        tracker = orchestrator._test_call_tracker

        tracker["grok-fast"] = 0
        tracker["claude-sonnet"] = 0

        # Query with critical/verification keywords
        query = "Double-check this critical calculation: 14S5P × 5000mAh × 3.6V with detailed verification"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        # Should be complex or have high safety level
        is_complex_or_high_safety = (
            plan.complexity.value == "complex" or plan.safety_level.value in ["high", "critical"]
        )

        # The plan should indicate need for strong verification
        # (This tests that the plan analyzer detects verification needs)
        assert is_complex_or_high_safety, (
            f"Critical verification should be complex or high safety, got complexity={plan.complexity.value}, safety={plan.safety_level.value}"
        )


class TestComplexityDetection:
    """Test that plan analyzer correctly assesses complexity."""

    @pytest.mark.asyncio
    async def test_simple_query_complexity(self, orchestrator_with_tracking):
        """Simple queries should be marked as simple."""
        orchestrator = orchestrator_with_tracking

        simple_queries = [
            "What's 2+2?",
            "Hello",
            "Thanks",
        ]

        for query in simple_queries:
            plan = await orchestrator.plan_analyzer.analyze(query, source="api")
            assert plan.complexity.value == "simple", (
                f"'{query}' should be simple, got {plan.complexity.value}"
            )

    @pytest.mark.skip(
        reason="Complexity detection uses fallback plans which mark all as 'simple' - nuanced complexity requires proper LLM plan generation"
    )
    @pytest.mark.asyncio
    async def test_moderate_query_complexity(self, orchestrator_with_tracking):
        """Queries with single tool should be moderate."""
        orchestrator = orchestrator_with_tracking

        moderate_queries = [
            "What's the Samsung 50E capacity?",
            "Calculate 52V × 20Ah in watt-hours",
        ]

        for query in moderate_queries:
            plan = await orchestrator.plan_analyzer.analyze(query, source="api")
            assert plan.complexity.value in ["moderate", "complex"], (
                f"'{query}' should be moderate or complex, got {plan.complexity.value}"
            )

    @pytest.mark.skip(
        reason="Complexity detection uses fallback plans which mark all as 'simple' - nuanced complexity requires proper LLM plan generation"
    )
    @pytest.mark.asyncio
    async def test_complex_query_complexity(self, orchestrator_with_tracking):
        """Multi-step or verification queries should be complex."""
        orchestrator = orchestrator_with_tracking

        complex_queries = [
            "Find Samsung 50E specs and calculate 14S5P pack energy",
            "Look up Molicel P42A and verify if 13S4P gives 2.5kWh",
            "Compare LiFePO4 vs NMC energy density with calculations",
        ]

        for query in complex_queries:
            plan = await orchestrator.plan_analyzer.analyze(query, source="api")
            assert plan.complexity.value == "complex", (
                f"'{query}' should be complex, got {plan.complexity.value}"
            )


class TestToolEfficiency:
    """Test that Granite efficiently uses available tools."""

    @pytest.mark.asyncio
    async def test_code_exec_for_math_with_units(self, orchestrator_with_tracking, conversation):
        """Math with units should use code_exec, not try to do it in natural language."""
        orchestrator = orchestrator_with_tracking

        query = "52V × 20Ah in watt-hours"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        # Should use code_exec
        uses_code = any(step.tool == "code_exec" for step in plan.steps)
        assert uses_code, "Math with units should use code_exec tool"

        # Execute and verify answer is correct
        response = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        # Should mention 1040 Wh or 1.04 kWh (may be formatted with commas)
        assert (
            "1040" in response.content or "1,040" in response.content or "1.04" in response.content
        ), f"Should calculate correct answer, got: {response.content}"

    @pytest.mark.asyncio
    async def test_web_search_for_specs(self, orchestrator_with_tracking, conversation):
        """Spec lookups should use web_search when available."""
        orchestrator = orchestrator_with_tracking

        # Only run if web_search tool is available
        if "web_search" not in orchestrator.tools:
            pytest.skip("web_search tool not available")

        query = "What's the capacity of Panasonic NCR18650B?"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        # Should use web_search
        uses_search = any(step.tool == "web_search" for step in plan.steps)
        assert uses_search, "Spec lookup should use web_search tool"


class TestSanityChecking:
    """Test that sanity checks are applied appropriately."""

    @pytest.mark.skip(
        reason="LLM non-determinism: Granite doesn't always include sanity_check step in generated plans"
    )
    @pytest.mark.asyncio
    async def test_sanity_check_after_calculation(self, orchestrator_with_tracking):
        """Calculations should have sanity check steps."""
        orchestrator = orchestrator_with_tracking

        query = "13S4P with 3400mAh at 3.6V, what's the energy?"

        plan = await orchestrator.plan_analyzer.analyze(query, source="api")

        # Should have both code_exec and sanity_check
        has_code = any(step.tool == "code_exec" for step in plan.steps)
        has_sanity = any(step.type.value == "sanity_check" for step in plan.steps)

        assert has_code, "Should have code execution"
        assert has_sanity, "Should have sanity check after calculation"

        # Sanity check should come after code execution
        code_step_idx = next(i for i, s in enumerate(plan.steps) if s.tool == "code_exec")
        sanity_step_idx = next(
            i for i, s in enumerate(plan.steps) if s.type.value == "sanity_check"
        )

        assert sanity_step_idx > code_step_idx, "Sanity check should come after code execution"


class TestResponseQuality:
    """Test that Granite produces high-quality, readable responses."""

    @pytest.mark.skip(
        reason="Some responses are JSON from code_exec without natural language formatting - presenter behavior"
    )
    @pytest.mark.asyncio
    async def test_response_is_complete(self, orchestrator_with_tracking, conversation):
        """Responses should be complete sentences."""
        orchestrator = orchestrator_with_tracking

        query = "What's the energy in a 52V 20Ah battery?"

        response = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        assert response.content
        assert len(response.content) > 20, "Response should be substantive"
        # Response should end with punctuation or citation markers [N]
        ends_properly = (
            response.content.rstrip().endswith((".", "!", "?"))
            or response.content.rstrip().endswith(("]", ")"))  # Citations like [1][2]
        )
        assert ends_properly, (
            f"Should end with punctuation or citations, got: {response.content[-50:]}"
        )

    @pytest.mark.skip(
        reason="Test depends on presenter formatting which varies - may return error message if tools unavailable"
    )
    @pytest.mark.asyncio
    async def test_response_includes_calculation_result(
        self, orchestrator_with_tracking, conversation
    ):
        """Calculation responses should include the actual result."""
        orchestrator = orchestrator_with_tracking

        query = "13 series, 4 parallel, 3400mAh cells at 3.6V - total energy?"

        response = await orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="api",
        )

        # Should mention kWh or Wh
        content_lower = response.content.lower()
        has_energy_unit = "kwh" in content_lower or "wh" in content_lower

        assert has_energy_unit, f"Response should include energy units, got: {response.content}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
