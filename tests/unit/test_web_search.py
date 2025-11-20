"""Unit tests for Web Search Tool."""

import pytest
from src.lib.config import ConfigLoader
from src.tools.web_search import WebSearchTool

def test_web_search_initialization():
    """Test that web search tool can be initialized from config."""
    
    # Load configuration
    config = ConfigLoader()
    
    # Get enabled tools
    enabled_tools = config.get_enabled_tools()
    
    # Check if web_search is enabled
    assert "web_search" in enabled_tools, "web_search not found in enabled tools"
    
    # Try to initialize WebSearchTool
    tool_config = enabled_tools["web_search"]
    web_search_config = {
        "max_results": tool_config.config.get("max_results", 10),
        "timeout_seconds": tool_config.config.get("timeout_seconds", 15),
        "max_days_old": tool_config.config.get("max_days_old", 30),
        "api_key": config.get_env("brave_api_key"),
        "tavily_api_key": config.get_env("tavily_api_key"),
    }
    
    tool = WebSearchTool(web_search_config)
    
    assert tool.tool_name == "WebSearchTool"
    assert tool.max_results == web_search_config["max_results"]
    assert tool.timeout_seconds == web_search_config["timeout_seconds"]
