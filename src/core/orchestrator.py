"""Main orchestrator for query routing and response generation."""

from typing import Dict, Any, Optional, List
from src.core.llm_connector import LLMConnector, Message
from src.core.query_analyzer import QueryAnalyzer
from src.core.cost_tracker import CostTracker
from src.core.code_generator import CodeGenerator
from src.core.sanity_checker import SanityChecker
from src.models.query import Query
from src.models.response import Response, select_response_mode
from src.models.conversation import ConversationSession
from src.models.tool_invocation import ToolInvocation
from src.tools.base_tool import BaseTool, ToolStatus
from src.lib.capability_specs import CapabilitySpecLoader
import logging
import time

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrates query processing, model routing, and response generation."""

    def __init__(
        self,
        local_connector: LLMConnector,
        external_connectors: Optional[Dict[str, LLMConnector]] = None,
        tools: Optional[Dict[str, BaseTool]] = None,
        cost_limit: float = 1.0,
        soft_cap_threshold: float = 0.8,
    ):
        """Initialize orchestrator.
        
        Args:
            local_connector: Local model connector (Ollama)
            external_connectors: Optional dict of external connectors
            tools: Optional dict of tool implementations
            cost_limit: Maximum cost limit in USD
            soft_cap_threshold: Percentage for soft cap warning (0.0-1.0)
        """
        self.local_connector = local_connector
        self.external_connectors = external_connectors or {}
        self.tools = tools or {}
        self.query_analyzer = QueryAnalyzer()
        self.code_generator = CodeGenerator()
        self.sanity_checker = SanityChecker()
        self.cost_tracker = CostTracker(cost_limit, soft_cap_threshold)
        
        # Load capability specifications for intelligent routing
        self.capability_specs = CapabilitySpecLoader()
        if self.capability_specs.has_spec("granite4-micro"):
            logger.info("Capability specs loaded - intelligent local model routing enabled")
        else:
            logger.warning("No capability specs found - using default routing logic")
        self.query_analyzer = QueryAnalyzer()
        self.cost_tracker = CostTracker(cost_limit, soft_cap_threshold)

    async def process_query(
        self,
        query_text: str,
        conversation: ConversationSession,
        emotional_tone: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Process a user query and generate response.
        
        Args:
            query_text: User input text
            conversation: Current conversation session
            emotional_tone: Optional emotional analysis (will auto-detect if not provided)
            
        Returns:
            Response object with generated content
        """
        start_time = time.time()
        
        # 0. Analyze emotional tone if not provided
        if emotional_tone is None and "sentiment" in self.tools:
            sentiment_result = await self.tools["sentiment"].execute_with_fallback(
                {"text": query_text}
            )
            if sentiment_result.status == ToolStatus.SUCCESS:
                emotional_tone = sentiment_result.data
            else:
                emotional_tone = {"emotion": "neutral", "confidence": 1.0}
        elif emotional_tone is None:
            emotional_tone = {"emotion": "neutral", "confidence": 1.0}
        
        # 1. Analyze query with topic shift detection
        analysis = self.query_analyzer.analyze(
            query_text, 
            previous_topic_embedding=conversation.current_topic_embedding
        )
        
        # Update conversation topic if shift detected
        if analysis.get("topic_shift") and analysis.get("current_topic_embedding"):
            logger.info("Topic shift detected - clearing old context")
            conversation.current_topic_embedding = analysis["current_topic_embedding"]
            # Context filtering will happen in _prepare_messages
        elif analysis.get("current_topic_embedding"):
            # Update current topic even if no shift
            conversation.current_topic_embedding = analysis["current_topic_embedding"]
        
        # Create query object
        query = Query(
            session_id=conversation.session_id,
            raw_text=query_text,
            complexity_level=analysis["complexity_level"],
            emotional_tone=emotional_tone or {"emotion": "neutral", "confidence": 1.0},
            required_capabilities=analysis["required_capabilities"],
            routing_decision=analysis["routing_decision"],
            confidence=analysis["confidence"],
        )
        
        complexity_score = analysis.get("complexity_score", 0.0)
        topic_shift = analysis.get("topic_shift", False)
        
        logger.info(
            f"Query analyzed: complexity={query.complexity_level} (score={complexity_score:.2f}), "
            f"capabilities={query.required_capabilities}, "
            f"routing={query.routing_decision}, topic_shift={topic_shift}"
        )
        
        # 2. Execute tools if needed
        tool_invocations = []
        if query.needs_tools():
            tool_invocations = await self._execute_tools(query)
        
        # 3. Make intelligent routing decision with cost awareness
        connector, model_id = self._make_routing_decision(
            query.routing_decision,
            complexity_score,
            conversation.session_id,
            query.required_capabilities,
        )
        
        # 4. Prepare messages with context and tool results
        messages = self._prepare_messages(query_text, conversation, tool_invocations)
        
        # 5. Generate response from model
        llm_response = await connector.generate(
            messages=messages,
            temperature=0.7,
            max_tokens=None,  # Let model decide
        )
        
        # 5.5. SANITY CHECK - catch unrealistic values before user sees them
        sanity_result = self.sanity_checker.check_response(
            response_text=llm_response.content,
            query_text=query_text
        )
        
        if sanity_result["suspicious"]:
            logger.warning(
                f"Sanity check detected issues: {sanity_result['issues']}"
            )
            
            # If issues are severe, consider re-routing to better model
            if self.sanity_checker.should_escalate(sanity_result):
                logger.info("Sanity check failed - escalating to external model for verification")
                
                # Try to get a better answer from external model if available
                if "claude-sonnet" in self.external_connectors:
                    better_connector = self.external_connectors["claude-sonnet"]
                    can_proceed, reason = self.cost_tracker.can_proceed(
                        conversation.session_id, estimated_cost=0.005, is_critical=True
                    )
                    
                    if can_proceed:
                        logger.info("Re-generating with Claude Sonnet to fix suspicious values")
                        # Add sanity check context to messages
                        verification_msg = Message(
                            role="system",
                            content=(
                                f"VERIFICATION NEEDED: Previous answer contained suspicious values: "
                                f"{'; '.join(sanity_result['issues'])}. "
                                f"Please provide accurate, verified information."
                            )
                        )
                        verification_messages = messages + [verification_msg]
                        
                        llm_response = await better_connector.generate(
                            messages=verification_messages,
                            temperature=0.3,  # Lower temp for accuracy
                            max_tokens=None,
                        )
                        logger.info("Used better model for verification after sanity check failure")
        
        # 6. Detect explicit mode override
        explicit_override = self._detect_mode_override(query_text)
        
        # 7. Check for goal deviation (if memory tool available)
        goal_deviation = False
        if "rag" in self.tools:
            goal_deviation = await self._check_goal_deviation(
                query_text, conversation.session_id
            )
        
        # 8. Select response mode
        response_mode = select_response_mode(
            complexity=query.complexity_level,
            emotional_tone=query.emotional_tone,
            goal_deviation=goal_deviation,
            explicit_override=explicit_override,
        )
        
        # 9. Create response object
        response = Response(
            query_id=query.query_id,
            mode=response_mode,
            content=llm_response.content,
            token_count=llm_response.token_count,
            cost=llm_response.cost,
        )
        
        # 8. Add tool results to response
        for invocation in tool_invocations:
            if invocation.is_successful() and invocation.tool_name == "web_search":
                # Add citations from web search
                citations = invocation.result.get("data", {}).get("citations", [])
                for citation in citations:
                    response.add_citation(
                        title=citation.get("title", ""),
                        url=citation.get("url", ""),
                        snippet=citation.get("snippet", ""),
                    )
            
            # Add tool result summary
            response.add_tool_result(
                tool_name=invocation.tool_name,
                data=invocation.result or {},
                execution_time_ms=invocation.execution_time_ms,
            )
        
        # 7. Update conversation context
        conversation.add_to_context({
            "role": "user",
            "content": query_text,
            "token_count": llm_response.metadata.get("prompt_tokens", 0),
        })
        
        conversation.add_to_context({
            "role": "assistant",
            "content": response.content,
            "token_count": llm_response.metadata.get("completion_tokens", 0),
        })
        
        # 8. Update conversation cost
        conversation.add_cost(llm_response.cost)
        
        # 9. Track cost with CostTracker
        self.cost_tracker.track_query(
            query_id=query.query_id,
            session_id=conversation.session_id,
            model_id=model_id,
            input_tokens=llm_response.metadata.get("prompt_tokens", 0),
            output_tokens=llm_response.metadata.get("completion_tokens", 0),
            cost=llm_response.cost,
        )
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(
            f"Query processed in {elapsed:.0f}ms, "
            f"mode={response_mode}, "
            f"tools={len(tool_invocations)}, "
            f"cost=${llm_response.cost:.4f}, "
            f"session_total=${self.cost_tracker.get_session_cost(conversation.session_id):.4f}"
        )
        
        return response

    async def _execute_tools(self, query: Query) -> List[ToolInvocation]:
        """Execute required tools for the query.
        
        Args:
            query: Query object with required_capabilities
            
        Returns:
            List of ToolInvocation objects
        """
        invocations = []
        
        for capability in query.required_capabilities:
            if capability not in self.tools:
                logger.info(f"Tool '{capability}' not available (disabled or not configured) - continuing without it")
                # Create a failed invocation to track unavailable tools
                invocations.append(ToolInvocation(
                    query_message_id=query.query_id,
                    tool_name=capability,
                    parameters={},
                    result=None,
                    error=f"Tool not available (disabled or not configured)",
                    execution_time_ms=0,
                    status="failed",
                    fallback_used=False,
                ))
                continue
            
            tool = self.tools[capability]
            
            # Prepare tool parameters
            if capability == "web_search":
                parameters = {"query": query.raw_text}
            elif capability == "rag":
                # Memory retrieval
                parameters = {
                    "action": "search",
                    "user_id": query.session_id,  # Using session_id as user context
                    "query": query.raw_text,
                    "top_k": 3,
                }
            elif capability == "code_exec":
                # Code execution - check if we can auto-generate code
                if self.code_generator.can_auto_generate(query.raw_text):
                    logger.info(
                        f"Auto-generating Python code for computational query"
                    )
                    
                    # Generate code automatically
                    generated_code = self.code_generator.generate(query.raw_text)
                    
                    if generated_code:
                        parameters = {
                            "code": generated_code,
                            "auto_generated": True,
                        }
                        logger.debug(f"Generated code:\n{generated_code[:200]}...")
                    else:
                        logger.warning("Code generation failed, skipping execution")
                        continue
                else:
                    # Code execution - for computational queries, provide guidance
                    # The model should generate code, but we can help by including
                    # the query context as a hint
                    parameters = {
                        "query_context": query.raw_text,
                        "execution_mode": "safe",
                    }
                    
                    # Note: Code execution is typically triggered by model response
                    # that includes code blocks. However, we still execute the tool
                    # here to make the capability available and log the intent.
                    logger.info(
                        f"Code execution capability detected for query - "
                        f"tool available for model to invoke (no auto-generation)"
                    )
                    
                    # Skip automatic execution for now - let model decide
                    # Only auto-generate for recognized patterns
                    continue
            else:
                parameters = {}
            
            # Execute tool
            logger.info(f"Executing tool: {capability} with params: {list(parameters.keys())}")
            start_time = time.time()
            result = await tool.execute_with_fallback(parameters)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            if result.status == ToolStatus.SUCCESS:
                logger.info(
                    f"Tool '{capability}' succeeded in {elapsed_ms}ms"
                    f"{' (fallback used)' if result.fallback_used else ''}"
                )
            else:
                logger.warning(
                    f"Tool '{capability}' failed after {elapsed_ms}ms: {result.error}"
                )
            
            # Create invocation record
            invocation = ToolInvocation(
                query_message_id=query.query_id,
                tool_name=capability,
                parameters=parameters,
                result=result.data if result.status == ToolStatus.SUCCESS else None,
                error=result.error,
                execution_time_ms=result.execution_time_ms,
                status="success" if result.status == ToolStatus.SUCCESS else "failed",
                fallback_used=result.fallback_used,
            )
            invocations.append(invocation)
        
        return invocations

    def _make_routing_decision(
        self,
        initial_routing: str,
        complexity_score: float,
        session_id: str,
        capabilities: List[str],
    ) -> tuple[LLMConnector, str]:
        """Make intelligent routing decision using cost-optimized 3-tier system.
        
        Routing Strategy (Local-First with Tool Awareness):
        - Priority 10: Local (granite4) - FREE, use for most tasks especially with tools (< 0.5)
        - Priority 8: Grok Fast - ULTRA-CHEAP ($0.0002/$0.0005), moderate queries (0.5-0.7)
        - Priority 5: Claude Sonnet - BALANCED ($0.003/$0.015), complex queries (0.7-0.85)
        - Priority 3: Claude Opus - PREMIUM ($0.015/$0.075), critical/expert queries (> 0.85)
        
        Local Model Philosophy:
        - Granite4 is capable and should be confident with web search + tools
        - Only escalate to external when truly needed (complex reasoning, expert knowledge)
        - Web search queries should default to local + web_search tool
        
        Args:
            initial_routing: Initial routing suggestion from analyzer (ignored, use complexity_score)
            complexity_score: Query complexity score (0.0-1.0)
            session_id: Session ID for cost tracking
            capabilities: Required capabilities
            
        Returns:
            Tuple of (connector, model_id)
        """
        # Check if hard cap reached - must use local
        if self.cost_tracker.is_hard_cap_reached(session_id):
            logger.error(
                f"Hard cap reached for session {session_id}, forcing local model"
            )
            return self.local_connector, "local"
        
        # Check if soft cap reached - prefer cheaper models
        soft_cap_reached = self.cost_tracker.is_soft_cap_reached(session_id)
        if soft_cap_reached:
            logger.warning(
                f"Soft cap reached for session {session_id}, preferring cheaper models"
            )
        
        # Tier 1: Local model (FREE) - Most queries, especially with tools
        # Use capability specs if available for intelligent decision
        spec = self.capability_specs.get_spec("granite4-micro")
        
        if spec:
            # Capability spec available - use intelligent routing
            has_tools = len(capabilities) > 0
            has_web_search = "web_search" in capabilities
            has_code_exec = "code_exec" in capabilities
            
            # Check if local model can handle this complexity
            can_handle = spec.can_handle_complexity(complexity_score, has_tools)
            should_prefer = spec.should_prefer_over_external(
                complexity_score, has_web_search, has_code_exec
            )
            
            if can_handle or should_prefer or soft_cap_reached:
                if capabilities:
                    logger.info(
                        f"Routing to Local (granite4) with tools {capabilities} - "
                        f"complexity={complexity_score:.2f} (spec-guided), cost=FREE"
                    )
                else:
                    logger.info(
                        f"Routing to Local (granite4) - "
                        f"complexity={complexity_score:.2f} (spec-guided), cost=FREE"
                    )
                return self.local_connector, "local"
        else:
            # No capability spec - use default threshold (0.5)
            if complexity_score < 0.5 or (soft_cap_reached and complexity_score < 0.85):
                if capabilities:
                    logger.info(
                        f"Routing to Local (granite4) with tools {capabilities} - "
                        f"complexity={complexity_score:.2f}, cost=FREE"
                    )
                else:
                    logger.info(f"Routing to Local (granite4) - complexity={complexity_score:.2f}, cost=FREE")
                return self.local_connector, "local"
        
        # Tier 2: Grok Fast (ULTRA-CHEAP) - Moderate complexity
        # Try Grok for 0.5 <= complexity < 0.7
        if complexity_score < 0.7:
            if "grok-fast" in self.external_connectors:
                can_proceed, reason = self.cost_tracker.can_proceed(
                    session_id, estimated_cost=0.001, is_critical=False
                )
                
                if can_proceed:
                    logger.info(f"Routing to Grok Fast - complexity={complexity_score:.2f}, cost=$0.0002/1k")
                    return self.external_connectors["grok-fast"], "grok-fast"
                else:
                    logger.warning(f"Cannot use Grok Fast: {reason}, falling back to local")
                    return self.local_connector, "local"
            else:
                logger.debug("Grok Fast not configured, trying next tier")
        
        # Tier 3: Claude Sonnet (BALANCED) - Complex queries
        # Use Sonnet for 0.7 <= complexity < 0.85
        if complexity_score < 0.85:
            if "claude-sonnet" in self.external_connectors:
                can_proceed, reason = self.cost_tracker.can_proceed(
                    session_id, estimated_cost=0.005, is_critical=False
                )
                
                if can_proceed:
                    logger.info(f"Routing to Claude Sonnet - complexity={complexity_score:.2f}, cost=$0.003/1k")
                    return self.external_connectors["claude-sonnet"], "claude-sonnet"
                else:
                    logger.warning(f"Cannot use Sonnet: {reason}, falling back to cheaper tier")
                    # Try to use Grok as fallback
                    if "grok-fast" in self.external_connectors:
                        can_proceed_grok, _ = self.cost_tracker.can_proceed(
                            session_id, estimated_cost=0.001, is_critical=False
                        )
                        if can_proceed_grok:
                            logger.info("Falling back to Grok Fast")
                            return self.external_connectors["grok-fast"], "grok-fast"
                    return self.local_connector, "local"
            else:
                logger.debug("Claude Sonnet not configured, trying cheaper tier")
                # Try Grok as fallback
                if "grok-fast" in self.external_connectors:
                    can_proceed, _ = self.cost_tracker.can_proceed(
                        session_id, estimated_cost=0.001, is_critical=False
                    )
                    if can_proceed:
                        logger.info("Using Grok Fast (Sonnet unavailable)")
                        return self.external_connectors["grok-fast"], "grok-fast"
        
        # Tier 4: Claude Opus (PREMIUM) - Critical/Expert queries
        # Use Opus for complexity >= 0.85 (high-stakes, expert-level)
        if "claude-opus" in self.external_connectors:
            can_proceed, reason = self.cost_tracker.can_proceed(
                session_id, estimated_cost=0.02, is_critical=True
            )
            
            if can_proceed:
                logger.info(f"Routing to Claude Opus (PREMIUM) - complexity={complexity_score:.2f}, cost=$0.015/1k")
                return self.external_connectors["claude-opus"], "claude-opus"
            else:
                logger.warning(f"Cannot use Opus: {reason}, cascading to cheaper tiers")
                # Cascade fallback: Sonnet → Grok → Local
                if "claude-sonnet" in self.external_connectors:
                    can_proceed_sonnet, _ = self.cost_tracker.can_proceed(
                        session_id, estimated_cost=0.005, is_critical=True
                    )
                    if can_proceed_sonnet:
                        logger.info("Falling back to Claude Sonnet (high complexity)")
                        return self.external_connectors["claude-sonnet"], "claude-sonnet"
                
                if "grok-fast" in self.external_connectors:
                    can_proceed_grok, _ = self.cost_tracker.can_proceed(
                        session_id, estimated_cost=0.001, is_critical=True
                    )
                    if can_proceed_grok:
                        logger.info("Falling back to Grok Fast (high complexity)")
                        return self.external_connectors["grok-fast"], "grok-fast"
                
                logger.warning("All external models unavailable, using local for critical query")
                return self.local_connector, "local"
        else:
            logger.debug("Claude Opus not configured, cascading to cheaper tiers")
            # Try Sonnet then Grok for critical queries
            if "claude-sonnet" in self.external_connectors:
                can_proceed, _ = self.cost_tracker.can_proceed(
                    session_id, estimated_cost=0.005, is_critical=True
                )
                if can_proceed:
                    logger.info("Using Claude Sonnet (Opus unavailable, high complexity)")
                    return self.external_connectors["claude-sonnet"], "claude-sonnet"
            
            if "grok-fast" in self.external_connectors:
                can_proceed, _ = self.cost_tracker.can_proceed(
                    session_id, estimated_cost=0.001, is_critical=True
                )
                if can_proceed:
                    logger.info("Using Grok Fast (Opus/Sonnet unavailable, high complexity)")
                    return self.external_connectors["grok-fast"], "grok-fast"
        
        # Final fallback to local
        logger.warning(f"All external models unavailable, using local for complexity={complexity_score:.2f}")
        return self.local_connector, "local"

    def _select_connector(self, routing_decision: str) -> LLMConnector:
        """Select appropriate LLM connector based on routing.
        
        Args:
            routing_decision: Routing decision from analyzer
            
        Returns:
            LLM connector to use
        """
        if routing_decision == "local":
            return self.local_connector
        
        if routing_decision == "external_opus":
            if "claude-opus" in self.external_connectors:
                return self.external_connectors["claude-opus"]
            logger.warning("Claude Opus not available, falling back to local")
            return self.local_connector
        
        # Default to local
        return self.local_connector

    def _prepare_messages(
        self, query_text: str, conversation: ConversationSession, tool_invocations: List[ToolInvocation] = []
    ) -> list[Message]:
        """Prepare messages with conversation context and tool results.
        
        Args:
            query_text: Current user query
            conversation: Conversation session
            tool_invocations: Tool execution results
            
        Returns:
            List of Message objects
        """
        messages = []
        
        # Add system prompt
        messages.append(
            Message(
                role="system",
                content=(
                    "You are a helpful AI assistant. Provide clear, concise, "
                    "and accurate responses. For simple questions, keep answers "
                    "to 1-2 sentences unless more detail is requested."
                ),
            )
        )
        
        # Add conversation context
        for msg in conversation.get_context_messages():
            messages.append(Message(role=msg["role"], content=msg["content"]))
        
        # Add tool results if any
        if tool_invocations:
            tool_context = self._format_tool_results(tool_invocations)
            if tool_context:
                messages.append(
                    Message(
                        role="system",
                        content=f"Tool Results:\n{tool_context}",
                    )
                )
        
        # Add current query if not already in context
        if not messages or messages[-1].content != query_text:
            messages.append(Message(role="user", content=query_text))
        
        return messages

    def _format_tool_results(self, invocations: List[ToolInvocation]) -> str:
        """Format tool results for inclusion in prompt.
        
        Args:
            invocations: List of tool invocations
            
        Returns:
            Formatted string of tool results
        """
        formatted = []
        
        for inv in invocations:
            if inv.is_successful():
                if inv.tool_name == "web_search":
                    citations = inv.result.get("data", {}).get("citations", [])
                    formatted.append(f"\nWeb Search Results:")
                    for i, citation in enumerate(citations[:3], 1):  # Top 3
                        formatted.append(
                            f"{i}. {citation.get('title', 'N/A')}\n"
                            f"   {citation.get('snippet', 'N/A')}\n"
                            f"   Source: {citation.get('url', 'N/A')}"
                        )
                else:
                    formatted.append(f"\n{inv.tool_name}: {inv.result}")
        
        return "\n".join(formatted)

    async def check_health(self) -> Dict[str, bool]:
        """Check health of all connectors.
        
        Returns:
            Dict of connector_name: healthy status
        """
        health = {}
        
        # Check local connector
        health["local"] = await self.local_connector.check_health()
        
        # Check external connectors
        for name, connector in self.external_connectors.items():
            health[name] = await connector.check_health()
        
        return health

    def get_cost_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get cost summary for a session or all sessions.
        
        Args:
            session_id: Optional session ID to get summary for
            
        Returns:
            Cost summary dict
        """
        return self.cost_tracker.get_cost_summary(session_id)

    def enable_manual_override(self, enabled: bool = True) -> None:
        """Enable manual cost override for critical queries.
        
        Args:
            enabled: Whether to enable override
        """
        self.cost_tracker.enable_manual_override(enabled)

    def _detect_mode_override(self, query_text: str) -> Optional[str]:
        """Detect explicit mode override from query text.
        
        Args:
            query_text: User query
            
        Returns:
            Mode override or None
        """
        text_lower = query_text.lower()
        
        # Concise mode keywords
        if any(phrase in text_lower for phrase in [
            "just the quick answer",
            "give me the short version",
            "brief answer",
            "tldr",
            "in a nutshell",
            "quick summary"
        ]):
            return "concise"
        
        # Expert mode keywords
        if any(phrase in text_lower for phrase in [
            "explain in detail",
            "give me a detailed",
            "break it down",
            "step by step",
            "comprehensive analysis"
        ]):
            return "expert"
        
        # Advisor mode keywords
        if any(phrase in text_lower for phrase in [
            "help me decide",
            "what should i do",
            "advise me",
            "guide me"
        ]):
            return "advisor"
        
        return None

    async def _check_goal_deviation(self, query_text: str, session_id: str) -> bool:
        """Check if query suggests goal deviation.
        
        Args:
            query_text: User query
            session_id: Session ID for memory lookup
            
        Returns:
            True if query deviates from stored goals
        """
        # Search for user goals in memory
        if "rag" not in self.tools:
            return False
        
        try:
            memory_tool = self.tools["rag"]
            result = await memory_tool.execute_with_fallback({
                "action": "search",
                "user_id": session_id,
                "query": "my goals",
                "memory_type": "goal",
                "top_k": 3,
            })
            
            if result.status != ToolStatus.SUCCESS:
                return False
            
            memories = result.data.get("memories", [])
            if not memories:
                return False
            
            # Simple deviation check: look for negative patterns
            text_lower = query_text.lower()
            deviation_keywords = [
                "giving up", "quit", "stop trying", "too hard",
                "can't do", "impossible", "waste of time",
                "not worth it", "forget about"
            ]
            
            has_deviation = any(kw in text_lower for kw in deviation_keywords)
            
            return has_deviation
        
        except Exception as e:
            logger.warning(f"Goal deviation check failed: {e}")
            return False

    async def execute_code(self, code: str, session_id: str) -> ToolInvocation:
        """Execute Python code in sandboxed container.
        
        This is called when the model generates code that needs verification.
        
        Args:
            code: Python code to execute
            session_id: Session ID for tracking
            
        Returns:
            ToolInvocation with execution results
        """
        if "code_exec" not in self.tools:
            return ToolInvocation(
                query_message_id=session_id,
                tool_name="code_exec",
                parameters={"code": code},
                result=None,
                error="Code execution tool not available",
                execution_time_ms=0,
                status="failed",
                fallback_used=False,
            )
        
        logger.info("Executing generated code in sandbox")
        tool = self.tools["code_exec"]
        result = await tool.execute_with_fallback({"code": code})
        
        return ToolInvocation(
            query_message_id=session_id,
            tool_name="code_exec",
            parameters={"code": code},
            result=result.data if result.status == ToolStatus.SUCCESS else None,
            error=result.error,
            execution_time_ms=result.execution_time_ms,
            status="success" if result.status == ToolStatus.SUCCESS else "failed",
            fallback_used=result.fallback_used,
        )
