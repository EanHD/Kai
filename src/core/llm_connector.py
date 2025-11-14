"""Base LLM connector abstraction for swappable model interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Chat message format."""
    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    token_count: int
    cost: float
    model_used: str
    finish_reason: str  # "stop", "length", "tool_calls", etc.
    metadata: Dict[str, Any] = None


class LLMConnector(ABC):
    """Abstract base class for LLM provider implementations."""

    def __init__(self, model_config: Dict[str, Any]):
        """Initialize connector with model configuration.
        
        Args:
            model_config: Model configuration dict with provider-specific settings
        """
        self.model_config = model_config
        self.model_id = model_config.get('model_id')
        self.model_name = model_config.get('model_name')
        self.provider = model_config.get('provider')
        self.context_window = model_config.get('context_window', 4096)
        self.cost_per_1k_input = model_config.get('cost_per_1k_input', 0.0)
        self.cost_per_1k_output = model_config.get('cost_per_1k_output', 0.0)
        logger.info(f"Initialized {self.provider} connector for {self.model_name}")

    @abstractmethod
    async def generate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response from model.
        
        Args:
            messages: List of conversation messages
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters
            
        Returns:
            LLMResponse with generated content and metadata
        """
        pass

    @abstractmethod
    async def check_health(self) -> bool:
        """Check if model is available and responding.
        
        Returns:
            True if model is healthy, False otherwise
        """
        pass

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for token usage.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Total cost in USD
        """
        input_cost = (input_tokens / 1000) * self.cost_per_1k_input
        output_cost = (output_tokens / 1000) * self.cost_per_1k_output
        return input_cost + output_cost

    def get_capabilities(self) -> List[str]:
        """Get model capabilities.
        
        Returns:
            List of capability names
        """
        return self.model_config.get('capabilities', [])

    def supports_capability(self, capability: str) -> bool:
        """Check if model supports a capability.
        
        Args:
            capability: Capability name (e.g., "function_calling", "json_mode")
            
        Returns:
            True if supported, False otherwise
        """
        return capability in self.get_capabilities()
