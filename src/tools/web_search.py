"""Web search tool using DuckDuckGo API."""

from typing import Dict, Any, List
from src.tools.base_tool import BaseTool, ToolResult, ToolStatus
from duckduckgo_search import DDGS
import time
import logging

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Web search tool using DuckDuckGo."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize web search tool.
        
        Args:
            config: Tool configuration with max_results, timeout, etc.
        """
        super().__init__(config)
        self.max_results = config.get("max_results", 5)
        self.timeout_seconds = config.get("timeout_seconds", 10)
        self.cache = {}  # Simple in-memory cache

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """Execute web search.
        
        Args:
            parameters: Dict with 'query' key
            
        Returns:
            ToolResult with search results
        """
        start_time = time.time()
        
        try:
            # Validate parameters
            self.validate_parameters(parameters, ["query"])
            query = parameters["query"]
            
            # Check cache
            cache_key = f"search:{query}"
            if cache_key in self.cache:
                logger.info(f"Cache hit for search: {query}")
                elapsed_ms = int((time.time() - start_time) * 1000)
                return ToolResult(
                    tool_name=self.tool_name,
                    status=ToolStatus.SUCCESS,
                    data=self.cache[cache_key],
                    execution_time_ms=elapsed_ms,
                    fallback_used=True,  # Cache is a fallback
                )
            
            # Perform search
            logger.info(f"Searching DuckDuckGo for: {query}")
            
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=self.max_results,
                ))
            
            # Parse results into citation format
            citations = []
            for result in results:
                citations.append({
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "snippet": result.get("body", ""),
                })
            
            # Cache results
            self.cache[cache_key] = {"citations": citations, "query": query}
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Search completed in {elapsed_ms}ms, found {len(citations)} results")
            
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.SUCCESS,
                data={"citations": citations, "query": query},
                execution_time_ms=elapsed_ms,
            )
        
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Web search failed: {e}")
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.FAILED,
                error=str(e),
                execution_time_ms=elapsed_ms,
            )

    async def fallback(self, parameters: Dict[str, Any], error: Exception) -> ToolResult:
        """Fallback to cached results if available.
        
        Args:
            parameters: Original parameters
            error: Exception that caused failure
            
        Returns:
            ToolResult from cache or failure
        """
        query = parameters.get("query", "")
        cache_key = f"search:{query}"
        
        # Try to use cached results
        if cache_key in self.cache:
            logger.info(f"Using cached results for failed search: {query}")
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.SUCCESS,
                data=self.cache[cache_key],
                execution_time_ms=0,
                fallback_used=True,
            )
        
        # No cache available
        logger.warning(f"No cached results available for: {query}")
        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.FAILED,
            error=f"Search failed and no cached results: {error}",
            execution_time_ms=0,
            fallback_used=True,
        )
