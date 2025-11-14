"""Base tool interface for capability execution."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolStatus(Enum):
    """Tool execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ToolResult:
    """Result from tool execution."""
    tool_name: str
    status: ToolStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    fallback_used: bool = False


class BaseTool(ABC):
    """Abstract base class for tool implementations."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize tool with configuration.
        
        Args:
            config: Tool-specific configuration
        """
        self.config = config
        self.tool_name = self.__class__.__name__

    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """Execute the tool with given parameters.
        
        Args:
            parameters: Tool-specific input parameters
            
        Returns:
            ToolResult with execution outcome
        """
        pass

    @abstractmethod
    async def fallback(self, parameters: Dict[str, Any], error: Exception) -> ToolResult:
        """Fallback strategy when primary execution fails.
        
        Args:
            parameters: Original parameters
            error: Exception that caused failure
            
        Returns:
            ToolResult from fallback attempt
        """
        pass

    async def execute_with_fallback(self, parameters: Dict[str, Any]) -> ToolResult:
        """Execute tool with automatic fallback on failure.
        
        Args:
            parameters: Tool input parameters
            
        Returns:
            ToolResult from primary execution or fallback
        """
        try:
            result = await self.execute(parameters)
            return result
        except Exception as e:
            logger.warning(f"{self.tool_name} primary execution failed: {e}, trying fallback")
            return await self.fallback(parameters, e)

    def validate_parameters(self, parameters: Dict[str, Any], required_fields: list) -> None:
        """Validate that required parameters are present.
        
        Args:
            parameters: Parameters to validate
            required_fields: List of required field names
            
        Raises:
            ValueError: If required fields are missing
        """
        missing = [field for field in required_fields if field not in parameters]
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")
