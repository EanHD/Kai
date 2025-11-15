"""Code execution wrapper that integrates code generation.

This wrapper combines the CodeExecutorTool with CodeGenerator to support
both direct code execution and auto-generated code from task descriptions.
"""

import logging
from typing import Any

from src.core.code_generator import CodeGenerator
from src.tools.base_tool import BaseTool, ToolResult, ToolStatus
from src.tools.code_executor import CodeExecutorTool

logger = logging.getLogger(__name__)


class CodeExecWrapper(BaseTool):
    """Wrapper that auto-generates code when needed and executes it."""

    def __init__(self, config: dict[str, Any]):
        """Initialize wrapper with code executor and generator.

        Args:
            config: Configuration for code executor
        """
        super().__init__(config)
        self.executor = CodeExecutorTool(config)
        self.generator = CodeGenerator()

    async def execute(self, parameters: dict[str, Any]) -> ToolResult:
        """Execute code, auto-generating if needed.

        Args:
            parameters: Must follow canonical schema:
                {
                  "language": "python",
                  "mode": "task" | "raw_code",
                  "task": "task_name",  # if mode == "task"
                  "variables": {...},   # if mode == "task"
                  "code": "..."         # if mode == "raw_code"
                }

        Returns:
            ToolResult with execution output or structured error
        """
        # Validate canonical input schema
        validation_error = self._validate_input(parameters)
        if validation_error:
            return validation_error

        mode = parameters.get("mode", "task")

        # Mode: raw_code - direct execution
        if mode == "raw_code":
            if "code" not in parameters:
                return ToolResult(
                    tool_name=self.tool_name,
                    status=ToolStatus.FAILED,
                    error="mode='raw_code' requires 'code' parameter",
                    data={
                        "fix_hint": "PlanAnalyzer must include 'code' field when mode='raw_code'",
                        "received_parameters": list(parameters.keys()),
                    },
                )
            return await self.executor.execute({"code": parameters["code"]})

        # Mode: task - auto-generate from task name and variables
        if mode == "task":
            task = parameters.get("task")
            variables = parameters.get("variables", {})

            if not task:
                return ToolResult(
                    tool_name=self.tool_name,
                    status=ToolStatus.FAILED,
                    error="mode='task' requires 'task' parameter",
                    data={
                        "fix_hint": "PlanAnalyzer must include 'task' field when mode='task'",
                        "received_parameters": list(parameters.keys()),
                    },
                )

            # Execute task-based calculation
            code = self._generate_code_for_task(task, variables)

            if code:
                logger.info(f"Executing task '{task}' with variables: {list(variables.keys())}")
                return await self.executor.execute({"code": code})
            else:
                return ToolResult(
                    tool_name=self.tool_name,
                    status=ToolStatus.FAILED,
                    error=f"Unknown task: '{task}'",
                    data={
                        "task": task,
                        "supported_tasks": [
                            "battery_pack_energy",
                            "battery_range",
                            "unit_conversion",
                            "physics_calculation",
                            "generic_math",
                        ],
                        "fix_hint": "PlanAnalyzer must use a supported task name",
                    },
                )

        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.FAILED,
            error=f"Invalid mode: '{mode}'",
            data={
                "received_mode": mode,
                "supported_modes": ["task", "raw_code"],
                "fix_hint": "PlanAnalyzer must set mode to 'task' or 'raw_code'",
            },
        )

    def _validate_input(self, parameters: dict[str, Any]) -> ToolResult | None:
        """Validate canonical input schema.

        Returns:
            ToolResult error if invalid, None if valid
        """
        # Check required fields
        if "language" not in parameters:
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.FAILED,
                error="Missing required field 'language'",
                data={
                    "fix_hint": "PlanAnalyzer must include 'language': 'python' in code_exec input",
                    "received_parameters": list(parameters.keys()),
                },
            )

        if parameters["language"] != "python":
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.FAILED,
                error=f"Unsupported language: '{parameters['language']}'",
                data={
                    "supported_languages": ["python"],
                    "fix_hint": "PlanAnalyzer must set language='python'",
                },
            )

        if "mode" not in parameters:
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.FAILED,
                error="Missing required field 'mode'",
                data={
                    "fix_hint": "PlanAnalyzer must include 'mode': 'task' or 'raw_code' in code_exec input",
                    "received_parameters": list(parameters.keys()),
                },
            )

        mode = parameters["mode"]
        if mode not in ["task", "raw_code"]:
            return ToolResult(
                tool_name=self.tool_name,
                status=ToolStatus.FAILED,
                error=f"Invalid mode: '{mode}'",
                data={
                    "supported_modes": ["task", "raw_code"],
                    "fix_hint": "PlanAnalyzer must set mode to 'task' or 'raw_code'",
                },
            )

        return None

    def _generate_code_for_task(self, task: str, variables: dict[str, Any]) -> str | None:
        """Generate Python code for a named task.

        Args:
            task: Task name (e.g., "battery_pack_energy")
            variables: Task parameters

        Returns:
            Python code string or None if task unknown
        """
        # Route to task-specific handler
        task_handlers = {
            "battery_pack_energy": self._task_battery_pack_energy,
            "battery_range": self._task_battery_range,
            "unit_conversion": self._task_unit_conversion,
            "physics_calculation": self._task_physics_calculation,
            "generic_math": self._task_generic_math,
            "get_current_datetime": self._task_get_current_datetime,
        }

        handler = task_handlers.get(task)
        if handler:
            return handler(variables)

        return None

    def _task_get_current_datetime(self, variables: dict[str, Any]) -> str:
        """Generate code to get current date and time.
        
        No variables required.
        """
        return """
from datetime import datetime

# Get current datetime
now = datetime.now()

# Format output
result = {
    'date': now.strftime('%Y-%m-%d'),
    'time': now.strftime('%H:%M:%S'),
    'datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
    'day_of_week': now.strftime('%A'),
    'month': now.strftime('%B'),
    'year': now.year,
    'friendly': now.strftime('%B %d, %Y')
}

print(result)
"""

    def _task_battery_pack_energy(self, variables: dict[str, Any]) -> str:
        """Generate code for battery pack energy calculation.

        Expected variables:
        - cells_in_series: Number of cells in series
        - cells_in_parallel: Number of cells in parallel
        - cell_nominal_voltage_v: Cell voltage in volts
        - cell_nominal_capacity_ah: Cell capacity in amp-hours

        Also supports parsing from 'query' variable with XsYp notation (e.g., "14S5P").
        """
        # Check if we need to parse battery pack notation from query
        if "query" in variables and isinstance(variables["query"], str):
            import re

            query = variables["query"]

            # Try to parse XsYp notation (e.g., "14S5P", "13s4p")
            pack_match = re.search(r"(\d+)\s*[sS]\s*(\d+)\s*[pP]", query)
            if pack_match:
                variables["cells_in_series"] = int(pack_match.group(1))
                variables["cells_in_parallel"] = int(pack_match.group(2))
                logger.info(
                    f"Parsed battery pack notation: {pack_match.group(1)}S{pack_match.group(2)}P"
                )

            # Parse capacity (mAh or Ah)
            capacity_match = re.search(r"(\d+)\s*m?[aA]h", query, re.IGNORECASE)
            if capacity_match:
                capacity_value = int(capacity_match.group(1))
                # Check if it's mAh or Ah
                if "mah" in query.lower() or "ma" in query.lower():
                    variables["cell_nominal_capacity_ah"] = capacity_value / 1000.0
                else:
                    variables["cell_nominal_capacity_ah"] = float(capacity_value)
                logger.info(f"Parsed capacity: {variables['cell_nominal_capacity_ah']}Ah")

            # Parse voltage
            voltage_match = re.search(r"(\d+\.?\d*)\s*[vV]", query)
            if voltage_match:
                variables["cell_nominal_voltage_v"] = float(voltage_match.group(1))
                logger.info(f"Parsed voltage: {variables['cell_nominal_voltage_v']}V")

        code = """# Battery Pack Energy Calculation
import json

# Extract variables
cells_in_series = {cells_in_series}
cells_in_parallel = {cells_in_parallel}
cell_voltage_v = {cell_nominal_voltage_v}
cell_capacity_ah = {cell_nominal_capacity_ah}

# Calculate pack totals
total_cells = cells_in_series * cells_in_parallel
pack_voltage_v = cells_in_series * cell_voltage_v
pack_capacity_ah = cells_in_parallel * cell_capacity_ah

# Calculate energy
pack_energy_wh = pack_voltage_v * pack_capacity_ah
pack_energy_kwh = pack_energy_wh / 1000.0

# Output results
result = {{
    "total_cells": total_cells,
    "pack_voltage_v": pack_voltage_v,
    "pack_capacity_ah": pack_capacity_ah,
    "pack_energy_wh": round(pack_energy_wh, 2),
    "pack_energy_kwh": round(pack_energy_kwh, 3),
    "calculation": f"{{cells_in_series}}S{{cells_in_parallel}}P × {{cell_voltage_v}}V × {{cell_capacity_ah}}Ah = {{pack_energy_wh:.2f}}Wh ({{pack_energy_kwh:.3f}}kWh)"
}}

print(json.dumps(result, indent=2))
""".format(**variables)

        return code

    def _task_battery_range(self, variables: dict[str, Any]) -> str:
        """Generate code for battery range calculation.

        Expected variables:
        - battery_capacity_wh or battery_capacity_kwh: Battery capacity
        - consumption_wh_per_mile or consumption_wh_per_km: Energy consumption rate
        """
        # Normalize to Wh
        if "battery_capacity_kwh" in variables:
            capacity_wh = variables["battery_capacity_kwh"] * 1000
        else:
            capacity_wh = variables.get("battery_capacity_wh", 0)

        # Normalize consumption
        if "consumption_wh_per_km" in variables:
            consumption_wh = variables["consumption_wh_per_km"]
            distance_unit = "km"
        else:
            consumption_wh = variables.get("consumption_wh_per_mile", 0)
            distance_unit = "miles"

        code = f"""# Battery Range Calculation
import json

battery_capacity_wh = {capacity_wh}
consumption_wh_per_unit = {consumption_wh}
distance_unit = "{distance_unit}"

# Calculate range
if consumption_wh_per_unit > 0:
    range_distance = battery_capacity_wh / consumption_wh_per_unit
else:
    range_distance = 0

result = {{
    "battery_capacity_wh": battery_capacity_wh,
    "consumption_wh_per_unit": consumption_wh_per_unit,
    "range_distance": round(range_distance, 2),
    "distance_unit": distance_unit,
    "calculation": f"{{battery_capacity_wh}}Wh ÷ {{consumption_wh_per_unit}}Wh/{{distance_unit}} = {{range_distance:.2f}} {{distance_unit}}"
}}

print(json.dumps(result, indent=2))
"""
        return code

    def _task_unit_conversion(self, variables: dict[str, Any]) -> str:
        """Generate code for unit conversion."""
        code = """# Unit Conversion
import json

value = {value}
from_unit = "{from_unit}"
to_unit = "{to_unit}"

# Conversion factors (extend as needed)
conversions = {{
    ("wh", "kwh"): 0.001,
    ("kwh", "wh"): 1000,
    ("mah", "ah"): 0.001,
    ("ah", "mah"): 1000,
    ("mph", "ms"): 0.44704,
    ("ms", "mph"): 2.23694,
}}

key = (from_unit.lower(), to_unit.lower())
if key in conversions:
    converted_value = value * conversions[key]
    result = {{
        "original_value": value,
        "original_unit": from_unit,
        "converted_value": round(converted_value, 4),
        "converted_unit": to_unit,
        "calculation": f"{{value}} {{from_unit}} = {{converted_value:.4f}} {{to_unit}}"
    }}
else:
    result = {{"error": f"Conversion from {{from_unit}} to {{to_unit}} not supported"}}

print(json.dumps(result, indent=2))
""".format(**variables)
        return code

    def _task_physics_calculation(self, variables: dict[str, Any]) -> str:
        """Generate code for physics calculations."""
        # Build code from variables dynamically
        var_assignments = [f"{k} = {v}" for k, v in variables.items()]

        code = f"""# Physics Calculation
import json

{chr(10).join(var_assignments)}

# Perform calculation (customize based on variables)
result = {{
    "variables": {variables},
    "note": "Physics calculation executed"
}}

print(json.dumps(result, indent=2))
"""
        return code

    def _task_generic_math(self, variables: dict[str, Any]) -> str:
        """Generate code for generic math operations.

        If 'query' variable is present, tries to parse battery pack notation
        and route to battery_pack_energy calculation.
        """
        # Check if this looks like a battery calculation
        if "query" in variables and isinstance(variables["query"], str):
            import re

            query = variables["query"]

            # If we detect battery pack notation, route to battery task
            if re.search(r"\d+\s*[sS]\s*\d+\s*[pP]", query):
                logger.info(
                    "Generic math detected battery pack notation, routing to battery_pack_energy"
                )
                return self._task_battery_pack_energy(variables)

        var_assignments = [f"{k} = {v}" for k, v in variables.items() if k != "query"]

        code = f"""# Generic Math Calculation
import json

{chr(10).join(var_assignments) if var_assignments else "# No numeric variables provided"}

# Calculate result
result = {{
    "inputs": {variables},
    "note": "Calculation executed with provided variables"
}}

print(json.dumps(result, indent=2))
"""
        return code

    async def fallback(self, parameters: dict[str, Any], error: Exception) -> ToolResult:
        """Fallback to executor's fallback."""
        return await self.executor.fallback(parameters, error)
