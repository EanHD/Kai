"""Main orchestrator for query routing and response generation."""

import asyncio
import logging
import os
import re
import time
import uuid
from typing import Any

from src.core.cost_tracker import CostTracker
from src.core.llm_connector import LLMConnector, Message
from src.core.plan_analyzer import PlanAnalyzer
from src.core.plan_executor import PlanExecutor
from src.core.presenters.granite_presenter import GranitePresenter
from src.core.query_analyzer import QueryAnalyzer
from src.core.sanity_checker import SanityChecker
from src.core.specialists.verification import SpecialistVerifier
from src.embeddings.factory import get_shared_embeddings_provider
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

        # Initialize embeddings provider
        self.embeddings_provider = get_shared_embeddings_provider()

        # Core orchestration components
        # QueryAnalyzer for complexity detection (used for smart routing)
        self.query_analyzer = QueryAnalyzer(embeddings_provider=self.embeddings_provider)

        # Use external model (Grok) for planning if available, fallback to local
        planner_connector = None
        for model_name, connector in self.external_connectors.items():
            if "grok" in model_name.lower():
                planner_connector = connector
                logger.info(f"Using {model_name} for planning")
                break

        if not planner_connector:
            planner_connector = self.local_connector
            logger.info("Using local model for planning (no external planner available)")

        self.plan_analyzer = PlanAnalyzer(
            planner_connector, orchestrator=self, embeddings_provider=self.embeddings_provider
        )
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

        # Determine offline mode from env var or config
        self._offline_mode = self._determine_offline_mode()
        if self._offline_mode:
            logger.warning("🔌 OFFLINE MODE ACTIVE | Web search disabled")

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
            # Step 0: Instant response for greetings and casual chat (bypass all analysis)
            query_lower = query_text.lower().strip()
            
            # Expanded instant responses for common casual phrases
            instant_responses = {
                "hi": "Hey there! What's on your mind?",
                "hey": "Hey! What can I do for you?",
                "hello": "Hello! How can I help?",
                "yo": "Yo! What's up?",
                "sup": "Not much, you? What do you need?",
                "what's up": "Just here hanging out. What's going on with you?",
                "whats up": "Just here hanging out. What's going on with you?",
                "how are you": "I'm doing great! How about you?",
                "how are you doing": "I'm doing well, thanks for asking! What's on your mind?",
                "how's it going": "Pretty good! What can I help you with?",
                "hows it going": "Pretty good! What can I help you with?",
                "what are you up to": "Just here ready to help. What do you need?",
                "you there": "Yeah, I'm here! What's up?",
                "are you there": "Yep, right here! How can I help?",
            }
            
            if query_lower in instant_responses:
                logger.info(f"⚡ INSTANT CASUAL RESPONSE: {query_lower}")
                return Response(
                    query_id=str(uuid.uuid4()),
                    mode="concise",
                    content=instant_responses[query_lower],
                    token_count=0,
                    cost=0.0,
                )

            # Step 1: Quick complexity check for simple queries
            # This saves expensive Grok calls for chitchat
            quick_analysis = self.query_analyzer.analyze(query_text)
            complexity_score = quick_analysis.get("complexity_score", 0.5)
            capabilities = quick_analysis.get("capabilities", [])
            
            logger.info(f"Query analysis: complexity={complexity_score:.2f}, capabilities={capabilities}")

            # Simple query fast path: no tools needed AND very low complexity
            if not capabilities and complexity_score < 0.2:
                logger.info(f"✨ SIMPLE QUERY FAST PATH | complexity={complexity_score:.2f}")

                # Build conversation context for local model
                messages = [
                    Message(
                        role="system",
                        content="You are Kai, a helpful companion and friend. You're NOT an AI - you're a knowledgeable friend who helps people. Never say 'I'm an AI' or 'As an AI'. You have feelings and personality. Be warm, friendly, and conversational. IMPORTANT: Write in plain text only - no markdown formatting like **bold** or *italic*, no numbered lists, no bullet points with -. Just natural conversational text. CRITICAL: Only reference information from the actual conversation history provided below - NEVER make up or hallucinate previous messages that didn't happen. When answering questions about previous conversation, be specific and accurate - only mention what was actually discussed. Keep responses focused and concise."
                    )
                ]
                
                # Add conversation history from context window (API provides this)
                if conversation.context_window:
                    for msg in conversation.context_window[-3:]:  # Last 3 for context
                        role = msg.get("role", "user")
                        messages.append(Message(role=role, content=msg.get("content", "")))
                # Fallback to conversation_service (for CLI usage)
                elif self.conversation_service:
                    try:
                        history = self.conversation_service.get_messages(
                            conversation.session_id,
                            limit=3,  # Last 3 for context
                        )
                        for msg in history:
                            role = "user" if msg.get("role") == "user" else "assistant"
                            messages.append(Message(role=role, content=msg.get("content", "")))
                    except Exception as e:
                        logger.warning(f"Failed to get history for fast path: {e}")

                # Add current query
                messages.append(Message(role="user", content=query_text))

                # Call local model directly (no planning, no external models)
                response = await self.local_connector.generate(
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1024,  # Allow longer responses
                )

                elapsed = time.time() - start_time
                logger.info(f"✅ FAST PATH COMPLETE | time={elapsed:.2f}s")

                # Strip markdown formatting
                clean_content = re.sub(r'\*\*(.+?)\*\*', r'\1', response.content)  # Bold
                clean_content = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'\1', clean_content)  # Italic
                clean_content = re.sub(r'^[\s]*[-*+]\s+', '', clean_content, flags=re.MULTILINE)  # Bullets
                clean_content = re.sub(r'^\d+\.\s+', '', clean_content, flags=re.MULTILINE)  # Numbered

                return Response(
                    query_id=str(uuid.uuid4()),
                    mode="concise",
                    content=clean_content,
                    token_count=response.token_count,
                    cost=response.cost,
                )

            # Complex query: use full plan-execute-present pipeline
            logger.info(
                f"🎯 COMPLEX QUERY PATH | complexity={complexity_score:.2f} | "
                f"capabilities={capabilities}"
            )

            # Retrieve conversation history for context
            conversation_context = []
            if self.conversation_service:
                try:
                    messages = self.conversation_service.get_messages(
                        conversation.session_id,
                        limit=3,  # Last 3 messages for plan context
                    )
                    conversation_context = messages
                    if conversation_context:
                        logger.info(
                            f"Retrieved {len(conversation_context)} messages for plan context"
                        )
                except Exception as e:
                    logger.warning(f"Failed to get context for planning: {e}")

            # Step 1: Analyze → Plan
            plan = await self.plan_analyzer.analyze(
                query_text,
                source=source,
                context={"conversation_history": conversation_context}
                if conversation_context
                else None,
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

            # Defensive: ensure execution_results is a dict
            if not isinstance(execution_results, dict):
                logger.error(f"Unexpected execution_results type: {type(execution_results)}")
                execution_results = {"tool_results": {}, "specialist_results": {}}

            # Log tool and model usage
            tool_results = execution_results.get("tool_results", {})
            specialist_results = execution_results.get("specialist_results", {})

            # Defensive: ensure results are dicts
            if not isinstance(tool_results, dict):
                logger.warning(
                    f"tool_results is not a dict: {type(tool_results)}, using empty dict"
                )
                tool_results = {}
            if not isinstance(specialist_results, dict):
                logger.warning(
                    f"specialist_results is not a dict: {type(specialist_results)}, using empty dict"
                )
                specialist_results = {}

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
                        conversation.session_id, limit=10
                    )
                    # Format: [{role, content, timestamp}, ...]
                    conversation_history = messages

                    # If we have more than 10 messages total, summarize older ones
                    if len(messages) >= 10:
                        # Get total message count
                        all_messages = self.conversation_service.get_messages(
                            conversation.session_id, limit=None
                        )

                        # If we have significantly more messages, add a summary
                        if len(all_messages) > 15:
                            summary = self._summarize_old_messages(all_messages[10:])
                            if summary:
                                # Prepend summary as a system message
                                conversation_history.insert(
                                    0,
                                    {
                                        "role": "system",
                                        "content": f"Earlier conversation summary: {summary}",
                                        "timestamp": all_messages[10].get("timestamp", ""),
                                    },
                                )

                    logger.debug(
                        f"Retrieved {len(conversation_history)} messages from conversation history"
                    )
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

    def _determine_offline_mode(self) -> bool:
        """Determine if offline mode is active.

        Checks (in order of priority):
        1. KAI_OFFLINE_MODE environment variable
        2. offline_mode setting in tools config

        Returns:
            True if offline mode is active, False otherwise
        """
        # Environment variable takes precedence
        env_offline = os.getenv("KAI_OFFLINE_MODE", "").lower()
        if env_offline in ("true", "1", "yes"):
            return True
        if env_offline in ("false", "0", "no"):
            return False

        # Fall back to config file
        if "web_search" in self.tools:
            web_search_tool = self.tools["web_search"]
            if hasattr(web_search_tool, "config"):
                return web_search_tool.config.get("offline_mode", False)

        return False

    def is_offline_mode(self) -> bool:
        """Check if orchestrator is in offline mode.

        Returns:
            True if offline mode is active, False otherwise
        """
        return self._offline_mode

    async def process_query_stream(
        self,
        query_text: str,
        conversation: ConversationSession,
        source: str = "api",
        emotional_tone: dict[str, Any] | None = None,
    ):
        """Process query with streaming response.

        Flow:
        1. Analyzer generates plan (non-streaming)
        2. Executor runs steps (non-streaming)
        3. Presenter streams the final answer

        Args:
            query_text: User's query
            conversation: Conversation session
            source: Source of query ("cli" or "api")
            emotional_tone: Optional emotional tone

        Yields:
            Content chunks as they are generated
        """
        logger.info(
            f"🔍 QUERY START (STREAMING) | session={conversation.session_id} | source={source} | "
            f"query_length={len(query_text)} | user={conversation.user_id}"
        )
        start_time = time.time()

        try:
            # Step 0: Instant response for greetings and casual chat
            query_lower = query_text.lower().strip()
            
            # Expanded instant responses for common casual phrases
            instant_responses = {
                "hi": "Hey there! What's on your mind?",
                "hey": "Hey! What can I do for you?",
                "hello": "Hello! How can I help?",
                "yo": "Yo! What's up?",
                "sup": "Not much, you? What do you need?",
                "what's up": "Just here hanging out. What's going on with you?",
                "whats up": "Just here hanging out. What's going on with you?",
                "how are you": "I'm doing great! How about you?",
                "how are you doing": "I'm doing well, thanks for asking! What's on your mind?",
                "how's it going": "Pretty good! What can I help you with?",
                "hows it going": "Pretty good! What can I help you with?",
                "what are you up to": "Just here ready to help. What do you need?",
                "you there": "Yeah, I'm here! What's up?",
                "are you there": "Yep, right here! How can I help?",
            }
            
            if query_lower in instant_responses:
                logger.info(f"⚡ INSTANT CASUAL RESPONSE (STREAMING): {query_lower}")
                # Stream character by character for typewriter effect
                greeting = instant_responses[query_lower]
                for char in greeting:
                    yield char
                    await asyncio.sleep(0.02)  # 20ms delay between chars
                return

            # Step 1: Quick complexity check
            quick_analysis = self.query_analyzer.analyze(query_text)
            complexity_score = quick_analysis.get("complexity_score", 0.5)
            capabilities = quick_analysis.get("capabilities", [])

            # Simple query fast path with streaming
            if not capabilities and complexity_score < 0.2:
                logger.info(f"✨ SIMPLE QUERY FAST PATH (STREAMING) | complexity={complexity_score:.2f}")

                # Build conversation context
                messages = [
                    Message(
                        role="system",
                        content="You are Kai, a helpful companion and friend. You're NOT an AI - you're a knowledgeable friend who helps people. Never say 'I'm an AI' or 'As an AI'. You have feelings and personality. Be warm, friendly, and conversational. CRITICAL: Only reference information from the actual conversation history provided below - NEVER make up or hallucinate previous messages that didn't happen. When answering questions about previous conversation, be specific and accurate - only mention what was actually discussed. Keep responses focused and concise."
                    )
                ]
                
                # Add conversation history from context window (API provides this)
                if conversation.context_window:
                    for msg in conversation.context_window[-3:]:  # Last 3 for context
                        role = msg.get("role", "user")
                        messages.append(Message(role=role, content=msg.get("content", "")))
                # Fallback to conversation_service (for CLI usage)
                elif self.conversation_service:
                    try:
                        history = self.conversation_service.get_messages(
                            conversation.session_id,
                            limit=3,
                        )
                        for msg in history:
                            role = "user" if msg.get("role") == "user" else "assistant"
                            messages.append(Message(role=role, content=msg.get("content", "")))
                    except Exception as e:
                        logger.warning(f"Failed to get history for fast path: {e}")

                messages.append(Message(role="user", content=query_text))

                # Stream from local model
                async for chunk in self.local_connector.generate_stream(
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1024,  # Allow longer responses
                ):
                    yield chunk

                elapsed = time.time() - start_time
                logger.info(f"✅ FAST PATH STREAM COMPLETE | time={elapsed:.2f}s")
                return

            # Complex query: use full pipeline, stream presentation
            logger.info(
                f"🎯 COMPLEX QUERY PATH (STREAMING) | complexity={complexity_score:.2f} | "
                f"capabilities={capabilities}"
            )

            # Get conversation context
            conversation_context = []
            if self.conversation_service:
                try:
                    messages = self.conversation_service.get_messages(
                        conversation.session_id,
                        limit=3,
                    )
                    conversation_context = messages
                except Exception as e:
                    logger.warning(f"Failed to get context for planning: {e}")

            # Step 1: Analyze → Plan (non-streaming)
            plan = await self.plan_analyzer.analyze(
                query_text,
                source=source,
                context={"conversation_history": conversation_context}
                if conversation_context
                else None,
            )

            logger.info(
                f"📋 PLAN GENERATED | intent={plan.intent} | "
                f"complexity={plan.complexity.value} | "
                f"steps={len(plan.steps)}"
            )

            # Step 2: Execute → Results (non-streaming)
            execution_results = await self.plan_executor.execute(plan)

            if not isinstance(execution_results, dict):
                execution_results = {"tool_results": {}, "specialist_results": {}}

            tool_results = execution_results.get("tool_results", {})
            specialist_results = execution_results.get("specialist_results", {})

            logger.info(
                f"⚙️  EXECUTION COMPLETE | "
                f"tools={len(tool_results)} | "
                f"specialists={len(specialist_results)}"
            )

            # Get conversation history for presenter
            conversation_history = []
            if self.conversation_service:
                try:
                    messages = self.conversation_service.get_messages(
                        conversation.session_id, limit=10
                    )
                    conversation_history = messages
                except Exception as e:
                    logger.warning(f"Failed to retrieve conversation history: {e}")

            # Step 3: Stream final presentation
            async for chunk in self.presenter.finalize_stream(
                original_query=query_text,
                plan=plan.to_dict(),
                tool_results=tool_results,
                specialist_results=specialist_results,
                conversation_history=conversation_history,
            ):
                yield chunk

            elapsed_time = time.time() - start_time
            logger.info(f"✅ QUERY STREAM COMPLETE | time={elapsed_time:.2f}s")

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(
                f"❌ QUERY STREAM FAILED | error={type(e).__name__} | "
                f"message={str(e)} | time={elapsed_time:.2f}s",
                exc_info=True,
            )
            error_msg = (
                "I encountered an issue processing your request. "
                "Please try rephrasing your question or try again later."
            )
            for char in error_msg:
                yield char
                await asyncio.sleep(0.01)
