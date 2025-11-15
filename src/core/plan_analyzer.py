"""Plan analyzer - generates structured execution plans from queries.

Uses Granite to analyze queries and produce JSON plans describing
what tools and models should be invoked.
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional

from src.core.llm_connector import LLMConnector, Message
from src.core.plan_types import (
    Plan, PlanStep, Budget, StepType,
    ComplexityLevel, SafetyLevel
)

logger = logging.getLogger(__name__)


ANALYZER_SYSTEM_PROMPT = """You are Kai's planning brain. Your job is to analyze a user's query and produce a structured JSON plan describing what needs to be done.

You must NOT answer the user's question directly. Instead, you describe which tools and models should be used, in which order, and with what inputs.

You MUST respond with a valid JSON object only. Do not include any natural language outside JSON. Do not wrap the JSON in markdown or code blocks.

Required JSON structure:
{
  "intent": "string describing what user wants",
  "complexity": "simple | moderate | complex",
  "safety_level": "normal | high | critical",
  "capabilities": ["list", "of", "required", "capabilities"],
  "steps": [
    {
      "id": "unique_step_id",
      "type": "tool_call | sanity_check | model_call | finalization",
      "tool": "tool_name or null",
      "model": "model_name or null", 
      "description": "what this step does",
      "input": {},
      "depends_on": ["list_of_step_ids"],
      "required": true,
      "can_skip_if_unavailable": false
    }
  ]
}

Available tools: web_search, code_exec, rag, sentiment
Available models for model_call: external_reasoner_fast, external_reasoner_strong

Guidelines:
- For spec verification or "check sources": add web_search step
- For math/calculations with units (Wh, Ah, miles, hours): add code_exec step
- Always add sanity_check step after calculations
- Add finalization step at the end
- Mark dependencies clearly in depends_on
- If query asks to "show work" or "verify": set safety_level to "high"
"""


class PlanAnalyzer:
    """Generates structured execution plans from queries."""
    
    def __init__(self, local_connector: LLMConnector):
        """Initialize plan analyzer.
        
        Args:
            local_connector: LLM connector for Granite
        """
        self.connector = local_connector
    
    async def analyze(self, query_text: str, context: Optional[Dict] = None) -> Plan:
        """Analyze query and generate execution plan.
        
        Args:
            query_text: User's query
            context: Optional context (conversation history, etc.)
            
        Returns:
            Plan object with steps to execute
        """
        # Build prompt
        messages = [
            Message(role="system", content=ANALYZER_SYSTEM_PROMPT),
            Message(role="user", content=query_text),
        ]
        
        try:
            # Call Granite to generate plan
            response = await self.connector.generate(
                messages=messages,
                temperature=0.3,  # Low temp for structured output
                max_tokens=1500,
            )
            
            # Parse JSON response
            plan_dict = self._parse_plan_json(response.content)
            
            if not plan_dict:
                logger.warning("Failed to parse plan JSON, using fallback")
                return self._create_fallback_plan(query_text)
            
            # Convert to Plan object
            plan = self._dict_to_plan(plan_dict, query_text)
            
            logger.info(
                f"Generated plan: intent={plan.intent}, "
                f"complexity={plan.complexity.value}, "
                f"steps={len(plan.steps)}"
            )
            
            return plan
            
        except Exception as e:
            logger.error(f"Plan analysis failed: {e}", exc_info=True)
            return self._create_fallback_plan(query_text)
    
    def _parse_plan_json(self, response: str) -> Optional[Dict]:
        """Parse JSON from LLM response.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed dict or None if failed
        """
        # Try direct JSON parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from markdown blocks
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
        
        logger.warning(f"Could not parse JSON from response: {response[:200]}...")
        return None
    
    def _dict_to_plan(self, plan_dict: Dict, query_text: str) -> Plan:
        """Convert dict to Plan object.
        
        Args:
            plan_dict: Parsed plan dictionary
            query_text: Original query
            
        Returns:
            Plan object
        """
        # Parse complexity
        complexity_str = plan_dict.get("complexity", "moderate")
        try:
            complexity = ComplexityLevel(complexity_str)
        except ValueError:
            complexity = ComplexityLevel.MODERATE
        
        # Parse safety level
        safety_str = plan_dict.get("safety_level", "normal")
        try:
            safety_level = SafetyLevel(safety_str)
        except ValueError:
            safety_level = SafetyLevel.NORMAL
        
        # Parse steps
        steps = []
        for step_dict in plan_dict.get("steps", []):
            try:
                step_type = StepType(step_dict.get("type", "tool_call"))
            except ValueError:
                step_type = StepType.TOOL_CALL
            
            step = PlanStep(
                id=step_dict.get("id", f"step_{len(steps)}"),
                type=step_type,
                tool=step_dict.get("tool"),
                model=step_dict.get("model"),
                description=step_dict.get("description", ""),
                input=step_dict.get("input", {}),
                depends_on=step_dict.get("depends_on", []),
                required=step_dict.get("required", True),
                can_skip_if_unavailable=step_dict.get("can_skip_if_unavailable", False),
            )
            steps.append(step)
        
        return Plan(
            plan_id=str(uuid.uuid4()),
            user_query=query_text,
            intent=plan_dict.get("intent", "unknown"),
            complexity=complexity,
            safety_level=safety_level,
            capabilities=plan_dict.get("capabilities", []),
            steps=steps,
        )
    
    def _create_fallback_plan(self, query_text: str) -> Plan:
        """Create simple fallback plan when analysis fails.
        
        Args:
            query_text: User query
            
        Returns:
            Simple plan with just finalization
        """
        return Plan(
            plan_id=str(uuid.uuid4()),
            user_query=query_text,
            intent="answer_query",
            complexity=ComplexityLevel.SIMPLE,
            safety_level=SafetyLevel.NORMAL,
            capabilities=[],
            steps=[
                PlanStep(
                    id="finalize",
                    type=StepType.FINALIZATION,
                    model="granite",
                    description="Answer query directly",
                    input={"query": query_text},
                    depends_on=[],
                    required=True,
                )
            ],
        )
