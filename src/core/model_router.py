"""Model router for intelligent tiered routing based on query complexity and cost."""

import logging
from typing import Any, Optional
from dataclasses import dataclass

from src.core.llm_connector import LLMConnector

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Decision from the model router."""
    model_id: str
    model_name: str
    connector: LLMConnector
    estimated_cost: float
    routing_tier: str
    reasoning: str


class ModelRouter:
    """Routes queries to appropriate models based on complexity, intent, and cost."""

    def __init__(
        self,
        local_connector: LLMConnector,
        external_connectors: dict[str, LLMConnector],
        cost_tracker: Any,
        monthly_cap: float = 3.0,
        soft_cap_threshold: float = 0.8,
    ):
        """Initialize model router.

        Args:
            local_connector: Local model connector (Qwen2.5-3B)
            external_connectors: External model connectors
            cost_tracker: Cost tracking instance
            monthly_cap: Monthly spending cap in USD
            soft_cap_threshold: Threshold for soft cap (0.0-1.0)
        """
        self.local_connector = local_connector
        self.external_connectors = external_connectors
        self.cost_tracker = cost_tracker
        self.monthly_cap = monthly_cap
        self.soft_cap_threshold = soft_cap_threshold

        # Model tier mapping
        self.tiers = {
            "local_fast": {
                "connector": local_connector,
                "cost": 0.0,
                "description": "Qwen2.5-3B local model",
            },
            "grok_fast": {
                "model_name": "x-ai/grok-4-fast",
                "cost": 0.002,
                "description": "Grok-4-Fast for planning/strategy",
            },
            "sonnet": {
                "model_name": "anthropic/claude-sonnet-4.5",
                "cost": 0.01,
                "description": "Claude Sonnet for deep reasoning",
            },
            "opus": {
                "model_name": "anthropic/claude-opus-4.1",
                "cost": 0.05,
                "description": "Claude Opus for critical tasks",
            },
        }

    def route(
        self,
        query_text: str,
        analysis: dict[str, Any],
        force_local: bool = False,
    ) -> RoutingDecision:
        """Route query to appropriate model based on analysis.

        Routing Table:
        - Casual chat, greetings, <3 messages → local_fast (Qwen2.5-3B) [$0]
        - Math / code execution → local_fast + sandbox [$0]
        - Simple fact questions → local_fast + quick search [$0]
        - "plan", "strategy", "help me think" → grok-4-fast [~$0.002]
        - Deep reasoning, analogies, creativity → sonnet-4.5 [~$0.01]
        - Critical / very complex → opus-4.1 [rare]

        Args:
            query_text: The user's query
            analysis: Analysis result from QueryAnalyzer
            force_local: Force local-only mode

        Returns:
            RoutingDecision with model selection and reasoning
        """
        # Check if we've hit cost cap
        current_cost = self.cost_tracker.get_total_cost()
        cap_percentage = current_cost / self.monthly_cap if self.monthly_cap > 0 else 0

        if cap_percentage >= 1.0:
            logger.warning(f"💰 MONTHLY CAP HIT (${current_cost:.2f}/${self.monthly_cap:.2f}) - forcing local-only")
            force_local = True
        elif cap_percentage >= self.soft_cap_threshold:
            logger.warning(
                f"💰 SOFT CAP REACHED ({cap_percentage*100:.0f}%) - "
                f"${current_cost:.2f}/${self.monthly_cap:.2f} - downgrading to local-only"
            )
            force_local = True

        # Extract analysis fields
        complexity_score = analysis.get("complexity_score", 0.5)
        complexity_level = analysis.get("complexity_level", "moderate")
        intent_tags = analysis.get("intent_tags", [])
        required_capabilities = analysis.get("required_capabilities", [])
        requires_multi_hop = analysis.get("requires_multi_hop", False)

        # TIER 1: Local Fast (Qwen2.5-3B) - Default for most queries
        # Casual chat, greetings, simple questions
        if force_local:
            return self._create_local_decision(
                "Force local due to cost cap or user preference"
            )

        # No heavy keywords → stay local forever
        has_heavy_keywords = any(
            tag in intent_tags
            for tag in [
                "planning",
                "strategy",
                "deep_reasoning",
                "creative",
                "critical",
                "complex_analysis",
            ]
        )

        if not has_heavy_keywords and complexity_score < 0.6:
            return self._create_local_decision(
                f"Simple query without heavy keywords (complexity={complexity_score:.2f})"
            )

        # Casual greetings and short messages
        if complexity_level == "simple" and len(query_text.split()) < 10:
            return self._create_local_decision(
                "Casual greeting or short message"
            )

        # Math and code execution → local + sandbox (no need for external)
        if "code_exec" in required_capabilities and not requires_multi_hop:
            return self._create_local_decision(
                "Math/code execution handled locally with sandbox"
            )

        # Simple fact questions → local + quick search
        if "web_search" in required_capabilities and complexity_score < 0.6:
            return self._create_local_decision(
                "Simple fact question with quick search"
            )

        # TIER 2: Grok-4-Fast - Planning and strategy
        # Keywords: "plan", "strategy", "help me think"
        if any(tag in intent_tags for tag in ["planning", "strategy", "thinking"]):
            return self._create_external_decision(
                "grok_fast",
                "Planning/strategy query requires Grok-4-Fast"
            )

        # TIER 3: Claude Sonnet - Deep reasoning
        # Deep reasoning, analogies, creativity
        if any(tag in intent_tags for tag in ["deep_reasoning", "analogy", "creative"]):
            return self._create_external_decision(
                "sonnet",
                "Deep reasoning query requires Claude Sonnet"
            )

        # High complexity score → Sonnet
        if complexity_score >= 0.75 and not force_local:
            return self._create_external_decision(
                "sonnet",
                f"High complexity score ({complexity_score:.2f}) requires Sonnet"
            )

        # TIER 4: Claude Opus - Critical/very complex (rare)
        if "critical" in intent_tags or complexity_score >= 0.9:
            return self._create_external_decision(
                "opus",
                "Critical task requires Claude Opus"
            )

        # Default: local fast
        return self._create_local_decision(
            f"Default routing (complexity={complexity_score:.2f})"
        )

    def _create_local_decision(self, reasoning: str) -> RoutingDecision:
        """Create routing decision for local model."""
        return RoutingDecision(
            model_id="local_fast",
            model_name="qwen2.5:3b-instruct-q5_K_M",
            connector=self.local_connector,
            estimated_cost=0.0,
            routing_tier="local_fast",
            reasoning=reasoning,
        )

    def _create_external_decision(
        self, tier: str, reasoning: str
    ) -> RoutingDecision:
        """Create routing decision for external model.

        Args:
            tier: Tier name (grok_fast, sonnet, opus)
            reasoning: Explanation for routing decision

        Returns:
            RoutingDecision for external model
        """
        tier_config = self.tiers.get(tier)
        if not tier_config:
            logger.warning(f"Unknown tier '{tier}', falling back to local")
            return self._create_local_decision(f"Unknown tier fallback: {reasoning}")

        model_name = tier_config.get("model_name")
        
        # Find connector for this model
        connector = None
        for model_id, conn in self.external_connectors.items():
            if model_name in model_id or model_name.split("/")[-1] in model_id:
                connector = conn
                break

        if not connector:
            logger.warning(
                f"No connector available for {model_name}, falling back to local"
            )
            return self._create_local_decision(
                f"External model unavailable: {reasoning}"
            )

        return RoutingDecision(
            model_id=tier,
            model_name=model_name,
            connector=connector,
            estimated_cost=tier_config.get("cost", 0.0),
            routing_tier=tier,
            reasoning=reasoning,
        )

    def check_cost_status(self) -> dict[str, Any]:
        """Check current cost status against caps.

        Returns:
            Dict with cost status information
        """
        current_cost = self.cost_tracker.get_total_cost()
        cap_percentage = current_cost / self.monthly_cap if self.monthly_cap > 0 else 0

        return {
            "current_cost": current_cost,
            "monthly_cap": self.monthly_cap,
            "cap_percentage": cap_percentage,
            "soft_cap_reached": cap_percentage >= self.soft_cap_threshold,
            "hard_cap_reached": cap_percentage >= 1.0,
            "force_local": cap_percentage >= self.soft_cap_threshold,
        }
