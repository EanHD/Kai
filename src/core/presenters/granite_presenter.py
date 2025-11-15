"""Granite presenter - finalizes responses in Kai's voice.

Takes structured results and generates natural language answers.
"""

import json
import logging
from typing import Dict, Any, Optional

from src.core.llm_connector import LLMConnector, Message
from src.core.plan_types import FinalizationInput, FinalizationOutput

logger = logging.getLogger(__name__)


PRESENTER_SYSTEM_PROMPT = """You are Kai's voice. Your job is to take structured results from tools and specialist models and turn them into a clear, honest, user-facing answer.

You must:
- Use only the data provided in the structured input
- Do not invent new numbers or facts
- Explain calculations step-by-step, but concisely
- Mention uncertainty if confidence is not high
- Use citations [1], [2], etc. when referring to specific external sources
- Keep the tone: practical, direct, helpful

You will receive a JSON object with:
- original_query: the user's question
- plan: the execution plan that was followed
- tool_results: results from web search, code execution, etc.
- specialist_results: verification data from external models
- citation_map: list of sources to reference

You must respond with a JSON object containing:
{
  "final_answer": "natural language answer in Kai's voice",
  "short_summary": "one or two sentence TL;DR",
  "citations_used": [1, 2]
}

Guidelines:
- If confidence is "low": mention uncertainty explicitly
- If calculations were performed: show the key steps
- If sources were checked: reference them as [1], [2]
- If verification failed: be honest about limitations
- Keep it concise but complete

Do NOT include any additional fields. Do NOT output markdown around the JSON.
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
        plan: Dict[str, Any],
        tool_results: Dict[str, Any],
        specialist_results: Dict[str, Any],
        style_profile: str = "kai_default",
    ) -> FinalizationOutput:
        """Generate final answer from structured results.
        
        Args:
            original_query: User's original query
            plan: Execution plan that was followed
            tool_results: Results from tool executions
            specialist_results: Results from specialist models
            style_profile: Style profile to use
            
        Returns:
            FinalizationOutput with final answer
        """
        # Build citation map
        citation_map = self._build_citation_map(tool_results, specialist_results)
        
        # Build finalization input
        finalization_input = FinalizationInput(
            task="finalize_answer",
            style_profile=style_profile,
            original_query=original_query,
            plan=plan,
            tool_results=tool_results,
            specialist_results=specialist_results,
            citation_map=citation_map,
        )
        
        # Call Granite presenter
        messages = [
            Message(role="system", content=PRESENTER_SYSTEM_PROMPT),
            Message(
                role="user",
                content=json.dumps(finalization_input.__dict__, indent=2)
            ),
        ]
        
        try:
            response = await self.connector.generate(
                messages=messages,
                temperature=0.5,  # Balanced for natural language
                max_tokens=1500,
            )
            
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
            return self._create_fallback_output(
                original_query, tool_results, specialist_results
            )
    
    def _build_citation_map(
        self,
        tool_results: Dict[str, Any],
        specialist_results: Dict[str, Any],
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
        for step_id, result in tool_results.items():
            if result.get("status") == "success":
                data = result.get("data", {})
                if "citations" in data:
                    for citation in data["citations"]:
                        citations.append({
                            "id": citation_id,
                            "label": citation.get("title", "Source"),
                            "url": citation.get("url", ""),
                        })
                        citation_id += 1
        
        # Extract from specialist verification
        if "verification" in specialist_results:
            verification = specialist_results["verification"]
            if hasattr(verification, "verified_specs") and verification.verified_specs:
                for source in verification.verified_specs.sources:
                    citations.append({
                        "id": citation_id,
                        "label": source.label,
                        "url": source.url,
                    })
                    citation_id += 1
        
        return citations
    
    def _parse_finalization_json(self, response: str) -> Optional[Dict]:
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
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass
        
        # Try finding first { to last }
        start = response.find('{')
        end = response.rfind('}')
        
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(response[start:end+1])
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _create_fallback_output(
        self,
        query: str,
        tool_results: Dict[str, Any],
        specialist_results: Dict[str, Any],
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
        
        # Check for code execution results
        for step_id, result in tool_results.items():
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
            final_answer = "\n\n".join(answer_parts)
            summary = "Results computed successfully."
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
            citations_used=[],
            debug_info={
                "fallback": True,
                "tool_count": len(tool_results),
            },
        )
