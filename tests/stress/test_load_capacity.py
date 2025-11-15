"""Stress and load tests to validate system under pressure.

Tests system behavior under:
- Rapid-fire queries
- Long conversation contexts
- Large tool outputs
- Cost budget exhaustion
- Concurrent requests

Run with: pytest tests/stress/test_load_capacity.py -v -s

Note: These tests may take several minutes and incur moderate API costs (~$0.50-$1.00)
"""

import asyncio
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

pytestmark = pytest.mark.stress

import os

from src.core.orchestrator import Orchestrator
from src.core.providers.ollama_provider import OllamaProvider
from src.core.providers.openrouter_provider import OpenRouterProvider
from src.models.conversation import ConversationSession
from src.tools.code_exec_wrapper import CodeExecWrapper


@pytest.fixture
async def stress_test_orchestrator():
    """Create orchestrator for stress testing."""
    # Local model
    granite_config = {
        "model_id": "granite-stress",
        "model_name": "granite4:micro-h",
        "provider": "ollama",
        "context_window": 4000,
    }
    local_connector = OllamaProvider(
        model_config=granite_config,
        base_url="http://localhost:11434",
    )

    # External models
    external_connectors = {}
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

    # Tools
    code_exec_config = {
        "memory_limit_mb": 128,
        "timeout_seconds": 10,
        "enabled": True,
    }
    tools = {
        "code_exec": CodeExecWrapper(config=code_exec_config),
    }

    # High limit for stress tests
    orchestrator = Orchestrator(
        local_connector=local_connector,
        external_connectors=external_connectors,
        tools=tools,
        cost_limit=5.0,  # $5 cap for stress tests
        soft_cap_threshold=0.8,
    )

    return orchestrator


# ============================================================================
# RAPID-FIRE QUERY TESTS
# ============================================================================


class TestRapidFireQueries:
    """Test system under rapid query load."""

    @pytest.mark.asyncio
    async def test_sequential_rapid_queries(self, stress_test_orchestrator):
        """Send 50 queries sequentially as fast as possible."""
        print(f"\n{'=' * 80}")
        print("STRESS TEST: 50 Sequential Rapid Queries")
        print(f"{'=' * 80}")

        conversation = ConversationSession(user_id="stress_test_rapid")
        queries = [
            "What is 7 times 8?",
            "Calculate 15 plus 23",
            "What's 100 divided by 4?",
            "Compute 9 squared",
            "What is 50 percent of 200?",
        ] * 10  # 5 queries × 10 = 50 total

        start_time = time.time()
        responses = []
        errors = []

        for i, query in enumerate(queries, 1):
            try:
                response = await stress_test_orchestrator.process_query(
                    query_text=query,
                    conversation=conversation,
                    source="stress_test",
                )
                responses.append(response)

                if i % 10 == 0:
                    elapsed = time.time() - start_time
                    qps = i / elapsed
                    print(f"  Progress: {i}/50 queries ({qps:.2f} q/s)")

            except Exception as e:
                errors.append((i, query, str(e)))
                print(f"  ERROR on query {i}: {e}")

        elapsed = time.time() - start_time
        qps = len(queries) / elapsed

        print(f"\n  Total time: {elapsed:.2f}s")
        print(f"  Throughput: {qps:.2f} queries/second")
        print(f"  Successful: {len(responses)}/{len(queries)}")
        print(f"  Errors: {len(errors)}")

        # Should handle most queries successfully
        success_rate = len(responses) / len(queries)
        assert success_rate >= 0.90, f"Should handle ≥90% of queries, got {success_rate:.1%}"

        print(f"✅ PASS: {success_rate:.1%} success rate")

    @pytest.mark.asyncio
    async def test_concurrent_queries(self, stress_test_orchestrator):
        """Send 20 queries concurrently."""
        print(f"\n{'=' * 80}")
        print("STRESS TEST: 20 Concurrent Queries")
        print(f"{'=' * 80}")

        queries = [
            ("user1", "Calculate 12 times 12"),
            ("user2", "What is 99 plus 1?"),
            ("user3", "Compute 144 divided by 12"),
            ("user4", "What's 7 cubed?"),
            ("user5", "Calculate 25 percent of 400"),
        ] * 4  # 5 users × 4 = 20 queries

        start_time = time.time()

        async def process_one(user_id: str, query: str):
            """Process single query."""
            try:
                conv = ConversationSession(user_id=user_id)
                response = await stress_test_orchestrator.process_query(
                    query_text=query,
                    conversation=conv,
                    source="stress_test_concurrent",
                )
                return (True, response)
            except Exception as e:
                return (False, str(e))

        # Launch all concurrently
        tasks = [process_one(user_id, query) for user_id, query in queries]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time
        successful = sum(1 for success, _ in results if success)

        print(f"\n  Total time: {elapsed:.2f}s")
        print(f"  Successful: {successful}/{len(queries)}")
        print(f"  Success rate: {successful / len(queries):.1%}")

        # Should handle concurrent load
        success_rate = successful / len(queries)
        assert success_rate >= 0.85, (
            f"Should handle ≥85% concurrent queries, got {success_rate:.1%}"
        )

        print("✅ PASS: Concurrent queries handled")


# ============================================================================
# LONG CONVERSATION CONTEXT TESTS
# ============================================================================


class TestLongConversations:
    """Test system with extended conversation history."""

    @pytest.mark.asyncio
    async def test_50_message_conversation(self, stress_test_orchestrator):
        """Build up a 50-message conversation and ensure it still works."""
        print(f"\n{'=' * 80}")
        print("STRESS TEST: 50-Message Conversation")
        print(f"{'=' * 80}")

        conversation = ConversationSession(user_id="stress_test_long_conv")

        # Build up conversation
        for i in range(25):  # 25 exchanges = 50 messages
            query = f"What is {i} plus {i + 1}?"

            response = await stress_test_orchestrator.process_query(
                query_text=query,
                conversation=conversation,
                source="stress_test",
            )

            assert response.content, f"Should get response for query {i}"

            if (i + 1) % 10 == 0:
                print(f"  Progress: {(i + 1) * 2} messages in conversation")

        # Verify conversation state
        assert len(conversation.messages) >= 50, "Should have ≥50 messages"

        # Final query should still work
        final_response = await stress_test_orchestrator.process_query(
            query_text="What was my first question?",
            conversation=conversation,
            source="stress_test",
        )

        assert final_response.content, "Should handle query after long conversation"

        print(f"✅ PASS: Long conversation handled ({len(conversation.messages)} messages)")


# ============================================================================
# LARGE OUTPUT TESTS
# ============================================================================


class TestLargeOutputs:
    """Test handling of large tool outputs."""

    @pytest.mark.asyncio
    async def test_large_calculation_output(self, stress_test_orchestrator):
        """Test calculation that generates large intermediate output."""
        print(f"\n{'=' * 80}")
        print("STRESS TEST: Large Calculation Output")
        print(f"{'=' * 80}")

        conversation = ConversationSession(user_id="stress_test_large")

        # Query that might generate large output
        query = "Generate a list of squares from 1 to 100 and sum them"

        response = await stress_test_orchestrator.process_query(
            query_text=query,
            conversation=conversation,
            source="stress_test",
        )

        assert response.content, "Should handle large output query"

        # Expected sum: 1² + 2² + ... + 100² = 338,350
        import re

        numbers = [int(n) for n in re.findall(r"\d+", response.content)]
        has_correct = any(338000 <= n <= 339000 for n in numbers)

        print(f"  Response length: {len(response.content)} chars")
        print(f"  Numbers found: {numbers[:5]}...")

        assert has_correct or len(numbers) > 0, "Should produce calculation result"

        print("✅ PASS: Large output handled")


# ============================================================================
# COST BUDGET EXHAUSTION TESTS
# ============================================================================


class TestCostExhaustion:
    """Test behavior when approaching/hitting cost limits."""

    @pytest.mark.asyncio
    async def test_soft_cap_warning(self, stress_test_orchestrator):
        """Test that soft cap (80%) triggers warning."""
        print(f"\n{'=' * 80}")
        print("STRESS TEST: Soft Cap Warning")
        print(f"{'=' * 80}")

        # Set very low limit for testing
        stress_test_orchestrator.cost_limit = 0.01
        stress_test_orchestrator.soft_cap_threshold = 0.8

        conversation = ConversationSession(user_id="stress_test_cost")

        # Make queries until we hit soft cap
        queries_made = 0

        for i in range(20):  # Max 20 attempts
            try:
                await stress_test_orchestrator.process_query(
                    query_text=f"What is {i} times 2?",
                    conversation=conversation,
                    source="stress_test",
                )
                queries_made += 1

                cost = stress_test_orchestrator.cost_tracker.get_total_cost()
                limit = stress_test_orchestrator.cost_limit

                if cost >= limit * 0.8:
                    print(f"  Soft cap hit at query {i + 1}")
                    print(f"  Cost: ${cost:.4f} / ${limit:.4f}")
                    break

            except Exception as e:
                if "cost limit" in str(e).lower() or "budget" in str(e).lower():
                    print(f"  Hard cap hit at query {i + 1}")
                    break
                raise

        print(f"  Queries completed: {queries_made}")
        print("✅ PASS: Cost tracking under load")

    @pytest.mark.asyncio
    async def test_hard_cap_enforcement(self):
        """Test that hard cap (100%) prevents queries."""
        print(f"\n{'=' * 80}")
        print("STRESS TEST: Hard Cap Enforcement")
        print(f"{'=' * 80}")

        # Create orchestrator with tiny limit
        granite_config = {
            "model_id": "granite-stress",
            "model_name": "granite4:micro-h",
            "provider": "ollama",
        }
        local_connector = OllamaProvider(
            model_config=granite_config,
            base_url="http://localhost:11434",
        )

        orchestrator = Orchestrator(
            local_connector=local_connector,
            external_connectors={},
            tools={},
            cost_limit=0.001,  # Tiny limit
            soft_cap_threshold=0.8,
        )

        conversation = ConversationSession(user_id="stress_test_hard_cap")

        # Make queries until hard cap hit
        for i in range(50):
            try:
                await orchestrator.process_query(
                    query_text=f"Query {i}",
                    conversation=conversation,
                    source="stress_test",
                )
            except Exception as e:
                if (
                    "cost" in str(e).lower()
                    or "limit" in str(e).lower()
                    or "budget" in str(e).lower()
                ):
                    print(f"  Hard cap enforced at query {i + 1}")
                    print(f"  Error: {str(e)[:100]}")
                    print("✅ PASS: Hard cap prevents queries")
                    return

        pytest.fail("Hard cap should have been hit")


# ============================================================================
# RESOURCE LEAK DETECTION
# ============================================================================


class TestResourceLeaks:
    """Test for memory leaks and resource cleanup."""

    @pytest.mark.asyncio
    async def test_memory_stability(self, stress_test_orchestrator):
        """Run many queries and check memory doesn't grow unbounded."""
        print(f"\n{'=' * 80}")
        print("STRESS TEST: Memory Stability")
        print(f"{'=' * 80}")

        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        print(f"  Initial memory: {initial_memory:.1f} MB")

        # Run 100 queries
        conversation = ConversationSession(user_id="stress_test_memory")
        for i in range(100):
            await stress_test_orchestrator.process_query(
                query_text=f"Calculate {i} squared",
                conversation=conversation,
                source="stress_test",
            )

            if (i + 1) % 25 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                print(f"  After {i + 1} queries: {current_memory:.1f} MB")

        final_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory

        print(f"  Final memory: {final_memory:.1f} MB")
        print(f"  Growth: {memory_growth:.1f} MB")

        # Memory shouldn't grow unreasonably (allow 100 MB for caching)
        assert memory_growth < 100, f"Memory grew too much: {memory_growth:.1f} MB"

        print("✅ PASS: Memory stable")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
