"""Granite presenter - finalizes responses in Kai's voice.

Takes structured results and generates natural language answers.
"""

import json
import logging
from typing import Any

from src.core.llm_connector import LLMConnector, Message
from src.core.plan_types import FinalizationOutput

logger = logging.getLogger(__name__)


PRESENTER_SYSTEM_PROMPT = """You are Kai, a knowledgeable and friendly assistant helping someone with their question.

CONCISENESS RULES (CRITICAL):
- Simple factual questions ("what is X?", "who is Y?", "when was Z?"): Answer in ONE sentence maximum.
- General questions: Answer in 3-5 sentences maximum.
- Complex questions or when specifically asked for detail: Provide more depth.

Do NOT:
- Use markdown formatting (**, __, *, etc.)
- Create tables or lists with special characters
- Add unnecessary preambles like "Here's what I found" or "Let me explain"
- Be overly formal or robotic
- Include citation details unless specifically asked (just answer the question)

DO:
- Give direct, helpful answers
- Be conversational and warm
- Get straight to the point
- Show personality when appropriate

CONVERSATION CONTEXT AWARENESS:
If you receive conversation_history, USE IT to understand what the user is referring to. 
When they say "it", "that", "the sensor", "the part", look back at recent messages to identify the specific item.
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
                temperature=0.3,  # Focused for concise output
                max_tokens=2048,  # Allow longer formatted responses
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
            final_answer = output_dict.get("final_answer", "")
            
            # Strip any markdown that slipped through for clean prose
            final_answer = self._strip_markdown(final_answer)
            
            return FinalizationOutput(
                final_answer=final_answer,
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

    def _strip_markdown(self, text: str) -> str:
        """Remove any markdown formatting for clean book-like prose.

        Args:
            text: Text that may contain markdown

        Returns:
            Clean text without markdown formatting
        """
        import re

        # Remove bold/italic markers
        text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
        text = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', text)

        # Remove headers (keep the text)
        text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)

        # Remove code blocks
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # Remove horizontal rules
        text = re.sub(r'^[\-_*]{3,}$', '', text, flags=re.MULTILINE)

        # Remove blockquotes
        text = re.sub(r'^>\s*(.+)$', r'\1', text, flags=re.MULTILINE)

        # Remove markdown tables (pipe-delimited)
        text = re.sub(r'^\|.+\|\s*$', '', text, flags=re.MULTILINE)  # Table rows
        text = re.sub(r'^\|[\s\-:]+\|\s*$', '', text, flags=re.MULTILINE)  # Separator rows

        # Remove list markers (convert to plain text)
        text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)

        # Clean up extra whitespace while preserving paragraph breaks
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)

        return text.strip()

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
                temperature=0.3,  # Focused for concise output
                max_tokens=2048,  # Allow longer formatted responses
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
            # Clean up any JSON attempts at the end and strip markdown
            cleaned_response = raw_response
            if "```" in cleaned_response:
                # Remove code blocks
                import re
                cleaned_response = re.sub(r"```[\w]*\n.*?\n```", "", cleaned_response, flags=re.DOTALL)
            
            # Strip all markdown for clean prose
            cleaned_response = self._strip_markdown(cleaned_response)
            
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

    async def quick_conversation_path(
        self,
        user_message: str,
        history: list[dict[str, Any]],
        quick_search_results: str | None = None,
    ):
        """Fast path for simple conversation.
        
        Args:
            user_message: The user's current message
            history: Conversation history
            quick_search_results: Optional results from a quick web search
            
        Yields:
            Streamed response tokens
        """
        system_prompt = """You are Kai, a warm, slightly sarcastic friend who sounds like a real person.
Never lecture. Keep answers short unless the user is clearly going deep.
Use contractions. Ask follow-up questions when it makes sense.
Never say "As an AI". If unsure, say "not sure, let me think..." """

        messages = [Message(role="system", content=system_prompt)]
        
        # Add history
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            messages.append(Message(role=role, content=content))
            
        # Add current message with optional search context
        content = user_message
        if quick_search_results:
            content += f"\n\nContext from quick search:\n{quick_search_results}"
            
        messages.append(Message(role="user", content=content))
        
        try:
            async for chunk in self.connector.generate_stream(
                messages=messages,
                temperature=0.7,
                max_tokens=1024
            ):
                yield chunk
        except Exception as e:
            logger.error(f"Quick conversation path failed: {e}")
            yield "I'm having a bit of trouble thinking right now. Can you ask that again?"
