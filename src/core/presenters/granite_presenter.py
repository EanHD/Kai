"""Granite presenter - finalizes responses in Kai's voice.

Takes structured results and generates natural language answers.
"""

import json
import logging
from typing import Any

from src.core.llm_connector import LLMConnector, Message
from src.core.plan_types import FinalizationOutput

logger = logging.getLogger(__name__)


PRESENTER_SYSTEM_PROMPT = """You are Kai, a practical AI assistant.

Format results into natural answers. Respond with ONLY valid JSON - no markdown code blocks, no extra text.

Format:
{
  "final_answer": "Direct answer using facts from results. Cite sources [1] [2]. No bold, no headings, just plain text.",
  "short_summary": "one sentence summary",
  "citations_used": [1, 2]
}

Rules:
- Plain text only - no ** bold **, no ## headings, no bullet points
- Cite sources with [1] [2] after facts
- Be concise and direct
- JSON only - no markdown wrapper
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
                max_tokens=800,  # Reduced for faster responses
            )

            # Log raw response for debugging
            logger.debug(f"Granite presenter raw output:\n{response.content}")

            # Parse response
            output_dict = self._parse_finalization_json(response.content)

            if not output_dict:
                logger.error("Failed to parse finalization JSON, using fallback")
                return self._create_fallback_output(
                    original_query, tool_results, specialist_results, raw_response=response.content
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

    async def finalize_stream(
        self,
        original_query: str,
        plan: dict[str, Any],
        tool_results: dict[str, Any],
        specialist_results: dict[str, Any],
        conversation_history: list[dict[str, Any]] | None = None,
        style_profile: str = "kai_default",
    ):
        """Stream final answer from structured results.

        Args:
            original_query: User's original query
            plan: Execution plan
            tool_results: Results from tools
            specialist_results: Results from specialists
            conversation_history: Recent conversation messages
            style_profile: Style profile to use

        Yields:
            Content chunks as they are generated
        """
        # Build citation map
        citation_map = self._build_citation_map(tool_results, specialist_results)

        # Serialize specialist results
        serialized_specialist_results = {}
        for key, value in specialist_results.items():
            if hasattr(value, "to_dict"):
                serialized_specialist_results[key] = value.to_dict()
            elif isinstance(value, dict):
                serialized_specialist_results[key] = value
            else:
                serialized_specialist_results[key] = str(value)

        # Build simplified input
        simplified_input = {
            "original_query": original_query,
            "tool_results": tool_results,
            "citations": citation_map,
            "conversation_history": conversation_history or [],
        }

        # Call Granite presenter in streaming mode
        messages = [
            Message(role="system", content=PRESENTER_SYSTEM_PROMPT),
            Message(role="user", content=json.dumps(simplified_input, indent=2)),
        ]

        try:
            # Stream from connector
            async for chunk in self.connector.generate_stream(
                messages=messages,
                temperature=0.5,
                max_tokens=800,
            ):
                yield chunk

        except Exception as e:
            logger.error(f"Streaming finalization failed: {e}", exc_info=True)
            # Fallback to simple answer
            fallback_msg = "I apologize, but I encountered an error formatting the response."
            for char in fallback_msg:
                yield char

    def _create_fallback_output(
        self,
        query: str,
        tool_results: dict[str, Any],
        specialist_results: dict[str, Any],
        raw_response: str | None = None,
    ) -> FinalizationOutput:
        """Create fallback output when finalization fails.

        Args:
            query: Original query
            tool_results: Tool results
            specialist_results: Specialist results
            raw_response: Raw model response that failed JSON parsing

        Returns:
            Basic FinalizationOutput
        """
        # If we have a raw_response that looks like actual content (not JSON),
        # use it directly - Granite sometimes generates good answers without JSON wrapper
        if raw_response and len(raw_response) > 50 and not raw_response.strip().startswith("{"):
            # Clean up any JSON attempts at the end
            cleaned_response = raw_response
            if "```" in cleaned_response:
                # Remove code blocks
                import re
                cleaned_response = re.sub(r"```[\w]*\n.*?\n```", "", cleaned_response, flags=re.DOTALL)
            
            return FinalizationOutput(
                final_answer=cleaned_response.strip(),
                short_summary="Response from search results",
                citations_used=list(range(1, 6)),  # Assume up to 5 citations
                debug_info={"fallback": "used_raw_response", "reason": "json_parse_failed"},
            )
        
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
                            citations.append(
                                {
                                    "id": i,
                                    "label": title,
                                    "url": url,
                                }
                            )

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
            # Last resort: use the raw response if it looks like actual content
            # (Granite sometimes generates good answers but not in JSON format)
            final_answer = (
                "I apologize, but I encountered a formatting issue. "
                "Please try rephrasing your question."
            )
            summary = "Error in response generation"
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
