"""Plan executor - executes plans with dependency resolution.

Coordinates tool execution, sanity checking, and specialist escalation.
"""

import logging
from collections import defaultdict
from typing import Any

from src.core.plan_types import (
    Plan,
    PlanStep,
    SafetyLevel,
    StepType,
)
from src.core.sanity_checker import SanityChecker
from src.core.specialists.verification import SpecialistVerifier

logger = logging.getLogger(__name__)


class PlanExecutor:
    """Executes plans with dependency-aware step ordering."""

    def __init__(
        self,
        tools: dict[str, Any],
        sanity_checker: SanityChecker,
        specialist_verifier: SpecialistVerifier,
    ):
        """Initialize plan executor.

        Args:
            tools: Available tools (web_search, code_exec, etc.)
            sanity_checker: Sanity checker for validation
            specialist_verifier: Specialist verifier for escalation
        """
        self.tools = tools
        self.sanity_checker = sanity_checker
        self.specialist_verifier = specialist_verifier

    async def execute(self, plan: Plan) -> dict[str, Any]:
        """Execute a plan and return results.

        Args:
            plan: Plan to execute

        Returns:
            Dict with tool_results and specialist_results
        """
        logger.info(f"Executing plan {plan.plan_id} with {len(plan.steps)} steps")

        # Validate plan before execution
        validation_error = self._validate_plan(plan)
        if validation_error:
            logger.error(f"Plan validation failed: {validation_error}")
            return {
                "tool_results": {
                    "validation_error": {
                        "status": "failed",
                        "error": validation_error,
                        "data": {},
                    }
                },
                "specialist_results": {},
            }

        # Resolve dependencies and order steps
        ordered_steps = self._topological_sort(plan.steps)

        if not ordered_steps:
            logger.error("Failed to resolve step dependencies - circular dependency detected")
            return {
                "tool_results": {},
                "specialist_results": {
                    "error": {
                        "type": "circular_dependency",
                        "message": "Plan contains circular dependencies",
                    }
                },
            }

        # Execute steps in order
        tool_results = {}
        specialist_results = {}
        sanity_result = None

        for step in ordered_steps:
            logger.info(f"Executing step: {step.id} ({step.type.value})")

            if step.type == StepType.TOOL_CALL:
                result = await self._execute_tool_step(step, tool_results)
                tool_results[step.id] = result

            elif step.type == StepType.SANITY_CHECK:
                sanity_result = self._execute_sanity_step(step, tool_results, plan.user_query)
                tool_results[step.id] = sanity_result

                # If sanity fails, escalate to specialist
                if sanity_result.get("suspicious", False):
                    logger.warning(
                        f"Sanity check failed with {len(sanity_result.get('issues', []))} issues"
                    )

                    # Decide which specialist to use
                    use_strong = (
                        plan.safety_level != SafetyLevel.NORMAL
                        or sanity_result.get("severity") == "high"
                    )

                    verification = await self.specialist_verifier.verify(
                        original_query=plan.user_query,
                        plan=plan.to_dict(),
                        tool_results=tool_results,
                        sanity_result=sanity_result,
                        use_strong_model=use_strong,
                    )

                    specialist_results["verification"] = verification

            elif step.type == StepType.MODEL_CALL:
                # External reasoner call (for complex queries without sanity issues)
                # Use fast model unless safety_level is high
                use_strong = plan.safety_level != SafetyLevel.NORMAL

                verification = await self.specialist_verifier.verify(
                    original_query=plan.user_query,
                    plan=plan.to_dict(),
                    tool_results=tool_results,
                    sanity_result=sanity_result or {"suspicious": False, "issues": []},
                    use_strong_model=use_strong,
                )

                specialist_results[step.id] = verification

            # Finalization step is handled by presenter, not executor

        return {
            "tool_results": tool_results,
            "specialist_results": specialist_results,
        }

    async def _execute_tool_step(
        self, step: PlanStep, previous_results: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a tool call step.

        Args:
            step: Tool call step
            previous_results: Results from previous steps

        Returns:
            Tool result dict
        """
        tool_name = step.tool

        if not tool_name or tool_name not in self.tools:
            logger.error(
                f"Tool '{tool_name}' not available | "
                f"step_id={step.id} | step_type={step.type} | "
                f"available_tools={list(self.tools.keys())}"
            )

            if step.required and not step.can_skip_if_unavailable:
                return {
                    "status": "failed",
                    "error": f"Required tool '{tool_name}' not available. Available tools: {list(self.tools.keys())}",
                    "data": {},
                }
            else:
                return {
                    "status": "skipped",
                    "error": f"Optional tool '{tool_name}' not available",
                    "data": {},
                }

        # Prepare tool input
        tool_input = self._prepare_tool_input(step.input, previous_results)

        try:
            # Execute tool
            tool = self.tools[tool_name]
            result = await tool.execute_with_fallback(tool_input)

            # Convert to dict
            return {
                "status": "success" if result.status.value == "success" else "failed",
                "data": result.data,
                "error": result.error,
                "execution_time_ms": result.execution_time_ms,
            }

        except Exception as e:
            logger.error(f"Tool '{tool_name}' execution failed: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "data": {},
            }

    def _execute_sanity_step(
        self,
        step: PlanStep,
        tool_results: dict[str, Any],
        query_text: str,
    ) -> dict[str, Any]:
        """Execute a sanity check step.

        Args:
            step: Sanity check step
            tool_results: Results from tool executions
            query_text: Original query

        Returns:
            Sanity check result
        """
        # Collect relevant results based on context_step_ids
        context_steps = step.input.get("context_step_ids", [])

        # Build response text from tool results
        response_parts = []
        for step_id in context_steps:
            if step_id in tool_results:
                result = tool_results[step_id]
                if result.get("status") == "success":
                    data = result.get("data", {})
                    # Extract text content
                    if "stdout" in data:
                        response_parts.append(data["stdout"])
                    elif "results" in data:
                        response_parts.append(str(data["results"]))

        response_text = "\n".join(response_parts)

        # Run sanity check
        sanity_result = self.sanity_checker.check_response(
            response_text=response_text,
            query_text=query_text,
        )

        return sanity_result

    def _prepare_tool_input(
        self, step_input: dict[str, Any], previous_results: dict[str, Any]
    ) -> dict[str, Any]:
        """Prepare tool input by resolving references to previous results.

        Args:
            step_input: Raw step input (may contain FROM_step_id references)
            previous_results: Results from previous steps

        Returns:
            Resolved input dict
        """
        resolved = {}

        for key, value in step_input.items():
            if isinstance(value, str) and value.startswith("FROM_"):
                # Reference to previous step result
                step_id = value[5:]  # Remove "FROM_" prefix
                if step_id in previous_results:
                    result = previous_results[step_id]
                    # Try to extract the relevant field
                    if "data" in result:
                        # For now, just use the whole data dict
                        # TODO: support more specific field extraction
                        resolved[key] = result["data"]
                    else:
                        resolved[key] = result
                else:
                    logger.warning(f"Reference to unknown step: {step_id}")
                    resolved[key] = value
            else:
                resolved[key] = value

        return resolved

    def _validate_plan(self, plan: Plan) -> str | None:
        """Validate plan for common issues.

        Args:
            plan: Plan to validate

        Returns:
            Error message if invalid, None if valid
        """
        # Check if plan requires math but has no code_exec step
        math_indicators = [
            "wh",
            "kwh",
            "ah",
            "mah",
            "voltage",
            "capacity",
            "energy",
            "miles",
            "km",
            "mph",
            "kph",
            "distance",
            "range",
            "calculate",
            "compute",
            "how many",
            "how much",
            "percentage",
            "%",
            "multiply",
            "divide",
            "total",
        ]

        query_lower = plan.user_query.lower()
        has_math_indicators = any(indicator in query_lower for indicator in math_indicators)

        # Check if plan has code_exec step
        has_code_exec = any(
            step.type == StepType.TOOL_CALL and step.tool == "code_exec" for step in plan.steps
        )

        # If query looks like math but plan has no code_exec, that's suspicious
        if has_math_indicators and not has_code_exec:
            logger.warning(
                f"Plan for math query '{plan.user_query[:50]}...' has no code_exec step. "
                "This may result in incorrect mental math."
            )
            # Don't fail the plan, just log warning
            # In the future, we could inject a code_exec step here

        # Check code_exec steps have valid input schema
        for step in plan.steps:
            if step.type == StepType.TOOL_CALL and step.tool == "code_exec":
                step_input = step.input or {}

                # Validate canonical schema
                if "language" not in step_input:
                    return f"Step '{step.id}': code_exec missing 'language' field"

                if "mode" not in step_input:
                    return f"Step '{step.id}': code_exec missing 'mode' field"

                mode = step_input.get("mode")
                if mode not in ["task", "raw_code"]:
                    return f"Step '{step.id}': code_exec mode must be 'task' or 'raw_code', got '{mode}'"

                if mode == "task" and "task" not in step_input:
                    return f"Step '{step.id}': code_exec mode='task' requires 'task' field"

                if mode == "raw_code" and "code" not in step_input:
                    return f"Step '{step.id}': code_exec mode='raw_code' requires 'code' field"

        return None

    def _topological_sort(self, steps: list[PlanStep]) -> list[PlanStep] | None:
        """Sort steps based on dependencies.

        Args:
            steps: List of steps to sort

        Returns:
            Ordered list of steps, or None if circular dependency
        """
        # Build dependency graph
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        step_map = {step.id: step for step in steps}

        for step in steps:
            if step.id not in in_degree:
                in_degree[step.id] = 0

            for dep in step.depends_on:
                graph[dep].append(step.id)
                in_degree[step.id] += 1

        # Find steps with no dependencies
        queue = [step_id for step_id in step_map.keys() if in_degree[step_id] == 0]
        result = []

        while queue:
            # Get step with no remaining dependencies
            current_id = queue.pop(0)
            result.append(step_map[current_id])

            # Reduce in-degree for dependent steps
            for neighbor in graph[current_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check if all steps were processed
        if len(result) != len(steps):
            logger.error("Circular dependency detected in plan")
            return None

        return result
