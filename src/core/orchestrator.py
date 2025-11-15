"""Main orchestrator for query routing and response generation."""

import logging
import time
import uuid
from typing import Any

from src.core.cost_tracker import CostTracker
from src.core.llm_connector import LLMConnector
from src.core.plan_analyzer import PlanAnalyzer
from src.core.plan_executor import PlanExecutor
from src.core.presenters.granite_presenter import GranitePresenter
from src.core.sanity_checker import SanityChecker
from src.core.specialists.verification import SpecialistVerifier
from src.models.conversation import ConversationSession
from src.models.response import Response
from src.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrates query processing with plan-execute-present pattern."""

    def __init__(
        self,
        local_connector: LLMConnector,
        external_connectors: dict[str, LLMConnector] | None = None,
        tools: dict[str, BaseTool] | None = None,
        cost_limit: float = 1.0,
        soft_cap_threshold: float = 0.8,
    ):
        """Initialize orchestrator.

        Args:
            local_connector: Local model connector (Ollama/Granite)
            external_connectors: Optional dict of external connectors
            tools: Optional dict of tool implementations
            cost_limit: Maximum cost limit in USD
            soft_cap_threshold: Percentage for soft cap warning (0.0-1.0)
        """
        self.local_connector = local_connector
        self.external_connectors = external_connectors or {}
        self.tools = tools or {}
        self.cost_tracker = CostTracker(cost_limit, soft_cap_threshold)
        self.conversation_service = None  # Will be injected by CLI/API

        # Core orchestration components
        self.plan_analyzer = PlanAnalyzer(self.local_connector)
        self.sanity_checker = SanityChecker()

        # Auto-detect specialist connectors
        fast_connector = None
        strong_connector = None

        for model_name, connector in self.external_connectors.items():
            if "grok" in model_name.lower() and not fast_connector:
                fast_connector = connector
            elif "claude" in model_name.lower() or "sonnet" in model_name.lower():
                strong_connector = connector

        self.specialist_verifier = SpecialistVerifier(
            fast_connector=fast_connector,
            strong_connector=strong_connector,
        )

        self.plan_executor = PlanExecutor(
            tools=self.tools,
            sanity_checker=self.sanity_checker,
            specialist_verifier=self.specialist_verifier,
        )

        # Presenter: ALWAYS use local model for user-facing text
        # External models (Grok) should only output JSON for planning
        # Local model handles natural language presentation
        logger.info("Using local model for presentation")
        self.presenter = GranitePresenter(self.local_connector)

    async def process_query(
        self,
        query_text: str,
        conversation: ConversationSession,
        source: str = "api",
        emotional_tone: dict[str, Any] | None = None,
    ) -> Response:
        """Process query using plan-execute-present orchestration.

        Flow:
        1. Analyzer (Granite) generates JSON execution plan
        2. Executor runs steps: tools → sanity → specialists
        3. Presenter (Granite) converts results to natural language

        Args:
            query_text: User's query
            conversation: Conversation session
            source: Source of query ("cli" or "api")
            emotional_tone: Optional emotional tone (unused currently)

        Returns:
            Response object with final answer
        """
        logger.info(
            f"🔍 QUERY START | session={conversation.session_id} | source={source} | "
            f"query_length={len(query_text)} | user={conversation.user_id}"
        )
        start_time = time.time()

        try:
            # Retrieve conversation history for context
            conversation_context = []
            if self.conversation_service:
                try:
                    messages = self.conversation_service.get_messages(
                        conversation.session_id,
                        limit=3  # Last 3 messages for plan context
                    )
                    conversation_context = messages
                    if conversation_context:
                        logger.info(f"Retrieved {len(conversation_context)} messages for plan context")
                except Exception as e:
                    logger.warning(f"Failed to get context for planning: {e}")
            
            # Step 1: Analyze → Plan
            plan = await self.plan_analyzer.analyze(
                query_text, 
                source=source,
                context={"conversation_history": conversation_context} if conversation_context else None
            )

            logger.info(
                f"📋 PLAN GENERATED | intent={plan.intent} | "
                f"complexity={plan.complexity.value} | "
                f"steps={len(plan.steps)} | "
                f"capabilities={plan.capabilities} | "
                f"safety_level={plan.safety_level.value}"
            )

            # Step 2: Execute → Results
            execution_results = await self.plan_executor.execute(plan)

            # Log tool and model usage
            tool_results = execution_results.get("tool_results", {})
            specialist_results = execution_results.get("specialist_results", {})

            # tool_results and specialist_results are dicts, not lists
            tools_used = (
                [
                    r.get("tool_name", "unknown") if isinstance(r, dict) else "unknown"
                    for r in tool_results.values()
                ]
                if isinstance(tool_results, dict)
                else []
            )
            models_used = (
                [
                    r.get("model", "unknown") if isinstance(r, dict) else "unknown"
                    for r in specialist_results.values()
                ]
                if isinstance(specialist_results, dict)
                else []
            )

            logger.info(
                f"⚙️  EXECUTION COMPLETE | "
                f"tools={len(tool_results)} {tools_used} | "
                f"specialists={len(specialist_results)} {models_used}"
            )

            # Retrieve conversation history if available
            conversation_history = []
            if self.conversation_service:
                try:
                    # Get last 10 messages for context (5 exchanges)
                    messages = self.conversation_service.get_messages(
                        conversation.session_id,
                        limit=10
                    )
                    # Format: [{role, content, timestamp}, ...]
                    conversation_history = messages
                    
                    # If we have more than 10 messages total, summarize older ones
                    if len(messages) >= 10:
                        # Get total message count
                        all_messages = self.conversation_service.get_messages(
                            conversation.session_id,
                            limit=None
                        )
                        
                        # If we have significantly more messages, add a summary
                        if len(all_messages) > 15:
                            summary = self._summarize_old_messages(all_messages[10:])
                            if summary:
                                # Prepend summary as a system message
                                conversation_history.insert(0, {
                                    "role": "system",
                                    "content": f"Earlier conversation summary: {summary}",
                                    "timestamp": all_messages[10].get("timestamp", "")
                                })
                    
                    logger.debug(f"Retrieved {len(conversation_history)} messages from conversation history")
                except Exception as e:
                    logger.warning(f"Failed to retrieve conversation history: {e}")

            # Step 3: Present → Answer
            final_output = await self.presenter.finalize(
                original_query=query_text,
                plan=plan.to_dict(),
                tool_results=execution_results["tool_results"],
                specialist_results=execution_results["specialist_results"],
                conversation_history=conversation_history,
            )

            elapsed_time = time.time() - start_time

            # Calculate estimated cost (will be more accurate with actual token counts)
            estimated_cost = (
                self.cost_tracker.get_total_cost() if hasattr(self, "cost_tracker") else 0.0
            )

            logger.info(
                f"✅ QUERY SUCCESS | "
                f"response_length={len(final_output.final_answer)} chars | "
                f"citations={len(final_output.citations_used)} | "
                f"time={elapsed_time:.2f}s | "
                f"cost=${estimated_cost:.4f} | "
                f"avg_speed={len(final_output.final_answer) / elapsed_time:.0f} chars/s"
            )

            # Build response
            return Response(
                query_id=str(uuid.uuid4()),
                mode="concise",
                content=final_output.final_answer,
                token_count=0,  # TODO: aggregate from execution
                cost=0.0,  # TODO: aggregate from execution
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(
                f"❌ QUERY FAILED | error={type(e).__name__} | "
                f"message={str(e)} | time={elapsed_time:.2f}s",
                exc_info=True,
            )

            return Response(
                query_id=str(uuid.uuid4()),
                mode="concise",
                content=(
                    "I encountered an issue processing your request. "
                    "Please try rephrasing your question or try again later."
                ),
                token_count=0,
                cost=0.0,
            )
    
    def _summarize_old_messages(self, old_messages: list[dict[str, Any]]) -> str | None:
        """Create a brief summary of older conversation messages.
        
        Args:
            old_messages: List of old messages to summarize
            
        Returns:
            Brief summary string or None
        """
        if not old_messages:
            return None
        
        # Simple extractive summary - get key topics
        topics = []
        for msg in old_messages:
            content = msg.get("content", "")
            # Extract key phrases (simple approach)
            if msg.get("role") == "user":
                # Look for user statements about themselves
                if "my" in content.lower():
                    topics.append(content[:100])  # First 100 chars
        
        if topics:
            return " | ".join(topics[:3])  # Max 3 topics
        
        return f"{len(old_messages)} earlier messages about various topics"

    async def check_health(self) -> dict[str, bool]:
        """Check health of orchestration components.

        Returns:
            Dict mapping component names to health status
        """
        health = {
            "local_model": False,
            "tools": len(self.tools) > 0,
            "external_models": len(self.external_connectors) > 0,
        }

        try:
            # Test local connector with simple query
            response = await self.local_connector.generate(
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10,
            )
            health["local_model"] = len(response.content) > 0
        except Exception as e:
            logger.error(f"Local model health check failed: {e}")

        return health

    def get_cost_summary(self, session_id: str | None = None) -> dict[str, Any]:
        """Get cost tracking summary.

        Args:
            session_id: Optional session to filter by

        Returns:
            Dict with cost statistics
        """
        return self.cost_tracker.get_cost_summary(session_id)
