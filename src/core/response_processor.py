"""Response post-processor for cleaning up LLM outputs.

Removes internal chain-of-thought artifacts and formats for user consumption.
"""

import logging
import re

logger = logging.getLogger(__name__)


class ResponsePostProcessor:
    """Cleans and formats LLM responses for user presentation."""

    def process(self, response_text: str, metadata: dict | None = None) -> dict[str, str]:
        """Process response text and extract metadata.

        Args:
            response_text: Raw response from LLM
            metadata: Optional existing metadata dict

        Returns:
            Dict with 'text' (cleaned) and 'metadata' (extracted info)
        """
        metadata = metadata or {}

        # Extract search queries before removing tags
        searches = self._extract_searches(response_text)
        if searches:
            metadata["searches_performed"] = searches

        # Remove search tags
        cleaned = self._remove_search_tags(response_text)

        # Extract verification info
        sources = self._extract_sources(cleaned)
        if sources:
            metadata["sources_cited"] = sources

        # Clean up extra whitespace
        cleaned = self._normalize_whitespace(cleaned)

        return {
            "text": cleaned,
            "metadata": metadata,
        }

    def _extract_searches(self, text: str) -> list[str]:
        """Extract search queries from <search> tags.

        Args:
            text: Response text

        Returns:
            List of search queries
        """
        pattern = r"<search>(.*?)</search>"
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        return [m.strip() for m in matches if m.strip()]

    def _remove_search_tags(self, text: str) -> str:
        """Remove <search> tags from response.

        Args:
            text: Response text

        Returns:
            Text without search tags
        """
        # Remove search tags
        cleaned = re.sub(r"<search>.*?</search>", "", text, flags=re.IGNORECASE | re.DOTALL)

        # Also remove thinking/reasoning tags if present
        cleaned = re.sub(r"<thinking>.*?</thinking>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(
            r"<reasoning>.*?</reasoning>", "", cleaned, flags=re.IGNORECASE | re.DOTALL
        )

        return cleaned

    def _extract_sources(self, text: str) -> list[str]:
        """Extract source citations from text.

        Looks for patterns like:
        - "According to [source]"
        - "Source: [name]"
        - URLs

        Args:
            text: Response text

        Returns:
            List of source names/URLs
        """
        sources = []

        # Pattern 1: "According to X" or "Based on X"
        according_pattern = r"(?:according to|based on|per|from)\s+([A-Z][^,\.]+)"
        matches = re.findall(according_pattern, text, re.IGNORECASE)
        sources.extend(m.strip() for m in matches if len(m.strip()) > 5)

        # Pattern 2: URLs
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        urls = re.findall(url_pattern, text)
        sources.extend(urls)

        # Deduplicate while preserving order
        seen = set()
        unique_sources = []
        for source in sources:
            if source.lower() not in seen:
                seen.add(source.lower())
                unique_sources.append(source)

        return unique_sources[:5]  # Limit to first 5

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text.

        Args:
            text: Text to normalize

        Returns:
            Text with normalized whitespace
        """
        # Replace multiple newlines with max 2
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Replace multiple spaces with single space
        text = re.sub(r" {2,}", " ", text)

        # Trim leading/trailing whitespace
        text = text.strip()

        return text
