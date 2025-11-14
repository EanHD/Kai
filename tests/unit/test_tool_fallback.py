"""Tests for tool fallback and disabled tool handling."""

import pytest
from src.tools.base_tool import BaseTool, ToolResult, ToolStatus


class MockTool(BaseTool):
    """Mock tool for testing."""
    
    async def execute(self, parameters):
        """Mock execute."""
        if parameters.get("should_fail"):
            raise ValueError("Forced failure")
        
        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.SUCCESS,
            data={"result": "success"},
            execution_time_ms=10,
        )
    
    async def fallback(self, parameters, error):
        """Mock fallback."""
        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.SUCCESS,
            data={"result": "fallback"},
            execution_time_ms=5,
            fallback_used=True,
        )


@pytest.mark.asyncio
async def test_disabled_tool():
    """Test that disabled tools return proper error."""
    tool = MockTool({"enabled": False})
    result = await tool.execute_with_fallback({"query": "test"})
    
    assert result.status == ToolStatus.FAILED
    assert "disabled" in result.error.lower()
    assert result.fallback_used is False


@pytest.mark.asyncio
async def test_enabled_tool_success():
    """Test that enabled tools execute successfully."""
    tool = MockTool({"enabled": True})
    result = await tool.execute_with_fallback({"query": "test"})
    
    assert result.status == ToolStatus.SUCCESS
    assert result.data["result"] == "success"
    assert result.fallback_used is False


@pytest.mark.asyncio
async def test_tool_fallback_on_failure():
    """Test that tools use fallback on failure."""
    tool = MockTool({"enabled": True})
    result = await tool.execute_with_fallback({"should_fail": True})
    
    assert result.status == ToolStatus.SUCCESS
    assert result.data["result"] == "fallback"
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_tool_default_enabled():
    """Test that tools are enabled by default."""
    tool = MockTool({})
    result = await tool.execute_with_fallback({"query": "test"})
    
    assert result.status == ToolStatus.SUCCESS
    assert tool.enabled is True
