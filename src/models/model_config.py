"""Model configuration with capabilities and routing logic."""

from dataclasses import dataclass
from typing import List, Dict, Any
from enum import Enum


class ModelCapability(str, Enum):
    """Model capability types."""
    CONCISE = "concise"  # Quick, direct answers
    WEB_SEARCH = "web_search"  # Can use web search
    RAG = "rag"  # Can retrieve from memory/docs
    EXPERT = "expert"  # Deep analysis and explanations
    ADVISOR = "advisor"  # Goal-oriented guidance
    CODE_EXEC = "code_exec"  # Can execute code
    COMPLEX_REASONING = "complex_reasoning"  # Multi-hop reasoning


class ModelProvider(str, Enum):
    """Model provider types."""
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"


@dataclass
class ModelConfig:
    """Complete model configuration with routing metadata."""
    
    # Identity
    model_id: str
    model_name: str
    provider: ModelProvider
    
    # Capabilities
    capabilities: List[ModelCapability]
    
    # Performance
    context_window: int  # Maximum context length
    speed_category: str = "fast"  # fast, medium, slow
    
    # Cost
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    is_local: bool = True
    
    # Routing
    routing_priority: int = 100  # Higher = higher priority (DESC sort)
    min_complexity_score: float = 0.0  # Minimum query complexity to use this model
    max_cost_per_query: float = 1.0  # Maximum allowed cost per query
    
    # State
    active: bool = True
    
    def has_capability(self, capability: ModelCapability) -> bool:
        """Check if model has a specific capability.
        
        Args:
            capability: Capability to check
            
        Returns:
            True if model has the capability
        """
        return capability in self.capabilities
    
    def can_handle_complexity(self, complexity_score: float) -> bool:
        """Check if model can handle query complexity.
        
        Args:
            complexity_score: Query complexity score (0.0-1.0)
            
        Returns:
            True if model can handle the complexity
        """
        return complexity_score >= self.min_complexity_score
    
    def is_cost_effective(self, estimated_tokens: int) -> bool:
        """Check if query cost is within model limits.
        
        Args:
            estimated_tokens: Estimated total tokens
            
        Returns:
            True if estimated cost is within limits
        """
        estimated_cost = (estimated_tokens / 1000.0) * max(
            self.cost_per_1k_input, self.cost_per_1k_output
        )
        return estimated_cost <= self.max_cost_per_query
    
    def get_estimated_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for token counts.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        input_cost = (input_tokens / 1000.0) * self.cost_per_1k_input
        output_cost = (output_tokens / 1000.0) * self.cost_per_1k_output
        return input_cost + output_cost
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage.
        
        Returns:
            Model config as dict
        """
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "provider": self.provider.value,
            "capabilities": [c.value for c in self.capabilities],
            "context_window": self.context_window,
            "speed_category": self.speed_category,
            "cost_per_1k_input": self.cost_per_1k_input,
            "cost_per_1k_output": self.cost_per_1k_output,
            "is_local": self.is_local,
            "routing_priority": self.routing_priority,
            "min_complexity_score": self.min_complexity_score,
            "max_cost_per_query": self.max_cost_per_query,
            "active": self.active,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelConfig":
        """Create from dictionary.
        
        Args:
            data: Model config dict
            
        Returns:
            ModelConfig instance
        """
        return cls(
            model_id=data["model_id"],
            model_name=data["model_name"],
            provider=ModelProvider(data["provider"]),
            capabilities=[ModelCapability(c) for c in data["capabilities"]],
            context_window=data["context_window"],
            speed_category=data.get("speed_category", "fast"),
            cost_per_1k_input=data.get("cost_per_1k_input", 0.0),
            cost_per_1k_output=data.get("cost_per_1k_output", 0.0),
            is_local=data.get("is_local", True),
            routing_priority=data.get("routing_priority", 100),
            min_complexity_score=data.get("min_complexity_score", 0.0),
            max_cost_per_query=data.get("max_cost_per_query", 1.0),
            active=data.get("active", True),
        )


@dataclass
class RoutingDecision:
    """Result of model routing decision."""
    
    selected_model_id: str
    reasoning: str  # Why this model was selected
    estimated_cost: float
    complexity_score: float
    fallback_models: List[str]  # Alternative models in priority order
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.
        
        Returns:
            Routing decision as dict
        """
        return {
            "selected_model_id": self.selected_model_id,
            "reasoning": self.reasoning,
            "estimated_cost": self.estimated_cost,
            "complexity_score": self.complexity_score,
            "fallback_models": self.fallback_models,
        }
