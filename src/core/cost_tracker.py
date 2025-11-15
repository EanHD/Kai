"""Cost tracking and management for LLM API usage."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CostLimit:
    """Cost limit configuration."""

    total_limit: float  # Total cost limit in USD
    soft_cap_threshold: float = 0.8  # Percentage for soft cap warning
    manual_override: bool = False  # Allow exceeding limit for critical queries


@dataclass
class CostRecord:
    """Individual cost record for a query."""

    query_id: str
    session_id: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CostTracker:
    """Tracks and manages LLM API costs with soft caps and overrides."""

    def __init__(self, cost_limit: float, soft_cap_threshold: float = 0.8):
        """Initialize cost tracker.

        Args:
            cost_limit: Total cost limit in USD
            soft_cap_threshold: Percentage (0.0-1.0) to trigger soft cap warning
        """
        self.cost_limit = CostLimit(
            total_limit=cost_limit,
            soft_cap_threshold=soft_cap_threshold,
        )
        self.session_costs: dict[str, float] = {}  # session_id -> total cost
        self.query_records: list[CostRecord] = []
        self.total_cost: float = 0.0
        logger.info(f"CostTracker initialized with ${cost_limit:.2f} limit")

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_per_1k_input: float,
        cost_per_1k_output: float,
    ) -> float:
        """Calculate cost for a query.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost_per_1k_input: Cost per 1000 input tokens
            cost_per_1k_output: Cost per 1000 output tokens

        Returns:
            Total cost in USD
        """
        input_cost = (input_tokens / 1000.0) * cost_per_1k_input
        output_cost = (output_tokens / 1000.0) * cost_per_1k_output
        return input_cost + output_cost

    def track_query(
        self,
        query_id: str,
        session_id: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
    ) -> None:
        """Track cost for a query.

        Args:
            query_id: Query identifier
            session_id: Session identifier
            model_id: Model identifier
            input_tokens: Input token count
            output_tokens: Output token count
            cost: Total cost in USD
        """
        record = CostRecord(
            query_id=query_id,
            session_id=session_id,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )

        self.query_records.append(record)
        self.total_cost += cost

        # Update session total
        if session_id not in self.session_costs:
            self.session_costs[session_id] = 0.0
        self.session_costs[session_id] += cost

        logger.info(
            f"Tracked ${cost:.4f} for query {query_id} "
            f"({input_tokens} in, {output_tokens} out) - "
            f"Session total: ${self.session_costs[session_id]:.4f}"
        )

    def get_session_cost(self, session_id: str) -> float:
        """Get total cost for a session.

        Args:
            session_id: Session identifier

        Returns:
            Total cost in USD
        """
        return self.session_costs.get(session_id, 0.0)

    def get_total_cost(self) -> float:
        """Get total cost across all sessions.

        Returns:
            Total cost in USD
        """
        return self.total_cost

    def is_soft_cap_reached(self, session_id: str | None = None) -> bool:
        """Check if soft cap has been reached.

        Args:
            session_id: Session to check, or None for total across all sessions

        Returns:
            True if soft cap threshold reached
        """
        if session_id:
            cost = self.get_session_cost(session_id)
        else:
            cost = self.total_cost

        threshold = self.cost_limit.total_limit * self.cost_limit.soft_cap_threshold
        return cost >= threshold

    def is_hard_cap_reached(self, session_id: str | None = None) -> bool:
        """Check if hard cap has been reached.

        Args:
            session_id: Session to check, or None for total across all sessions

        Returns:
            True if hard limit exceeded
        """
        if session_id:
            cost = self.get_session_cost(session_id)
        else:
            cost = self.total_cost

        return cost >= self.cost_limit.total_limit

    def can_proceed(
        self,
        session_id: str,
        estimated_cost: float,
        is_critical: bool = False,
    ) -> tuple[bool, str]:
        """Check if a query can proceed based on cost limits.

        Args:
            session_id: Session identifier
            estimated_cost: Estimated cost of the query
            is_critical: Whether this is a critical query (allows override)

        Returns:
            Tuple of (can_proceed, reason)
        """
        current_cost = self.get_session_cost(session_id)
        projected_cost = current_cost + estimated_cost

        # Hard cap check
        if projected_cost >= self.cost_limit.total_limit:
            if is_critical and self.cost_limit.manual_override:
                logger.warning(
                    f"Manual override: allowing critical query despite hard cap "
                    f"(${projected_cost:.4f} > ${self.cost_limit.total_limit:.2f})"
                )
                return True, "manual_override"
            else:
                return False, "hard_cap_exceeded"

        # Soft cap check
        soft_threshold = self.cost_limit.total_limit * self.cost_limit.soft_cap_threshold
        if projected_cost >= soft_threshold:
            logger.warning(
                f"Soft cap warning: ${projected_cost:.4f} "
                f">= ${soft_threshold:.2f} (${self.cost_limit.total_limit:.2f} limit)"
            )
            return True, "soft_cap_warning"

        return True, "ok"

    def enable_manual_override(self, enabled: bool = True) -> None:
        """Enable or disable manual override for critical queries.

        Args:
            enabled: Whether to enable manual override
        """
        self.cost_limit.manual_override = enabled
        logger.info(f"Manual override {'enabled' if enabled else 'disabled'}")

    def get_remaining_budget(self, session_id: str | None = None) -> float:
        """Get remaining budget before hard cap.

        Args:
            session_id: Session to check, or None for total

        Returns:
            Remaining budget in USD
        """
        if session_id:
            cost = self.get_session_cost(session_id)
        else:
            cost = self.total_cost

        return max(0.0, self.cost_limit.total_limit - cost)

    def get_cost_summary(self, session_id: str | None = None) -> dict[str, Any]:
        """Get cost summary statistics.

        Args:
            session_id: Session to summarize, or None for all sessions

        Returns:
            Dict with cost statistics
        """
        if session_id:
            records = [r for r in self.query_records if r.session_id == session_id]
            total = self.get_session_cost(session_id)
        else:
            records = self.query_records
            total = self.total_cost

        return {
            "total_cost": total,
            "query_count": len(records),
            "limit": self.cost_limit.total_limit,
            "remaining": self.get_remaining_budget(session_id),
            "soft_cap_reached": self.is_soft_cap_reached(session_id),
            "hard_cap_reached": self.is_hard_cap_reached(session_id),
            "manual_override_enabled": self.cost_limit.manual_override,
        }
