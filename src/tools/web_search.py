"""Web search tool using Brave Search API with DuckDuckGo fallback."""

import logging
import os
import time
from typing import Any

import requests
from duckduckgo_search import DDGS

from src.tools.base_tool import BaseTool, ToolResult, ToolStatus

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Web search tool with Brave API primary and DuckDuckGo fallback."""

    def __init__(self, config: dict[str, Any]):
        """Initialize web search tool.

        Args:
            config: Tool configuration with max_results, timeout, api_key, etc.
        """
        super().__init__(config)
        self.max_results = config.get("max_results", 5)
        self.timeout_seconds = config.get("timeout_seconds", 10)
        self.brave_api_key = config.get("api_key") or os.getenv("BRAVE_API_KEY")
        self.cache = {}  # Simple in-memory cache
        
        # Check if Brave API is available
        if self.brave_api_key:
            logger.info("Brave Search API configured as primary search")
        else:
            logger.info("No Brave API key found, using DuckDuckGo only")

    async def execute(self, parameters: dict[str, Any]) -> ToolResult:
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

            # Try Brave Search first if API key available
            if self.brave_api_key:
                try:
                    result = await self._search_brave(query)
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    
                    # Cache results
                    self.cache[cache_key] = result
                    
                    logger.info(f"Brave search completed in {elapsed_ms}ms")
                    return ToolResult(
                        tool_name=self.tool_name,
                        status=ToolStatus.SUCCESS,
                        data=result,
                        execution_time_ms=elapsed_ms,
                    )
                except Exception as brave_error:
                    logger.warning(f"Brave search failed: {brave_error}, falling back to DuckDuckGo")

            # Fallback to DuckDuckGo
            result = await self._search_duckduckgo(query)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Cache results
            self.cache[cache_key] = result
            
            logger.info(f"DuckDuckGo search completed in {elapsed_ms}ms")
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.SUCCESS,
                data=result,
                execution_time_ms=elapsed_ms,
                fallback_used=not self.brave_api_key,  # Mark as fallback if no Brave API
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

    async def _search_brave(self, query: str) -> dict[str, Any]:
        """Search using Brave Search API.
        
        Args:
            query: Search query
            
        Returns:
            Dict with citations and query
        """
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.brave_api_key
        }
        params = {
            "q": query,
            "count": self.max_results
        }
        
        logger.info(f"Searching Brave for: {query}")
        response = requests.get(url, headers=headers, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        
        data = response.json()
        
        # Parse Brave results into citation format
        citations = []
        for result in data.get("web", {}).get("results", [])[:self.max_results]:
            citations.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("description", ""),
            })
        
        logger.info(f"Brave search found {len(citations)} results")
        return {"citations": citations, "query": query}

    async def _search_duckduckgo(self, query: str) -> dict[str, Any]:
        """Search using DuckDuckGo.
        
        Args:
            query: Search query
            
        Returns:
            Dict with citations and query
        """
        logger.info(f"Searching DuckDuckGo for: {query}")

        with DDGS() as ddgs:
            results = list(
                ddgs.text(
                    query,
                    max_results=self.max_results,
                )
            )

        # Parse results into citation format
        citations = []
        for result in results:
            citations.append(
                {
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "snippet": result.get("body", ""),
                }
            )

        logger.info(f"DuckDuckGo search found {len(citations)} results")
        return {"citations": citations, "query": query}

    async def fallback(self, parameters: dict[str, Any], error: Exception) -> ToolResult:
        """Fallback to cached results or DuckDuckGo if Brave failed.

        Args:
            parameters: Original parameters
            error: Exception that caused failure

        Returns:
            ToolResult from cache, DuckDuckGo, or failure
        """
        query = parameters.get("query", "")
        cache_key = f"search:{query}"

        # Try to use cached results first
        if cache_key in self.cache:
            logger.info(f"Using cached results for failed search: {query}")
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.SUCCESS,
                data=self.cache[cache_key],
                execution_time_ms=0,
                fallback_used=True,
            )

        # Try DuckDuckGo as final fallback
        try:
            logger.info(f"Attempting DuckDuckGo fallback for: {query}")
            result = await self._search_duckduckgo(query)
            self.cache[cache_key] = result
            
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.SUCCESS,
                data=result,
                execution_time_ms=0,
                fallback_used=True,
            )
        except Exception as ddg_error:
            logger.error(f"DuckDuckGo fallback also failed: {ddg_error}")

        # No fallback available
        logger.warning(f"No cached results or fallback available for: {query}")
        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.FAILED,
            error=f"Search failed and no fallback available: {error}",
            execution_time_ms=0,
            fallback_used=True,
        )
