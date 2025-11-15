"""Main orchestrator for query routing and response generation."""

import os
import uuid
import time
import logging
from typing import Dict, Any, Optional

from src.core.llm_connector import LLMConnector
from src.core.cost_tracker import CostTracker
from src.core.plan_analyzer import PlanAnalyzer
from src.core.plan_executor import PlanExecutor
from src.core.presenters.granite_presenter import GranitePresenter
from src.core.specialists.verification import SpecialistVerifier
from src.core.sanity_checker import SanityChecker
from src.models.response import Response
from src.models.conversation import ConversationSession
from src.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrates query processing with plan-execute-present pattern."""

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
        
        self.presenter = GranitePresenter(self.local_connector)

    async def process_query(
        self,
        query_text: str,
        conversation: ConversationSession,
        emotional_tone: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Process query using plan-execute-present orchestration.
        
        Flow:
        1. Analyzer (Granite) generates JSON execution plan
        2. Executor runs steps: tools → sanity → specialists
        3. Presenter (Granite) converts results to natural language
        
        Args:
            query_text: User's query
            conversation: Conversation session
            emotional_tone: Optional emotional tone (unused currently)
            
        Returns:
            Response object with final answer
        """
        logger.info(f"Processing query (session={conversation.session_id})")
        start_time = time.time()
        
        try:
            # Step 1: Analyze → Plan
            plan = await self.plan_analyzer.analyze(query_text)
            
            logger.info(
                f"Plan: intent={plan.intent}, "
                f"complexity={plan.complexity.value}, "
                f"steps={len(plan.steps)}, "
                f"capabilities={plan.capabilities}"
            )
            
            # Step 2: Execute → Results
            execution_results = await self.plan_executor.execute(plan)
            
            logger.info(
                f"Executed: tools={len(execution_results['tool_results'])}, "
                f"specialists={len(execution_results['specialist_results'])}"
            )
            
            # Step 3: Present → Answer
            final_output = await self.presenter.finalize(
                original_query=query_text,
                plan=plan.to_dict(),
                tool_results=execution_results['tool_results'],
                specialist_results=execution_results['specialist_results'],
            )
            
            elapsed_time = time.time() - start_time
            
            logger.info(
                f"Complete: {len(final_output.final_answer)} chars, "
                f"citations={len(final_output.citations_used)}, "
                f"time={elapsed_time:.2f}s"
            )
            
            # Build response
            response = Response(
                query_id=str(uuid.uuid4()),
                mode="concise",
                content=final_output.final_answer,
                token_count=0,  # TODO: aggregate from execution
                cost=0.0,  # TODO: aggregate from execution
            )
            
            response.metadata = {
                **final_output.debug_info,
                "plan_id": plan.plan_id,
                "intent": plan.intent,
                "complexity": plan.complexity.value,
                "elapsed_time": elapsed_time,
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Orchestration failed: {e}", exc_info=True)
            
            return Response(
                query_id=str(uuid.uuid4()),
                mode="concise",
                content=(
                    "I encountered an issue processing your request. "
                    "Please try rephrasing your question or try again later."
                ),
                token_count=0,
                cost=0.0,
                metadata={"error": str(e)},
            )

    async def check_health(self) -> Dict[str, bool]:
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

    def get_cost_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get cost tracking summary.
        
        Args:
            session_id: Optional session to filter by
            
        Returns:
            Dict with cost statistics
        """
        return self.cost_tracker.get_summary(session_id)
