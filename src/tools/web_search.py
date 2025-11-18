"""Web search tool with Perplexity-like multi-source aggregation."""

import asyncio
import logging
import os
import time
import warnings
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import requests
from ddgs import DDGS

from src.tools.base_tool import BaseTool, ToolResult, ToolStatus

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Web search with multi-source aggregation, ranking, and filtering."""

    # Trusted domains with authority scores (Perplexity-style)
    TRUSTED_DOMAINS = {
        # News & Tech
        "techcrunch.com": 0.95,
        "arstechnica.com": 0.95,
        "theverge.com": 0.9,
        "wired.com": 0.9,
        # Events & Entertainment
        "ticketmaster.com": 0.95,
        "eventbrite.com": 0.9,
        "bandsintown.com": 0.85,
        "songkick.com": 0.85,
        # Reference
        "wikipedia.org": 0.85,
        "github.com": 0.9,
        "stackoverflow.com": 0.9,
        # News
        "reuters.com": 0.95,
        "apnews.com": 0.95,
        "bbc.com": 0.9,
        # Medium trust
        "medium.com": 0.6,
        "reddit.com": 0.5,
    }

    def __init__(self, config: dict[str, Any]):
        """Initialize web search tool.

        Args:
            config: Tool configuration with max_results, timeout, api_key, etc.
        """
        super().__init__(config)
        self.max_results = config.get("max_results", 10)
        self.timeout_seconds = config.get("timeout_seconds", 15)
        self.brave_api_key = config.get("api_key") or os.getenv("BRAVE_API_KEY")
        self.tavily_api_key = config.get("tavily_api_key") or os.getenv("TAVILY_API_KEY")
        self.max_days_old = config.get("max_days_old", 30)  # Filter old results
        self.cache = {}  # Simple in-memory cache

        # Log available sources
        sources = []
        if self.tavily_api_key:
            sources.append("Tavily AI (Perplexity-style)")
        if self.brave_api_key:
            sources.append("Brave Search")
        sources.append("DuckDuckGo (fallback)")

        logger.info(f"Web search initialized with sources: {', '.join(sources)}")

    async def execute(self, parameters: dict[str, Any]) -> ToolResult:
        """Execute web search with multi-source aggregation.

        Args:
            parameters: Dict with 'query' key

        Returns:
            ToolResult with ranked, filtered search results
        """
        start_time = time.time()

        # Check offline mode BEFORE attempting any network calls
        offline_mode = self.config.get("offline_mode", False)
        if offline_mode:
            logger.warning("🔌 OFFLINE MODE | Web search disabled")
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.FAILED,
                error="Web search disabled in offline mode",
                data={
                    "query": parameters.get("query", ""),
                    "offline_mode": True,
                    "reason": "System is configured to run without network access",
                },
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

        try:
            # Validate parameters
            self.validate_parameters(parameters, ["query"])
            query = parameters["query"]

            # Check cache
            cache_key = f"search:{query}:{self.max_days_old}"
            if cache_key in self.cache:
                logger.info(f"Cache hit for search: {query}")
                elapsed_ms = int((time.time() - start_time) * 1000)
                return ToolResult(
                    tool_name=self.tool_name,
                    status=ToolStatus.SUCCESS,
                    data=self.cache[cache_key],
                    execution_time_ms=elapsed_ms,
                    fallback_used=True,
                )

            # Enhance query with date context (Perplexity-style)
            enhanced_query = self._enhance_query(query)
            if enhanced_query != query:
                logger.info(f"Enhanced query: '{query}' → '{enhanced_query}'")

            # Search multiple sources in parallel
            all_results = await self._parallel_search(enhanced_query)

            # Check if we got zero results (likely offline)
            if not all_results:
                logger.warning(f"No search results returned (offline?): {query}")
                return ToolResult(
                    tool_name=self.tool_name,
                    status=ToolStatus.FAILED,
                    error="No search results available. This may indicate network connectivity issues.",
                    data={
                        "query": query,
                        "offline_mode": True,
                        "suggestions": [
                            "Check your internet connection",
                            "Verify firewall/proxy settings",
                            "Try again later",
                        ],
                    },
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            # Filter by date (only recent results)
            if self.max_days_old:
                all_results = self._filter_by_date(all_results, self.max_days_old)

            # Rank by authority and relevance
            all_results = self._rank_results(all_results)

            # Take top N results
            top_results = all_results[: self.max_results]

            # Parse into citation format
            citations = []
            for result in top_results:
                citations.append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "snippet": result.get("snippet", ""),
                        "source": result.get("source", ""),
                        "score": result.get("final_score", 0.5),
                    }
                )

            # Prepare output
            output = {
                "citations": citations,
                "query": query,
                "enhanced_query": enhanced_query,
                "sources_used": self._get_sources_used(top_results),
                "total_results": len(all_results),
            }

            # Cache results
            self.cache[cache_key] = output

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Search completed: {len(citations)} results in {elapsed_ms}ms "
                f"from {', '.join(output['sources_used'])}"
            )

            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.SUCCESS,
                data=output,
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

    def _enhance_query(self, query: str) -> str:
        """Enhance query with date context for time-sensitive searches.

        Args:
            query: Original search query

        Returns:
            Enhanced query with date/time context
        """
        enhanced = query
        query_lower = query.lower()
        current_month = datetime.now().strftime("%B %Y")

        # Time-sensitive keywords
        time_words = [
            "latest",
            "new",
            "upcoming",
            "recent",
            "today",
            "now",
            "concert",
            "event",
            "show",
            "festival",
            "happening",
            "current",
        ]

        # Check if query is time-sensitive
        is_time_sensitive = any(word in query_lower for word in time_words)

        # Check if date is already included
        has_date = any(
            month in query_lower
            for month in [
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
                "2024",
                "2025",
                "2026",
            ]
        )

        # Add current month/year if time-sensitive and no date present
        if is_time_sensitive and not has_date:
            enhanced = f"{query} {current_month}"

        return enhanced

    async def _parallel_search(self, query: str) -> list[dict[str, Any]]:
        """Search multiple sources in parallel (Perplexity-style).

        Args:
            query: Search query

        Returns:
            Combined and deduplicated results from all sources
        """
        tasks = []

        # Add all available search sources
        if self.tavily_api_key:
            tasks.append(self._search_tavily(query))

        if self.brave_api_key:
            tasks.append(self._search_brave(query))

        # Always include DuckDuckGo as free fallback
        tasks.append(self._search_duckduckgo(query))

        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results
        combined = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Search source failed: {result}")
                continue
            if isinstance(result, list):
                combined.extend(result)

        # Deduplicate by URL
        seen_urls = set()
        unique = []
        for item in combined:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(item)

        logger.debug(f"Parallel search: {len(combined)} total → {len(unique)} unique results")
        return unique

    async def _search_tavily(self, query: str) -> list[dict[str, Any]]:
        """Search using Tavily AI (best for current events).

        Args:
            query: Search query

        Returns:
            List of search results
        """
        url = "https://api.tavily.com/search"
        headers = {"Content-Type": "application/json"}
        data = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": self.max_results,
            "include_answer": False,
        }

        logger.info(f"Searching Tavily AI: {query}")
        response = requests.post(url, headers=headers, json=data, timeout=self.timeout_seconds)
        response.raise_for_status()

        result_data = response.json()
        results = []

        for item in result_data.get("results", []):
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                    "source": "tavily",
                    "published_date": item.get("published_date"),
                    "score": item.get("score", 0.5),
                }
            )

        logger.info(f"Tavily returned {len(results)} results")
        return results

    async def _search_brave(self, query: str) -> list[dict[str, Any]]:
        """Search using Brave Search API.

        Args:
            query: Search query

        Returns:
            List of search results
        """
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": self.brave_api_key}
        params = {
            "q": query,
            "count": self.max_results,
            "freshness": "pw",  # Past week for fresher results
        }

        logger.info(f"Searching Brave: {query}")
        response = requests.get(url, headers=headers, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()

        data = response.json()
        results = []

        for result in data.get("web", {}).get("results", [])[: self.max_results]:
            results.append(
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("description", ""),
                    "source": "brave",
                    "published_date": result.get("age"),
                }
            )

        logger.info(f"Brave returned {len(results)} results")
        return results

    async def _search_duckduckgo(self, query: str) -> list[dict[str, Any]]:
        """Search using DuckDuckGo (free fallback).

        Args:
            query: Search query

        Returns:
            List of search results
        """
        logger.info(f"Searching DuckDuckGo: {query}")

        try:
            with DDGS() as ddgs:
                results = list(
                    ddgs.text(
                        query,
                        max_results=self.max_results,
                    )
                )
        except Exception as e:
            # Check if this is a network error (offline mode)
            error_str = str(e).lower()
            if any(
                indicator in error_str
                for indicator in [
                    "connection",
                    "network",
                    "timeout",
                    "unreachable",
                    "name resolution",
                    "dns",
                    "offline",
                ]
            ):
                logger.warning(f"DuckDuckGo network error (offline?): {e}")
                # Return empty results instead of raising - fallback will handle
                return []
            else:
                # Re-raise other errors
                raise

        # Parse results into standard format
        parsed = []
        for result in results:
            parsed.append(
                {
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "snippet": result.get("body", ""),
                    "source": "duckduckgo",
                }
            )

        logger.info(f"DuckDuckGo returned {len(parsed)} results")
        return parsed

    def _filter_by_date(self, results: list[dict], max_days_old: int) -> list[dict]:
        """Filter results to only recent ones (Perplexity-style).

        Args:
            results: Search results
            max_days_old: Maximum age in days

        Returns:
            Filtered results
        """
        cutoff = datetime.now() - timedelta(days=max_days_old)
        filtered = []

        for result in results:
            pub_date = result.get("published_date")

            # If no date, keep it (might be fresh)
            if not pub_date:
                filtered.append(result)
                continue

            # Try to parse date
            try:
                if isinstance(pub_date, str):
                    # Try ISO format
                    date = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                    if date > cutoff:
                        filtered.append(result)
            except (ValueError, TypeError):
                # Can't parse date, keep it anyway
                filtered.append(result)

        logger.debug(
            f"Date filter: {len(results)} → {len(filtered)} results (max {max_days_old} days)"
        )
        return filtered

    def _rank_results(self, results: list[dict]) -> list[dict]:
        """Rank results by authority and relevance (Perplexity-style).

        Args:
            results: Search results

        Returns:
            Ranked results (sorted by score)
        """
        for result in results:
            # Base score from search engine
            score = result.get("score", 0.5)

            # Domain authority boost
            url = result.get("url", "")
            domain = urlparse(url).netloc.replace("www.", "")
            authority = self.TRUSTED_DOMAINS.get(domain, 0.5)

            # Source boost (Tavily > Brave > DuckDuckGo)
            source_boost = {
                "tavily": 1.2,
                "brave": 1.0,
                "duckduckgo": 0.8,
            }.get(result.get("source", ""), 1.0)

            # Calculate final score
            result["final_score"] = score * authority * source_boost

        # Sort by final score
        return sorted(results, key=lambda x: x.get("final_score", 0), reverse=True)

    def _get_sources_used(self, results: list[dict]) -> list[str]:
        """Get list of unique sources that returned results.

        Args:
            results: Search results

        Returns:
            List of source names (e.g., ['tavily', 'brave'])
        """
        sources = set()
        for result in results:
            if source := result.get("source"):
                sources.add(source)
        return sorted(sources)

    async def fallback(self, parameters: dict[str, Any], error: Exception) -> ToolResult:
        """Fallback to cached results or basic DuckDuckGo.

        Args:
            parameters: Original parameters
            error: Exception that caused failure

        Returns:
            ToolResult from cache, DuckDuckGo, or failure
        """
        query = parameters.get("query", "")
        cache_key = f"search:{query}"

        # Try cached results first
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
            results = await self._search_duckduckgo(query)

            # Format output
            output = {
                "citations": [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", ""),
                    }
                    for r in results
                ],
                "query": query,
                "sources_used": ["duckduckgo"],
            }

            self.cache[cache_key] = output

            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.SUCCESS,
                data=output,
                execution_time_ms=0,
                fallback_used=True,
            )
        except Exception as ddg_error:
            logger.error(f"DuckDuckGo fallback also failed: {ddg_error}")

        # All fallbacks failed
        logger.warning(f"No cached results or fallback available for: {query}")
        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.FAILED,
            error=f"Search failed and no fallback available: {error}",
            execution_time_ms=0,
            fallback_used=True,
        )
