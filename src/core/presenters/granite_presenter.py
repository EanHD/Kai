"""Granite presenter - finalizes responses in Kai's voice.

Takes structured results and generates natural language answers.
"""

import json
import logging
from typing import Any

from src.core.llm_connector import LLMConnector, Message
from src.core.plan_types import FinalizationInput, FinalizationOutput

logger = logging.getLogger(__name__)


PRESENTER_SYSTEM_PROMPT = """You are Kai, a practical AI assistant.

Your job: Format search/code results into natural answers with citations.

YOU MUST respond with ONLY valid JSON. No markdown, no explanations, no text before/after JSON.

Response format:
{
  "final_answer": "natural answer using facts from results, cite sources like [1] [2]",
  "short_summary": "one sentence summary",
  "citations_used": [1, 2]
}

Tips:
- Use facts from tool_results
- Add citation numbers like [1] after facts
- Be direct and helpful
- If you used web search, say so
- If you calculated something, show the result
"""


class GranitePresenter:
    """Generates final user-facing responses using Granite."""

    def __init__(self, connector: LLMConnector):
        """Initialize presenter.

        Args:
            connector: LLM connector for Granite
        """
        self.connector = connector

    async def finalize(
        self,
        original_query: str,
        plan: dict[str, Any],
        tool_results: dict[str, Any],
        specialist_results: dict[str, Any],
        conversation_history: list[dict[str, Any]] | None = None,
        style_profile: str = "kai_default",
    ) -> FinalizationOutput:
        """Generate final answer from structured results.

        Args:
            original_query: User's original query
            plan: Execution plan that was followed
            tool_results: Results from tool executions
            specialist_results: Results from specialist models
            conversation_history: Recent conversation messages for context
            style_profile: Style profile to use

        Returns:
            FinalizationOutput with final answer
        """
        # Build citation map
        citation_map = self._build_citation_map(tool_results, specialist_results)

        # Serialize specialist results for JSON
        serialized_specialist_results = {}
        for key, value in specialist_results.items():
            if hasattr(value, "to_dict"):
                serialized_specialist_results[key] = value.to_dict()
            elif isinstance(value, dict):
                serialized_specialist_results[key] = value
            else:
                # Convert dataclasses and other objects
                serialized_specialist_results[key] = str(value)

        # Build finalization input - SIMPLIFIED to reduce prompt complexity
        # Only send what Granite actually needs to see
        simplified_input = {
            "original_query": original_query,
            "tool_results": tool_results,
            "citations": citation_map,
            "conversation_history": conversation_history or [],
        }
        
        # Call Granite presenter
        messages = [
            Message(role="system", content=PRESENTER_SYSTEM_PROMPT),
            Message(role="user", content=json.dumps(simplified_input, indent=2)),
        ]

        try:
            response = await self.connector.generate(
                messages=messages,
                temperature=0.5,  # Balanced for natural language
                max_tokens=1500,
            )

            # Log raw response for debugging
            logger.debug(f"Granite presenter raw output:\n{response.content}")

            # Parse response
            output_dict = self._parse_finalization_json(response.content)

            if not output_dict:
                logger.error("Failed to parse finalization JSON, using fallback")
                return self._create_fallback_output(
                    original_query, tool_results, specialist_results
                )

            # Convert to FinalizationOutput
            return FinalizationOutput(
                final_answer=output_dict.get("final_answer", ""),
                short_summary=output_dict.get("short_summary", ""),
                citations_used=output_dict.get("citations_used", []),
                debug_info={
                    "used_tools": list(tool_results.keys()),
                    "used_specialists": list(specialist_results.keys()),
                    "citation_count": len(citation_map),
                },
            )

        except Exception as e:
            logger.error(f"Finalization failed: {e}", exc_info=True)
            return self._create_fallback_output(original_query, tool_results, specialist_results)

    def _build_citation_map(
        self,
        tool_results: dict[str, Any],
        specialist_results: dict[str, Any],
    ) -> list:
        """Build citation map from results.

        Args:
            tool_results: Tool results
            specialist_results: Specialist results

        Returns:
            List of citation dicts
        """
        citations = []
        citation_id = 1

        # Extract from web search results
        for _step_id, result in tool_results.items():
            if result.get("status") == "success":
                data = result.get("data", {})
                if "citations" in data:
                    for citation in data["citations"]:
                        citations.append(
                            {
                                "id": citation_id,
                                "label": citation.get("title", "Source"),
                                "url": citation.get("url", ""),
                            }
                        )
                        citation_id += 1

        # Extract from specialist verification
        if "verification" in specialist_results:
            verification = specialist_results["verification"]
            if hasattr(verification, "verified_specs") and verification.verified_specs:
                for source in verification.verified_specs.sources:
                    citations.append(
                        {
                            "id": citation_id,
                            "label": source.label,
                            "url": source.url,
                        }
                    )
                    citation_id += 1

        return citations

    def _parse_finalization_json(self, response: str) -> dict | None:
        """Parse JSON from finalization response.

        Args:
            response: Raw response text

        Returns:
            Parsed dict or None
        """
        # Try direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown
        import re

        json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        matches = re.findall(json_pattern, response, re.DOTALL)

        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass

        # Try finding first { to last }
        start = response.find("{")
        end = response.rfind("}")

        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(response[start : end + 1])
            except json.JSONDecodeError:
                pass

        # Log the problematic response for debugging
        logger.warning(f"Failed to parse finalization JSON. Response preview: {response[:300]}...")
        return None

    def _create_fallback_output(
        self,
        query: str,
        tool_results: dict[str, Any],
        specialist_results: dict[str, Any],
    ) -> FinalizationOutput:
        """Create fallback output when finalization fails.

        Args:
            query: Original query
            tool_results: Tool results
            specialist_results: Specialist results

        Returns:
            Basic FinalizationOutput
        """
        # Try to extract something useful from results
        answer_parts = []
        citations = []

        # Check for web search results
        if "web_search" in tool_results:
            search_result = tool_results["web_search"]
            if search_result.get("status") == "success":
                data = search_result.get("data", {})
                search_citations = data.get("citations", [])
                
                if search_citations:
                    # Build answer from search results
                    answer_parts.append(f"Based on my search for '{query}':")
                    
                    # Add top 3 results
                    for i, citation in enumerate(search_citations[:3], 1):
                        title = citation.get("title", "")
                        snippet = citation.get("snippet", "")
                        url = citation.get("url", "")
                        
                        if snippet:
                            answer_parts.append(f"\n[{i}] {snippet}")
                            citations.append({
                                "id": i,
                                "label": title,
                                "url": url,
                            })
                    
                    # Add sources
                    if citations:
                        answer_parts.append("\n\nSources:")
                        for cit in citations:
                            answer_parts.append(f"[{cit['id']}] {cit['label']} - {cit['url']}")

        # Check for code execution results
        for _step_id, result in tool_results.items():
            if result.get("status") == "success":
                data = result.get("data", {})
                if "stdout" in data:
                    answer_parts.append(data["stdout"])

        # Check for verification results
        if "verification" in specialist_results:
            verification = specialist_results["verification"]
            if hasattr(verification, "error") and verification.error:
                answer_parts.append(
                    f"Note: {verification.error.get('message', 'Verification unavailable')}"
                )

        if answer_parts:
            final_answer = "\n".join(answer_parts)
            summary = "Results from search and computation."
        else:
            final_answer = (
                "I encountered an issue generating the final answer. "
                "The underlying computation may have completed, but I cannot "
                "present it reliably right now."
            )
            summary = "Answer generation failed."

        return FinalizationOutput(
            final_answer=final_answer,
            short_summary=summary,
            citations_used=[c["id"] for c in citations],
            debug_info={
                "fallback": True,
                "tool_count": len(tool_results),
                "used_search_fallback": bool(citations),
            },
        )
