#!/usr/bin/env python3
"""Quick test to verify web search tool is initialized in API server."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.lib.config import ConfigLoader

def test_web_search_initialization():
    """Test that web search tool can be initialized from config."""
    
    # Load configuration
    config = ConfigLoader()
    
    # Get enabled tools
    enabled_tools = config.get_enabled_tools()
    
    print("✓ Config loaded successfully")
    print(f"✓ Enabled tools: {list(enabled_tools.keys())}")
    
    # Check if web_search is enabled
    if "web_search" not in enabled_tools:
        print("❌ ERROR: web_search not found in enabled tools")
        return False
    
    print("✓ web_search is enabled in config")
    
    # Try to initialize WebSearchTool
    try:
        from src.tools.web_search import WebSearchTool
        
        tool_config = enabled_tools["web_search"]
        web_search_config = {
            "max_results": tool_config.config.get("max_results", 10),
            "timeout_seconds": tool_config.config.get("timeout_seconds", 15),
            "max_days_old": tool_config.config.get("max_days_old", 30),
            "api_key": config.get_env("brave_api_key"),
            "tavily_api_key": config.get_env("tavily_api_key"),
        }
        
        tool = WebSearchTool(web_search_config)
        print("✓ WebSearchTool initialized successfully")
        print(f"  - Tool name: {tool.tool_name}")
        print(f"  - Max results: {tool.max_results}")
        print(f"  - Timeout: {tool.timeout_seconds}s")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize WebSearchTool: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing web search tool initialization...")
    print("=" * 50)
    
    success = test_web_search_initialization()
    
    print("=" * 50)
    if success:
        print("✅ All tests passed! Web search tool can be initialized.")
        sys.exit(0)
    else:
        print("❌ Test failed!")
        sys.exit(1)
