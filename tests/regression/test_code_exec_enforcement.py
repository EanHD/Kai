"""Regression tests for code_exec enforcement in plans.

Verifies that math queries always get code_exec steps, either in the
original plan or injected during validation.
"""

from src.core.plan_analyzer import PlanAnalyzer
from src.core.plan_executor import PlanExecutor
from src.core.plan_types import ComplexityLevel, Plan, PlanStep, SafetyLevel, StepType
from src.core.sanity_checker import SanityChecker
from src.core.specialists.verification import SpecialistVerifier


class TestCodeExecEnforcement:
    """Test code_exec enforcement for math queries."""

    def test_plan_validation_injects_code_exec_for_battery_query(self):
        """Plan validation should inject code_exec for battery calculations."""
        # Create a plan with NO code_exec step for a math query
        query = "What's the energy of a 14S5P pack with 3500mAh cells?"
        plan = Plan(
            plan_id="test",
            user_query=query,
            source="cli",
            intent="battery_energy",
            complexity=ComplexityLevel.MODERATE,
            safety_level=SafetyLevel.NORMAL,
            capabilities=["code_exec"],  # Says it needs code_exec
            steps=[
                # But no code_exec step provided!
                PlanStep(
                    id="finalize",
                    type=StepType.FINALIZATION,
                    description="Present result",
                    input={},
                    depends_on=[],
                    required=True,
                ),
            ],
        )

        # Create executor
        executor = PlanExecutor(
            tools={},
            sanity_checker=SanityChecker(),
            specialist_verifier=SpecialistVerifier(None, None),
        )

        # Validate plan - should inject code_exec step
        error = executor._validate_plan(plan)

        # Should not return error - should inject step instead
        assert error is None

        # Should now have code_exec step
        code_exec_steps = [s for s in plan.steps if s.tool == "code_exec"]
        assert len(code_exec_steps) == 1

        # Should use battery_pack_energy task
        step = code_exec_steps[0]
        assert step.input["mode"] == "task"
        assert step.input["task"] == "battery_pack_energy"
        # Verify correct variable name
        assert "query" in step.input["variables"]
        assert step.input["variables"]["query"] == query

    def test_plan_validation_injects_generic_math_for_non_battery(self):
        """Plan validation should inject generic_math for non-battery calculations."""
        # Create a plan with NO code_exec step for a math query
        query = "Calculate 25% of 400"
        plan = Plan(
            plan_id="test",
            user_query=query,
            source="cli",
            intent="percentage",
            complexity=ComplexityLevel.SIMPLE,
            safety_level=SafetyLevel.NORMAL,
            capabilities=["code_exec"],
            steps=[
                PlanStep(
                    id="finalize",
                    type=StepType.FINALIZATION,
                    description="Present result",
                    input={},
                    depends_on=[],
                    required=True,
                ),
            ],
        )

        # Create executor
        executor = PlanExecutor(
            tools={},
            sanity_checker=SanityChecker(),
            specialist_verifier=SpecialistVerifier(None, None),
        )

        # Validate plan - should inject code_exec step
        error = executor._validate_plan(plan)

        assert error is None

        # Should have code_exec step
        code_exec_steps = [s for s in plan.steps if s.tool == "code_exec"]
        assert len(code_exec_steps) == 1

        # Should use generic_math task
        step = code_exec_steps[0]
        assert step.input["mode"] == "task"
        assert step.input["task"] == "generic_math"

    def test_plan_validation_accepts_existing_code_exec(self):
        """Plan validation should not inject if code_exec already present."""
        query = "What's 2+2?"
        plan = Plan(
            plan_id="test",
            user_query=query,
            source="cli",
            intent="math",
            complexity=ComplexityLevel.SIMPLE,
            safety_level=SafetyLevel.NORMAL,
            capabilities=["code_exec"],
            steps=[
                PlanStep(
                    id="calc",
                    type=StepType.TOOL_CALL,
                    tool="code_exec",
                    input={
                        "language": "python",
                        "mode": "task",
                        "task": "generic_math",
                        "variables": {"query": query},
                    },
                    depends_on=[],
                    required=True,
                ),
                PlanStep(
                    id="finalize",
                    type=StepType.FINALIZATION,
                    description="Present result",
                    input={},
                    depends_on=["calc"],
                    required=True,
                ),
            ],
        )

        executor = PlanExecutor(
            tools={},
            sanity_checker=SanityChecker(),
            specialist_verifier=SpecialistVerifier(None, None),
        )

        # Validate plan
        error = executor._validate_plan(plan)
        assert error is None

        # Should still have exactly 1 code_exec step (not injected duplicate)
        code_exec_steps = [s for s in plan.steps if s.tool == "code_exec"]
        assert len(code_exec_steps) == 1
        assert code_exec_steps[0].id == "calc"

    def test_injected_step_placed_before_finalization(self):
        """Injected code_exec should be inserted before finalization step."""
        query = "What's the total energy?"
        plan = Plan(
            plan_id="test",
            user_query=query,
            source="cli",
            intent="energy",
            complexity=ComplexityLevel.SIMPLE,
            safety_level=SafetyLevel.NORMAL,
            capabilities=[],
            steps=[
                PlanStep(
                    id="finalize",
                    type=StepType.FINALIZATION,
                    description="Present",
                    input={},
                    depends_on=[],
                    required=True,
                ),
            ],
        )

        executor = PlanExecutor(
            tools={},
            sanity_checker=SanityChecker(),
            specialist_verifier=SpecialistVerifier(None, None),
        )

        executor._validate_plan(plan)

        # Finalization should be last
        assert plan.steps[-1].type == StepType.FINALIZATION

        # Code exec should be before finalization
        code_exec_idx = next(i for i, s in enumerate(plan.steps) if s.tool == "code_exec")
        finalize_idx = next(i for i, s in enumerate(plan.steps) if s.type == StepType.FINALIZATION)
        assert code_exec_idx < finalize_idx


class TestFallbackPlanBatteryDetection:
    """Test fallback plan battery pattern detection."""

    def test_fallback_plan_detects_battery_pattern_uppercase(self):
        """Fallback plan should detect battery pattern 14S5P."""
        query = "14S5P battery pack energy"

        analyzer = PlanAnalyzer(local_connector=None, embeddings_provider=None)
        plan = analyzer._create_fallback_plan(query, source="cli")

        # Should have code_exec step
        code_exec_steps = [s for s in plan.steps if s.tool == "code_exec"]
        assert len(code_exec_steps) == 1

        # Should use battery_pack_energy task
        step = code_exec_steps[0]
        assert step.input["task"] == "battery_pack_energy"

    def test_fallback_plan_detects_battery_pattern_lowercase(self):
        """Fallback plan should detect battery pattern 13s4p."""
        query = "what's the capacity of a 13s4p pack?"

        analyzer = PlanAnalyzer(local_connector=None, embeddings_provider=None)
        plan = analyzer._create_fallback_plan(query, source="cli")

        code_exec_steps = [s for s in plan.steps if s.tool == "code_exec"]
        assert len(code_exec_steps) == 1
        assert code_exec_steps[0].input["task"] == "battery_pack_energy"

    def test_fallback_plan_detects_battery_pattern_with_spaces(self):
        """Fallback plan should detect battery pattern with spaces (14S 5P)."""
        query = "14S 5P battery configuration"

        analyzer = PlanAnalyzer(local_connector=None, embeddings_provider=None)
        plan = analyzer._create_fallback_plan(query, source="cli")

        code_exec_steps = [s for s in plan.steps if s.tool == "code_exec"]
        assert len(code_exec_steps) == 1
        assert code_exec_steps[0].input["task"] == "battery_pack_energy"

    def test_fallback_plan_uses_generic_math_for_non_battery(self):
        """Fallback plan should use generic_math for non-battery calculations."""
        query = "calculate 50 + 30"

        analyzer = PlanAnalyzer(local_connector=None, embeddings_provider=None)
        plan = analyzer._create_fallback_plan(query, source="cli")

        code_exec_steps = [s for s in plan.steps if s.tool == "code_exec"]
        assert len(code_exec_steps) == 1
        assert code_exec_steps[0].input["task"] == "generic_math"


class TestBatteryNotationVariations:
    """Test recognition of various battery pack notation styles."""

    def test_14s5p_uppercase(self):
        """Test 14S5P uppercase notation."""
        query = "14S5P pack with 3500mAh cells"

        analyzer = PlanAnalyzer(local_connector=None, embeddings_provider=None)
        plan = analyzer._create_fallback_plan(query, source="cli")

        code_exec_steps = [s for s in plan.steps if s.tool == "code_exec"]
        assert len(code_exec_steps) == 1
        assert code_exec_steps[0].input["task"] == "battery_pack_energy"
        assert code_exec_steps[0].input["variables"]["query"] == query

    def test_14s5p_lowercase(self):
        """Test 14s5p lowercase notation."""
        query = "14s5p pack with 3500mAh cells"

        analyzer = PlanAnalyzer(local_connector=None, embeddings_provider=None)
        plan = analyzer._create_fallback_plan(query, source="cli")

        code_exec_steps = [s for s in plan.steps if s.tool == "code_exec"]
        assert len(code_exec_steps) == 1
        assert code_exec_steps[0].input["task"] == "battery_pack_energy"

    def test_14s_5p_with_spaces(self):
        """Test 14S 5P with spaces."""
        query = "14S 5P battery configuration"

        analyzer = PlanAnalyzer(local_connector=None, embeddings_provider=None)
        plan = analyzer._create_fallback_plan(query, source="cli")

        code_exec_steps = [s for s in plan.steps if s.tool == "code_exec"]
        assert len(code_exec_steps) == 1
        assert code_exec_steps[0].input["task"] == "battery_pack_energy"

    def test_14s5p_mixed_case(self):
        """Test 14s5P mixed case notation."""
        query = "energy of 14s5P pack"

        analyzer = PlanAnalyzer(local_connector=None, embeddings_provider=None)
        plan = analyzer._create_fallback_plan(query, source="cli")

        code_exec_steps = [s for s in plan.steps if s.tool == "code_exec"]
        assert len(code_exec_steps) == 1
        assert code_exec_steps[0].input["task"] == "battery_pack_energy"

    def test_14s5p_in_sentence(self):
        """Test 14S5P notation embedded in complex query."""
        query = "If I build a 14S5P pack with NCR18650B cells at 3500mAh, what's the total energy?"

        analyzer = PlanAnalyzer(local_connector=None, embeddings_provider=None)
        plan = analyzer._create_fallback_plan(query, source="cli")

        code_exec_steps = [s for s in plan.steps if s.tool == "code_exec"]
        assert len(code_exec_steps) == 1
        assert code_exec_steps[0].input["task"] == "battery_pack_energy"
