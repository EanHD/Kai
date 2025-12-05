"""Main orchestrator for query routing and response generation."""

import asyncio
import logging
import os
import re
import time
import uuid
from typing import Any
from datetime import datetime

from src.core.cost_tracker import CostTracker
from src.core.llm_connector import LLMConnector, Message
from src.core.plan_analyzer import PlanAnalyzer
from src.core.plan_executor import PlanExecutor
from src.core.presenters.granite_presenter import GranitePresenter
from src.core.presenters.local_presenter import LocalPresenter
from src.core.query_analyzer import QueryAnalyzer
from src.core.sanity_checker import SanityChecker
from src.core.specialists.verification import SpecialistVerifier
from src.core.reasoner import ReasoningEngine
from src.embeddings.factory import get_shared_embeddings_provider
from src.models.conversation import ConversationSession
from src.models.response import Response
from src.models.knowledge import KnowledgeObject, Point
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.storage.knowledge_store import KnowledgeStore
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
        sqlite_store: SQLiteStore | None = None,
        vector_store: VectorStore | None = None,
        planner_connector: LLMConnector | None = None,
        narrator_connector: LLMConnector | None = None,
        memory_vault = None,
    ):
        """Initialize orchestrator.

        Args:
            local_connector: Local model connector (Ollama/Granite)
            external_connectors: Optional dict of external connectors
            tools: Optional dict of tool implementations
            cost_limit: Maximum cost limit in USD
            soft_cap_threshold: Percentage for soft cap warning (0.0-1.0)
            sqlite_store: SQLite storage instance
            vector_store: Vector storage instance
            planner_connector: Specific connector for planning/reasoning
            narrator_connector: Specific connector for narration/presentation
            memory_vault: Optional memory vault for learned preferences
        """
        self.local_connector = local_connector
        self.external_connectors = external_connectors or {}
        self.tools = tools or {}
        self.cost_tracker = CostTracker(cost_limit, soft_cap_threshold)
        self.conversation_service = None  # Will be injected by CLI/API
        self.memory_vault = memory_vault  # Store for presenter access

        # Initialize embeddings provider
        self.embeddings_provider = get_shared_embeddings_provider()

        # Initialize Knowledge Components
        if sqlite_store and vector_store:
            self.knowledge_store = KnowledgeStore(
                sqlite_store=sqlite_store,
                vector_store=vector_store,
                embeddings_provider=self.embeddings_provider
            )
        else:
            logger.warning("Knowledge Store not initialized (missing stores)")
            self.knowledge_store = None

        # Initialize Reasoner (use planner connector if available, else fallback)
        self.reasoner_connector = planner_connector
        if not self.reasoner_connector:
            # Fallback logic if not explicitly provided
            for model_name, connector in self.external_connectors.items():
                if "claude" in model_name.lower() or "sonnet" in model_name.lower():
                    self.reasoner_connector = connector
                    break
        
        if not self.reasoner_connector:
             # Fallback to any external or local
             self.reasoner_connector = next(iter(self.external_connectors.values()), self.local_connector)
             
        self.reasoner = ReasoningEngine(self.reasoner_connector)
        
        # Initialize Local Presenter (Narrator)
        self.narrator_connector = narrator_connector or self.local_connector
        self.local_presenter = LocalPresenter(self.narrator_connector)

        # Core orchestration components
        # QueryAnalyzer for complexity detection (used for smart routing)
        # Pass local_connector for intelligent LLM-based analysis
        self.query_analyzer = QueryAnalyzer(
            embeddings_provider=self.embeddings_provider,
            llm_connector=self.local_connector
        )

        # Use planner connector for planning
        self.planner_connector = planner_connector
        if not self.planner_connector:
            # Fallback logic
            for model_name, connector in self.external_connectors.items():
                if "grok" in model_name.lower():
                    self.planner_connector = connector
                    logger.info(f"Using {model_name} for planning")
                    break

        if not self.planner_connector:
            self.planner_connector = self.local_connector
            logger.info("Using local model for planning (no external planner available)")

        self.plan_analyzer = PlanAnalyzer(
            self.planner_connector, orchestrator=self, embeddings_provider=self.embeddings_provider
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

        # Presenter: ALWAYS use narrator model for user-facing text
        logger.info("Using narrator model for presentation")
        self.presenter = GranitePresenter(self.narrator_connector, memory_vault=self.memory_vault)

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
        1. Check Cache (Knowledge Store)
        2. Analyzer (Planner) generates JSON execution plan (if tools needed)
        3. Executor runs steps: tools → sanity
        4. Reasoner (Planner) generates Knowledge Object
        5. Presenter (Narrator) converts KO to natural language

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
            quick_analysis = await self.query_analyzer.analyze(query_text)
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
                        content="You are Kai. You're a witty, slightly rebellious friend. You speak in lowercase mostly. You're chill, maybe a bit sarcastic. You NEVER say 'As an AI'. You NEVER lecture. If someone says 'yo', just say 'yo' back or something cool. Don't be weird. Be brief."
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

            # 1. Check Cache (Knowledge Store)
            if self.knowledge_store:
                cached_kos = self.knowledge_store.search(query_text, top_k=1, similarity_threshold=0.9)
                if cached_kos:
                    logger.info(f"🧠 CACHE HIT | Found Knowledge Object {cached_kos[0].summary[:50]}...")
                    
                    # Narrate cached KO
                    final_content = ""
                    async for chunk in self.local_presenter.narrate_knowledge_object(cached_kos[0]):
                        final_content += chunk
                    
                    elapsed_time = time.time() - start_time
                    logger.info(f"✅ CACHE HIT COMPLETE | time={elapsed_time:.2f}s")
                    
                    return Response(
                        query_id=str(uuid.uuid4()),
                        mode="concise",
                        content=final_content,
                        token_count=0,
                        cost=0.0,
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

            # Step 2: Analyze → Plan (Determine if tools are needed)
            plan = await self.plan_analyzer.analyze(
                query_text,
                source=source,
                context={"conversation_history": conversation_context}
                if conversation_context
                else None,
            )

            tools_output = None
            
            # If plan has steps (tools needed), execute them
            if plan.steps:
                logger.info(f"🛠️  TOOLS REQUIRED | steps={len(plan.steps)}")
                execution_results = await self.plan_executor.execute(plan)
                if isinstance(execution_results, dict):
                    tools_output = execution_results.get("tool_results", {})
            else:
                logger.info("🧠 PURE REASONING | No tools required")

            # Step 3: Call Reasoner to produce Knowledge Object
            logger.info("🤔 REASONING START")
            ko = await self.reasoner.analyze(
                query=query_text,
                context={"conversation_history": conversation_context},
                tools_output=tools_output
            )
            logger.info("💡 REASONING COMPLETE")

            # Step 4: Store Knowledge Object
            if self.knowledge_store:
                self.knowledge_store.store(ko)

            # Step 5: Narrate Knowledge Object
            final_content = ""
            async for chunk in self.local_presenter.narrate_knowledge_object(ko):
                final_content += chunk

            elapsed_time = time.time() - start_time
            
            # Calculate estimated cost
            estimated_cost = (
                self.cost_tracker.get_total_cost() if hasattr(self, "cost_tracker") else 0.0
            )

            logger.info(
                f"✅ QUERY SUCCESS | "
                f"response_length={len(final_content)} chars | "
                f"time={elapsed_time:.2f}s | "
                f"cost=${estimated_cost:.4f}"
            )

            # Build response
            return Response(
                query_id=str(uuid.uuid4()),
                mode="concise",
                content=final_content,
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

            # In debug mode, show the actual error
            debug_mode = os.getenv("DEBUG", "false").lower() == "true"
            if debug_mode:
                error_content = f"Error: {type(e).__name__}: {str(e)}"
            else:
                error_content = (
                    "I encountered an issue processing your request. "
                    "Please try rephrasing your question or try again later."
                )

            return Response(
                query_id=str(uuid.uuid4()),
                mode="concise",
                content=error_content,
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

            # ─────────────────────────────────────────────────────
            # FEATURE: TL;DR - Auto-summarize last response
            # ─────────────────────────────────────────────────────
            if query_lower in ["tl;dr", "tldr", "too long; didn't read"]:
                logger.info("📜 TL;DR REQUESTED")
                last_assistant_msg = None
                if self.conversation_service:
                    try:
                        history = self.conversation_service.get_messages(conversation.session_id, limit=10)
                        for msg in reversed(history):
                            if msg.get("role") == "assistant":
                                last_assistant_msg = msg.get("content")
                                break
                    except Exception as e:
                        logger.warning(f"Failed to get history for tl;dr: {e}")
                
                if last_assistant_msg:
                    summary_prompt = f"Summarize this in 2-3 sentences for a 'tl;dr':\n\n{last_assistant_msg}"
                    messages = [Message(role="user", content=summary_prompt)]
                    async for chunk in self.local_connector.generate_stream(messages, max_tokens=200):
                        yield chunk
                    return
                else:
                    yield "I don't have a previous response to summarize."
                    return

            # ─────────────────────────────────────────────────────
            # FEATURE: MEMORY - Auto-store "remember that"
            # ─────────────────────────────────────────────────────
            memory_match = re.match(r"^(?:please\s+)?remember\s+(?:that\s+)?(.+)$", query_text, re.IGNORECASE)
            if memory_match:
                content_to_store = memory_match.group(1).strip()
                logger.info(f"💾 MEMORY REQUEST: {content_to_store}")
                
                if self.knowledge_store:
                    ko = KnowledgeObject(
                        kind="qa",
                        query=f"User memory: {content_to_store}",
                        summary=content_to_store,
                        detailed_points=[Point(title="Memory", body=content_to_store, importance="high")],
                        confidence=1.0,
                        metadata={"type": "user_memory"}
                    )
                    self.knowledge_store.store(ko)
                    yield f"Got it, you {content_to_store}."
                else:
                    yield "I would remember that, but my memory storage isn't initialized."
                return

            # Step 1: Quick complexity check
            quick_analysis = await self.query_analyzer.analyze(query_text)
            complexity_score = quick_analysis.get("complexity_score", 0.5)
            capabilities = quick_analysis.get("required_capabilities", [])
            complexity_level = quick_analysis.get("complexity_level", "moderate")
            requires_multi_hop = quick_analysis.get("requires_multi_hop", False)

            # ─────────────────────────────────────────────────────
            # NEW FAST PATH – Bypass heavy reasoning for simple queries
            # ─────────────────────────────────────────────────────
            is_simple = complexity_level in ("trivial", "simple")
            has_no_caps = len(capabilities) == 0
            only_conversation = capabilities == ["conversation"]
            
            # Check for simple web search (single step, no multi-hop)
            is_simple_search = (
                "web_search" in capabilities 
                and len(capabilities) == 1 
                and not requires_multi_hop
                and complexity_score < 0.6 # Allow slightly more complex queries if just search
            )
            
            if is_simple or has_no_caps or only_conversation or is_simple_search:
                logger.info(f"⚡ FAST PATH ACTIVATED | caps={capabilities} | score={complexity_score:.2f}")
                
                # Get history
                history = []
                if self.conversation_service:
                    try:
                        history = self.conversation_service.get_messages(
                            conversation.session_id,
                            limit=5,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to get history for fast path: {e}")

                # Quick search if needed
                search_results = None
                if "web_search" in capabilities:
                    logger.info("🔎 Executing quick web search...")
                    search_results = await self._quick_web_search(query_text)
                
                # Stream directly
                start_fast = time.time()
                async for chunk in self.presenter.quick_conversation_path(
                    user_message=query_text,
                    history=history,
                    quick_search_results=search_results
                ):
                    yield chunk
                
                elapsed = time.time() - start_fast
                logger.info(f"✅ FAST PATH COMPLETE | time={elapsed:.2f}s")
                return

            # ─────────────────────────────────────────────────────
            # MEDIUM PATH – Single-shot reasoning for planning/strategy
            # ─────────────────────────────────────────────────────
            # Check config for medium path
            medium_path_enabled = True
            # Try to get from config loader if available, otherwise default to True
            # We don't have direct access to ConfigLoader instance here easily without injection,
            # but we can check env var directly as fallback
            if os.getenv("MEDIUM_PATH_ENABLED", "true").lower() != "true":
                medium_path_enabled = False

            intent_tags = quick_analysis.get("intent_tags", [])
            is_planning = "plan" in intent_tags or "strategy" in intent_tags
            is_medium_complexity = complexity_score > 0.6
            
            if medium_path_enabled and (is_planning or is_medium_complexity):
                logger.info(f"🚀 MEDIUM PATH ACTIVATED | score={complexity_score:.2f} | intent={intent_tags}")
                
                # Use planner connector (Grok/Sonnet)
                model_connector = self.planner_connector
                
                # System prompt for medium path
                medium_system_prompt = """You are an expert strategist. Think step-by-step but keep final answer concise and human-sounding.
Do not output JSON. Do not use markdown tables unless asked.
Never lecture. End with a question if it makes sense."""

                # Build messages
                messages = [Message(role="system", content=medium_system_prompt)]
                
                # Add history
                if self.conversation_service:
                    try:
                        history = self.conversation_service.get_messages(
                            conversation.session_id,
                            limit=5,
                        )
                        for msg in history:
                            role = msg.get("role", "user")
                            content = msg.get("content", "")
                            messages.append(Message(role=role, content=content))
                    except Exception as e:
                        logger.warning(f"Failed to get history for medium path: {e}")
                
                messages.append(Message(role="user", content=query_text))
                
                # Stream directly
                start_medium = time.time()
                
                # Use generate_stream directly from the connector
                stream_gen = model_connector.generate_stream(
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048
                )
                
                async for chunk in self.presenter.stream_raw(stream_gen):
                    yield chunk
                    
                elapsed = time.time() - start_medium
                logger.info(f"✅ MEDIUM PATH COMPLETE | time={elapsed:.2f}s")
                return

            # Complex query: use full pipeline, stream presentation
            logger.info(
                f"🎯 COMPLEX QUERY PATH (STREAMING) | complexity={complexity_score:.2f} | "
                f"capabilities={capabilities}"
            )

            # 1. Check Cache (Knowledge Store)
            if self.knowledge_store:
                cached_kos = self.knowledge_store.search(query_text, top_k=1, similarity_threshold=0.9)
                if cached_kos:
                    logger.info(f"🧠 CACHE HIT | Found Knowledge Object {cached_kos[0].summary[:50]}...")
                    async for chunk in self.local_presenter.narrate_knowledge_object(cached_kos[0]):
                        yield chunk
                    
                    elapsed_time = time.time() - start_time
                    logger.info(f"✅ CACHE STREAM COMPLETE | time={elapsed_time:.2f}s")
                    return

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

            # 2. Determine if Tools are needed
            # We use the existing PlanAnalyzer to check if we need tools
            plan = await self.plan_analyzer.analyze(
                query_text,
                source=source,
                context={"conversation_history": conversation_context}
                if conversation_context
                else None,
            )

            tools_output = None
            
            # If plan has steps (tools needed), execute them
            if plan.steps:
                logger.info(f"🛠️  TOOLS REQUIRED | steps={len(plan.steps)}")
                execution_results = await self.plan_executor.execute(plan)
                if isinstance(execution_results, dict):
                    tools_output = execution_results.get("tool_results", {})
            else:
                logger.info("🧠 PURE REASONING | No tools required")

            # 3. Call Reasoner to produce Knowledge Object
            logger.info("🤔 REASONING START")
            ko = await self.reasoner.analyze(
                query=query_text,
                context={"conversation_history": conversation_context},
                tools_output=tools_output
            )
            logger.info("💡 REASONING COMPLETE")

            # 4. Store Knowledge Object
            if self.knowledge_store:
                self.knowledge_store.store(ko)

            # 5. Narrate Knowledge Object
            async for chunk in self.local_presenter.narrate_knowledge_object(ko):
                yield chunk

            elapsed_time = time.time() - start_time
            logger.info(f"✅ QUERY STREAM COMPLETE | time={elapsed_time:.2f}s")

            # ─────────────────────────────────────────────────────
            # FEATURE: COST NOTIFICATION - Every 20 msgs or >50% budget
            # ─────────────────────────────────────────────────────
            try:
                session_cost = self.cost_tracker.get_session_cost(conversation.session_id)
                total_limit = self.cost_tracker.cost_limit.total_limit
                
                # Count messages in this session
                session_records = [r for r in self.cost_tracker.query_records if r.session_id == conversation.session_id]
                msg_count = len(session_records)
                
                should_notify = False
                if msg_count > 0 and msg_count % 20 == 0:
                    should_notify = True
                elif session_cost > (total_limit * 0.5):
                    # Notify periodically if over 50% budget
                    if msg_count > 0 and msg_count % 10 == 0:
                        should_notify = True
                        
                if should_notify:
                    notification = f"\n\n(heads up — we're at ${session_cost:.2f} of your ${total_limit:.0f} budget this month)"
                    for char in notification:
                        yield char
                        await asyncio.sleep(0.005)
            except Exception as e:
                logger.warning(f"Failed to generate cost notification: {e}")

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(
                f"❌ QUERY STREAM FAILED | error={type(e).__name__} | "
                f"message={str(e)} | time={elapsed_time:.2f}s",
                exc_info=True,
            )
            
            # In debug mode, show the actual error
            debug_mode = os.getenv("DEBUG", "false").lower() == "true"
            if debug_mode:
                error_msg = f"Error: {type(e).__name__}: {str(e)}"
            else:
                error_msg = (
                    "I encountered an issue processing your request. "
                    "Please try rephrasing your question or try again later."
                )
            
            for char in error_msg:
                yield char
                await asyncio.sleep(0.01)

    async def _quick_web_search(self, query: str) -> str | None:
        """Execute a quick web search for the fast path.
        
        Args:
            query: The query to search for
            
        Returns:
            Formatted search summary or None
        """
        if "web_search" not in self.tools:
            return None
            
        try:
            # Use the tool directly
            result = await self.tools["web_search"].execute(query)
            if result.status == "success":
                data = result.data
                citations = data.get("citations", [])
                if not citations:
                    return None
                    
                summary = "Search Results:\n"
                for i, cit in enumerate(citations[:3]): # Top 3 only for speed/conciseness
                    summary += f"- {cit.get('snippet', '')}\n"
                return summary
        except Exception as e:
            logger.error(f"Quick search failed: {e}")
            return None
        return None
