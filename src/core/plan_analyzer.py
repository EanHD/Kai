"""Plan analyzer - generates structured execution plans from queries.

Uses Granite to analyze queries and produce JSON plans describing
what tools and models should be invoked.
"""

import json
import logging
import uuid

from src.core.llm_connector import LLMConnector, Message
from src.core.plan_types import ComplexityLevel, Plan, PlanStep, SafetyLevel, StepType
from src.core.query_analyzer import QueryAnalyzer

logger = logging.getLogger(__name__)


ANALYZER_SYSTEM_PROMPT = """You are Kai's planning brain. Your job is to analyze a user's query and produce a structured JSON plan describing what needs to be done.

CONTEXT: You are planning for Kai, an AI assistant with these capabilities:
- Memory (RAG): Store and retrieve user facts, preferences, conversations
- Web Search: Look up current information via Brave/DuckDuckGo
- Code Execution: Perform calculations, get current date/time, analyze data
- Sentiment Analysis: Detect emotional tone in text

When users ask about "your memory" or "what you can do", this is a META QUESTION about Kai's capabilities - just use external_reasoner to explain, don't route to tools.

You must NOT answer the user's question directly. You MUST NOT do math or calculations yourself. Instead, you describe which tools and models should be used, in which order, and with what inputs.

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

CRITICAL RULES:
- For META QUESTIONS about Kai itself (capabilities, memory, identity): NO TOOLS, just model_call + finalization
- For type "tool_call": MUST set "tool" to a valid tool name (web_search, code_exec, rag, sentiment), NEVER null
- For type "sanity_check": set "tool" to null and "model" to null (sanity_checker is built-in)
- For type "model_call": MUST set "model" to valid model (external_reasoner_fast or external_reasoner_strong), set "tool" to null
- For type "finalization": set "tool" to null and "model" to "granite" (built-in presenter)

MANDATORY MATH ROUTING:
- You MUST NEVER do arithmetic, unit conversions, or calculations yourself
- ALL math (battery Wh/kWh, distance/time, percentages, physics, finance) MUST use code_exec
- If the query involves ANY numbers or units, you MUST route to code_exec
- Mental math is FORBIDDEN - code_exec is your calculator

CODE_EXEC INPUT SCHEMA (MANDATORY):
For any code_exec step, the "input" object MUST follow this exact schema:

{
  "language": "python",
  "mode": "task",
  "task": "short_machine_readable_name",
  "variables": {
    "param_name": value,
    "param_name2": value2
  }
}

Required fields:
- "language": ALWAYS "python"
- "mode": ALWAYS "task" (you cannot write raw code)
- "task": One of the supported task names (see below)
- "variables": Dict of parameter names to values (numbers, strings, booleans)

Supported code_exec tasks:
- "get_current_datetime": Get current date and time (for "what's the date", "what time is it", etc.)
  Variables: {} (no variables needed)
- "battery_pack_energy": Calculate Wh/kWh from cell specs
  Variables: cells_in_series, cells_in_parallel, cell_nominal_voltage_v, cell_nominal_capacity_ah
- "battery_range": Calculate range from battery and consumption
  Variables: battery_capacity_wh, consumption_wh_per_mile (or consumption_wh_per_km)
- "unit_conversion": Convert between units
  Variables: value, from_unit, to_unit
- "physics_calculation": General physics (velocity, energy, power, etc.)
  Variables: depends on formula
- "generic_math": For other calculations
  Variables: provide all numbers from the query

EXAMPLE PLAN (MANDATORY PATTERN TO FOLLOW):

Query: "If I have a 13S4P battery pack using 3400mAh cells at 3.6V nominal, what's the total energy in kWh?"

Response:
{
  "intent": "calculate_battery_pack_energy",
  "complexity": "simple",
  "safety_level": "normal",
  "capabilities": ["code_exec"],
  "steps": [
    {
      "id": "calc_energy",
      "type": "tool_call",
      "tool": "code_exec",
      "description": "Calculate total pack energy from cell configuration",
      "input": {
        "language": "python",
        "mode": "task",
        "task": "battery_pack_energy",
        "variables": {
          "cells_in_series": 13,
          "cells_in_parallel": 4,
          "cell_nominal_voltage_v": 3.6,
          "cell_nominal_capacity_ah": 3.4
        }
      },
      "depends_on": [],
      "required": true,
      "can_skip_if_unavailable": false
    },
    {
      "id": "sanity_energy",
      "type": "sanity_check",
      "tool": null,
      "model": null,
      "description": "Verify energy calculation is realistic",
      "input": {"context_step_ids": ["calc_energy"]},
      "depends_on": ["calc_energy"],
      "required": true,
      "can_skip_if_unavailable": false
    },
    {
      "id": "finalize",
      "type": "finalization",
      "tool": null,
      "model": "granite",
      "description": "Present result to user",
      "input": {},
      "depends_on": ["calc_energy", "sanity_energy"],
      "required": true,
      "can_skip_if_unavailable": false
    }
  ]
}

EXAMPLE PLAN FOR WEB SEARCH (for current information, news, facts):

Query: "What's happening with SpaceX launches this month?"

Response:
{
  "intent": "get_spacex_launch_info",
  "complexity": "simple",
  "safety_level": "normal",
  "capabilities": ["web_search"],
  "steps": [
    {
      "id": "search_launches",
      "type": "tool_call",
      "tool": "web_search",
      "model": null,
      "description": "Search for SpaceX launches",
      "input": {
        "query": "SpaceX launches November 2025"
      },
      "depends_on": [],
      "required": true,
      "can_skip_if_unavailable": false
    },
    {
      "id": "finalize",
      "type": "finalization",
      "tool": null,
      "model": "granite",
      "description": "Present result to user",
      "input": {},
      "depends_on": ["search_launches"],
      "required": true,
      "can_skip_if_unavailable": false
    }
  ]
}

IMPORTANT: For follow-up queries, expand the search query based on conversation context!
Example: If previous query was "rap concerts in San Jose" and user asks "anything in December?",
the search query should be: "rap concerts San Jose December 2025"

EXAMPLE PLAN FOR DATE/TIME QUERIES (use code_exec, NOT web_search):

Query: "What is the current date today?"

Response:
{
  "intent": "get_current_date",
  "complexity": "simple",
  "safety_level": "normal",
  "capabilities": ["code_exec"],
  "steps": [
    {
      "id": "get_date",
      "type": "tool_call",
      "tool": "code_exec",
      "model": null,
      "description": "Get current date and time",
      "input": {
        "language": "python",
        "mode": "task",
        "task": "get_current_datetime",
        "variables": {}
      },
      "depends_on": [],
      "required": true,
      "can_skip_if_unavailable": false
    },
    {
      "id": "finalize",
      "type": "finalization",
      "tool": null,
      "model": "granite",
      "description": "Present result to user",
      "input": {},
      "depends_on": ["get_date"],
      "required": true,
      "can_skip_if_unavailable": false
    }
  ]
}

Guidelines:
- For web_search: MUST include "input": {"query": "your search query here"}
- For spec verification or "check sources": add web_search step
- For ANY math/calculations with units (Wh, Ah, miles, hours, mph, etc.): add code_exec step with proper task and variables
- Always add sanity_check step after calculations (type: "sanity_check", no tool/model)
- Add finalization step at the end (type: "finalization", model: "granite")
- Mark dependencies clearly in depends_on
- If query asks to "show work" or "verify": set safety_level to "high"

REMEMBER: You are a PLANNER not a CALCULATOR. Extract numbers, identify the task, fill variables, let Python do the math.
"""


class PlanAnalyzer:
    """Generates structured execution plans from queries."""

    def __init__(self, local_connector: LLMConnector):
        """Initialize plan analyzer.

        Args:
            local_connector: LLM connector for Granite
        """
        self.connector = local_connector
        self.query_analyzer = QueryAnalyzer()

    async def analyze(
        self, query_text: str, source: str = "api", context: dict | None = None
    ) -> Plan:
        """Analyze query and generate execution plan.

        Args:
            query_text: User's query
            source: Source of query ("cli" or "api")
            context: Optional context (conversation history, etc.)

        Returns:
            Plan object with steps to execute
        """
        # Build prompt with conversation context if available
        user_content = query_text
        if context and context.get("conversation_history"):
            history = context["conversation_history"]
            if history:
                # Add recent context to help understand follow-up questions
                context_str = "\n\nRecent conversation:\n"
                for msg in history[-3:]:  # Last 3 messages
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")[:200]  # Limit length
                    context_str += f"{role}: {content}\n"
                user_content = context_str + f"\nCurrent query: {query_text}"
                logger.info(f"Added conversation context with {len(history)} messages to plan analyzer")
        
        messages = [
            Message(role="system", content=ANALYZER_SYSTEM_PROMPT),
            Message(role="user", content=user_content),
        ]
        
        logger.debug(f"Plan analyzer input: {user_content[:300]}...")

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
                return self._create_fallback_plan(query_text, source)

            # Convert to Plan object
            plan = self._dict_to_plan(plan_dict, query_text, source)

            logger.info(
                f"Generated plan: intent={plan.intent}, "
                f"complexity={plan.complexity.value}, "
                f"steps={len(plan.steps)}"
            )

            return plan

        except Exception as e:
            logger.error(f"Plan analysis failed: {e}", exc_info=True)
            return self._create_fallback_plan(query_text, source)

    def _parse_plan_json(self, response: str) -> dict | None:
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

        logger.warning(f"Could not parse JSON from response: {response[:200]}...")
        return None

    def _dict_to_plan(self, plan_dict: dict, query_text: str, source: str = "api") -> Plan:
        """Convert dict to Plan object.

        Args:
            plan_dict: Parsed plan dictionary
            query_text: Original query
            source: Source of query ("cli" or "api")

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
            source=source,
            intent=plan_dict.get("intent", "unknown"),
            complexity=complexity,
            safety_level=safety_level,
            capabilities=plan_dict.get("capabilities", []),
            steps=steps,
        )

    def _create_fallback_plan(self, query_text: str, source: str = "api") -> Plan:
        """Create simple fallback plan when analysis fails.

        Uses QueryAnalyzer to detect required capabilities even when
        LLM-based planning fails.

        Args:
            query_text: User query
            source: Source of query ("cli" or "api")

        Returns:
            Plan with detected capabilities
        """
        # Use query analyzer to detect capabilities
        analysis = self.query_analyzer.analyze(query_text)
        required_caps = analysis.get("required_capabilities", [])

        # Create steps based on detected capabilities
        steps = []
        step_id = 1

        # Add code execution step if needed
        if "code_exec" in required_caps:
            steps.append(
                PlanStep(
                    id=f"code_exec_{step_id}",
                    type=StepType.TOOL_CALL,
                    tool="code_exec",
                    model="granite",
                    description="Execute calculation",
                    input={
                        "language": "python",
                        "mode": "task",
                        "task": "generic_math",
                        "variables": {"query": query_text},
                    },
                    depends_on=[],
                    required=True,
                )
            )
            step_id += 1

        # Add web search step if needed
        if "web_search" in required_caps:
            steps.append(
                PlanStep(
                    id=f"web_search_{step_id}",
                    type=StepType.TOOL_CALL,
                    tool="web_search",
                    model="granite",
                    description="Search for information",
                    input={"query": query_text},
                    depends_on=[],
                    required=True,
                )
            )
            step_id += 1

        # Add finalization step
        depends_on = [step.id for step in steps]
        steps.append(
            PlanStep(
                id="finalize",
                type=StepType.FINALIZATION,
                model="granite",
                description="Present results",
                input={"query": query_text},
                depends_on=depends_on,
                required=True,
            )
        )

        logger.info(f"Created fallback plan with capabilities: {required_caps}")

        return Plan(
            plan_id=str(uuid.uuid4()),
            user_query=query_text,
            source=source,
            intent="answer_query",
            complexity=ComplexityLevel.SIMPLE,
            safety_level=SafetyLevel.NORMAL,
            capabilities=required_caps,
            steps=steps,
        )
