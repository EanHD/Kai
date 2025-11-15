"""Plan types and schemas for orchestration.

Defines the structured JSON formats for:
- Analyzer plans
- Tool execution
- Specialist verification
- Finalization
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class StepType(str, Enum):
    """Types of steps in a plan."""

    TOOL_CALL = "tool_call"
    SANITY_CHECK = "sanity_check"
    MODEL_CALL = "model_call"
    FINALIZATION = "finalization"


class ComplexityLevel(str, Enum):
    """Query complexity levels."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class SafetyLevel(str, Enum):
    """Safety requirement levels."""

    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceLevel(str, Enum):
    """Confidence levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TrustLevel(str, Enum):
    """Source trust levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Budget:
    """Cost and latency budget for a plan."""

    max_external_usd: float = 0.03
    latency_tier: Literal["fast", "balanced", "thorough"] = "balanced"


@dataclass
class PlanStep:
    """A single step in an execution plan."""

    id: str
    type: StepType
    tool: str | None = None
    model: str | None = None
    description: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    required: bool = True
    can_skip_if_unavailable: bool = False


@dataclass
class Plan:
    """Complete execution plan from analyzer."""

    plan_id: str
    version: str = "1.0"
    user_query: str = ""
    source: str = "api"  # "cli" or "api" - where the query originated
    intent: str = ""
    complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    priority: Literal["low", "normal", "high"] = "normal"
    safety_level: SafetyLevel = SafetyLevel.NORMAL
    budget: Budget = field(default_factory=Budget)
    capabilities: list[str] = field(default_factory=list)
    steps: list[PlanStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "plan_id": self.plan_id,
            "version": self.version,
            "user_query": self.user_query,
            "source": self.source,
            "intent": self.intent,
            "complexity": self.complexity.value,
            "priority": self.priority,
            "safety_level": self.safety_level.value,
            "budget": {
                "max_external_usd": self.budget.max_external_usd,
                "latency_tier": self.budget.latency_tier,
            },
            "capabilities": self.capabilities,
            "steps": [
                {
                    "id": step.id,
                    "type": step.type.value,
                    "tool": step.tool,
                    "model": step.model,
                    "description": step.description,
                    "input": step.input,
                    "depends_on": step.depends_on,
                    "required": step.required,
                    "can_skip_if_unavailable": step.can_skip_if_unavailable,
                }
                for step in self.steps
            ],
        }


@dataclass
class ToolResult:
    """Result from a tool execution."""

    step_id: str
    tool_name: str
    status: Literal["success", "failed", "skipped"]
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time_ms: int = 0


@dataclass
class Source:
    """A source citation."""

    label: str
    url: str = ""
    type: Literal["datasheet", "distributor", "third_party_test", "official", "other"] = "other"
    trust_level: TrustLevel = TrustLevel.MEDIUM


@dataclass
class VerifiedSpecs:
    """Verified specifications from specialist."""

    cell_type: str
    nominal_voltage_v: float
    nominal_capacity_ah: float
    allowed_capacity_range_ah: dict[str, float]
    sources: list[Source] = field(default_factory=list)


@dataclass
class PackCalculation:
    """Battery pack calculations."""

    series_cells: int
    parallel_cells: int
    pack_nominal_voltage_v: float
    pack_total_ah: float
    pack_total_wh: float
    pack_total_kwh: float


@dataclass
class RangeEstimate:
    """Vehicle range estimation."""

    usable_wh: float
    runtime_hours: float
    ideal_range_miles: float
    realistic_range_miles: float


@dataclass
class Issue:
    """An issue detected during processing."""

    field: str
    problem: str
    severity: Literal["info", "warning", "error"]


@dataclass
class Confidence:
    """Confidence levels for different aspects."""

    overall: ConfidenceLevel
    specs: ConfidenceLevel = ConfidenceLevel.MEDIUM
    math: ConfidenceLevel = ConfidenceLevel.MEDIUM
    range: ConfidenceLevel = ConfidenceLevel.MEDIUM


@dataclass
class VerificationResult:
    """Complete verification result from specialist."""

    verified_specs: VerifiedSpecs | None = None
    pack_calculation: PackCalculation | None = None
    range_estimate: RangeEstimate | None = None
    issues: list[Issue] = field(default_factory=list)
    confidence: Confidence = field(
        default_factory=lambda: Confidence(overall=ConfidenceLevel.MEDIUM)
    )
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "issues": [
                {"field": i.field, "problem": i.problem, "severity": i.severity}
                for i in self.issues
            ],
            "confidence": {
                "overall": self.confidence.overall.value,
                "specs": self.confidence.specs.value,
                "math": self.confidence.math.value,
                "range": self.confidence.range.value,
            },
        }

        if self.verified_specs:
            result["verified_specs"] = {
                "cell_type": self.verified_specs.cell_type,
                "nominal_voltage_v": self.verified_specs.nominal_voltage_v,
                "nominal_capacity_ah": self.verified_specs.nominal_capacity_ah,
                "allowed_capacity_range_ah": self.verified_specs.allowed_capacity_range_ah,
                "sources": [
                    {
                        "label": s.label,
                        "url": s.url,
                        "type": s.type,
                        "trust_level": s.trust_level.value,
                    }
                    for s in self.verified_specs.sources
                ],
            }

        if self.pack_calculation:
            result["pack_calculation"] = {
                "series_cells": self.pack_calculation.series_cells,
                "parallel_cells": self.pack_calculation.parallel_cells,
                "pack_nominal_voltage_v": self.pack_calculation.pack_nominal_voltage_v,
                "pack_total_ah": self.pack_calculation.pack_total_ah,
                "pack_total_wh": self.pack_calculation.pack_total_wh,
                "pack_total_kwh": self.pack_calculation.pack_total_kwh,
            }

        if self.range_estimate:
            result["range_estimate"] = {
                "usable_wh": self.range_estimate.usable_wh,
                "runtime_hours": self.range_estimate.runtime_hours,
                "ideal_range_miles": self.range_estimate.ideal_range_miles,
                "realistic_range_miles": self.range_estimate.realistic_range_miles,
            }

        if self.error:
            result["error"] = self.error

        return result


@dataclass
class FinalizationInput:
    """Input for the finalization step."""

    task: str = "finalize_answer"
    style_profile: str = "kai_default"
    original_query: str = ""
    plan: dict[str, Any] | None = None
    tool_results: dict[str, Any] = field(default_factory=dict)
    specialist_results: dict[str, Any] = field(default_factory=dict)
    citation_map: list[dict[str, str]] = field(default_factory=list)
    conversation_history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FinalizationOutput:
    """Output from finalization."""

    final_answer: str
    short_summary: str
    citations_used: list[int] = field(default_factory=list)
    debug_info: dict[str, Any] = field(default_factory=dict)
