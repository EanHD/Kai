"""Base tool interface for capability execution."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

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
    data: dict[str, Any] | None = None
    error: str | None = None
    execution_time_ms: int = 0
    fallback_used: bool = False


class BaseTool(ABC):
    """Abstract base class for tool implementations."""

    def __init__(self, config: dict[str, Any]):
        """Initialize tool with configuration.

        Args:
            config: Tool-specific configuration
        """
        self.config = config
        self.tool_name = self.__class__.__name__
        self.enabled = config.get("enabled", True)

    @abstractmethod
    async def execute(self, parameters: dict[str, Any]) -> ToolResult:
        """Execute the tool with given parameters.

        Args:
            parameters: Tool-specific input parameters

        Returns:
            ToolResult with execution outcome
        """
        pass

    @abstractmethod
    async def fallback(self, parameters: dict[str, Any], error: Exception) -> ToolResult:
        """Fallback strategy when primary execution fails.

        Args:
            parameters: Original parameters
            error: Exception that caused failure

        Returns:
            ToolResult from fallback attempt
        """
        pass

    async def execute_with_fallback(self, parameters: dict[str, Any]) -> ToolResult:
        """Execute tool with automatic fallback on failure.

        Args:
            parameters: Tool input parameters

        Returns:
            ToolResult from primary execution or fallback
        """
        # Check if tool is disabled
        if not self.enabled:
            logger.info(f"{self.tool_name} is disabled")
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.FAILED,
                error="Tool is disabled in configuration",
                execution_time_ms=0,
                fallback_used=False,
            )

        try:
            result = await self.execute(parameters)
            return result
        except Exception as e:
            logger.warning(f"{self.tool_name} primary execution failed: {e}, trying fallback")
            return await self.fallback(parameters, e)

    def validate_parameters(self, parameters: dict[str, Any], required_fields: list) -> None:
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
