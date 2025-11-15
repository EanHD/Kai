"""Capability specification loader for local models."""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class CapabilitySpec:
    """Represents a model's capability specification."""

    def __init__(self, model_id: str, spec_data: dict[str, Any]):
        """Initialize capability spec.

        Args:
            model_id: Model identifier
            spec_data: Specification dictionary from YAML
        """
        self.model_id = model_id
        self.display_name = spec_data.get("display_name", model_id)
        self.description = spec_data.get("description", "")

        # Capabilities
        self.capabilities = spec_data.get("capabilities", {})
        self.strengths = spec_data.get("strengths", [])
        self.weaknesses = spec_data.get("weaknesses", [])
        self.optimal_use_cases = spec_data.get("optimal_use_cases", [])

        # Routing guidance
        routing = spec_data.get("routing_guidance", {})
        self.optimal_complexity_range = routing.get("optimal_complexity_range", [0.0, 1.0])
        self.with_tools_range = routing.get("with_tools_range", [0.0, 1.0])
        self.confidence_multiplier = routing.get("confidence_multiplier_with_tools", 1.0)
        self.prefer_over_external = routing.get("prefer_over_external_when", {})

        # Benchmarks
        self.benchmarks = spec_data.get("benchmarks", {})
        self.avg_response_time_ms = self.benchmarks.get("average_response_time_ms", 0)

        # Model personality
        self.personality = spec_data.get("model_personality", {})

    def can_handle_complexity(self, complexity_score: float, has_tools: bool = False) -> bool:
        """Check if model can handle given complexity.

        Args:
            complexity_score: Query complexity (0.0-1.0)
            has_tools: Whether tools are available

        Returns:
            True if within capability range
        """
        if has_tools:
            min_c, max_c = self.with_tools_range
        else:
            min_c, max_c = self.optimal_complexity_range

        return min_c <= complexity_score <= max_c

    def should_prefer_over_external(
        self, complexity_score: float, has_web_search: bool = False, has_code_exec: bool = False
    ) -> bool:
        """Check if should prefer this local model over external models.

        Args:
            complexity_score: Query complexity
            has_web_search: Web search tool available
            has_code_exec: Code execution tool available

        Returns:
            True if should prefer local model
        """
        # prefer_over_external is a list of conditions (OR logic)
        if not self.prefer_over_external:
            return self.can_handle_complexity(complexity_score, has_web_search or has_code_exec)

        # Check each condition - if any match, prefer local
        for condition in self.prefer_over_external:
            if isinstance(condition, dict):
                # Check complexity_below
                if "complexity_below" in condition:
                    if complexity_score < condition["complexity_below"]:
                        return True

                # Check has_web_search
                if condition.get("has_web_search") and has_web_search:
                    return True

                # Check has_code_exec
                if condition.get("has_code_exec") and has_code_exec:
                    return True

                # Check user privacy preference (not implemented yet)
                if condition.get("user_prefers_privacy"):
                    # Would check user settings - for now assume False
                    pass

        # If no conditions matched, fall back to capability check
        return self.can_handle_complexity(complexity_score, has_web_search or has_code_exec)


class CapabilitySpecLoader:
    """Loads and manages model capability specifications."""

    def __init__(self, config_path: Path | None = None):
        """Initialize capability spec loader.

        Args:
            config_path: Path to capability_specs.yaml (default: config/capability_specs.yaml)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "capability_specs.yaml"

        self.config_path = Path(config_path)
        self.specs: dict[str, CapabilitySpec] = {}
        self._load_specs()

    def _load_specs(self):
        """Load capability specifications from YAML file."""
        if not self.config_path.exists():
            logger.warning(f"Capability specs not found at {self.config_path}")
            return

        try:
            with open(self.config_path) as f:
                data = yaml.safe_load(f)

            if not data or "models" not in data:
                logger.warning("No models found in capability specs")
                return

            for model_id, spec_data in data["models"].items():
                self.specs[model_id] = CapabilitySpec(model_id, spec_data)
                logger.debug(f"Loaded capability spec for {model_id}")

            logger.info(f"Loaded {len(self.specs)} capability specifications")

        except Exception as e:
            logger.error(f"Failed to load capability specs: {e}")

    def get_spec(self, model_id: str) -> CapabilitySpec | None:
        """Get capability spec for a model.

        Args:
            model_id: Model identifier

        Returns:
            CapabilitySpec or None if not found
        """
        return self.specs.get(model_id)

    def has_spec(self, model_id: str) -> bool:
        """Check if model has a capability spec.

        Args:
            model_id: Model identifier

        Returns:
            True if spec exists
        """
        return model_id in self.specs

    def list_models(self) -> list[str]:
        """List all models with capability specs.

        Returns:
            List of model IDs
        """
        return list(self.specs.keys())
