"""Metrics collection for monitoring and observability."""

import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class QueryMetrics:
    """Metrics for a single query."""
    query_id: str
    session_id: str
    timestamp: datetime
    complexity: str
    response_time_ms: float
    token_count: int
    cost: float
    model_used: str
    tools_used: List[str]
    mode: str
    success: bool
    error: Optional[str] = None


class MetricsCollector:
    """Collects and aggregates system metrics."""

    def __init__(self, max_history: int = 10000):
        """Initialize metrics collector.
        
        Args:
            max_history: Maximum number of queries to keep in history
        """
        self.max_history = max_history
        self.query_history: deque[QueryMetrics] = deque(maxlen=max_history)
        
        # Aggregated metrics
        self.total_queries = 0
        self.total_cost = 0.0
        self.total_tokens = 0
        self.total_response_time_ms = 0.0
        
        # Counters by category
        self.queries_by_complexity: Dict[str, int] = defaultdict(int)
        self.queries_by_model: Dict[str, int] = defaultdict(int)
        self.queries_by_mode: Dict[str, int] = defaultdict(int)
        self.tool_usage_count: Dict[str, int] = defaultdict(int)
        self.error_count = 0

    def record_query(self, metrics: QueryMetrics):
        """Record metrics for a query.
        
        Args:
            metrics: QueryMetrics instance
        """
        self.query_history.append(metrics)
        
        # Update aggregates
        self.total_queries += 1
        self.total_cost += metrics.cost
        self.total_tokens += metrics.token_count
        self.total_response_time_ms += metrics.response_time_ms
        
        # Update counters
        self.queries_by_complexity[metrics.complexity] += 1
        self.queries_by_model[metrics.model_used] += 1
        self.queries_by_mode[metrics.mode] += 1
        
        for tool in metrics.tools_used:
            self.tool_usage_count[tool] += 1
        
        if not metrics.success:
            self.error_count += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics.
        
        Returns:
            Dict with aggregated metrics
        """
        if self.total_queries == 0:
            return {
                "total_queries": 0,
                "message": "No queries recorded yet",
            }
        
        avg_response_time = self.total_response_time_ms / self.total_queries
        avg_cost = self.total_cost / self.total_queries
        avg_tokens = self.total_tokens / self.total_queries
        error_rate = (self.error_count / self.total_queries) * 100
        
        return {
            "total_queries": self.total_queries,
            "total_cost": round(self.total_cost, 4),
            "total_tokens": self.total_tokens,
            "avg_response_time_ms": round(avg_response_time, 2),
            "avg_cost_per_query": round(avg_cost, 6),
            "avg_tokens_per_query": round(avg_tokens, 1),
            "error_rate_pct": round(error_rate, 2),
            "complexity_distribution": dict(self.queries_by_complexity),
            "model_usage": dict(self.queries_by_model),
            "mode_distribution": dict(self.queries_by_mode),
            "tool_usage": dict(self.tool_usage_count),
        }

    def get_recent_queries(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent query metrics.
        
        Args:
            count: Number of recent queries to return
            
        Returns:
            List of query metric dicts
        """
        recent = list(self.query_history)[-count:]
        
        return [
            {
                "query_id": m.query_id,
                "timestamp": m.timestamp.isoformat(),
                "complexity": m.complexity,
                "response_time_ms": round(m.response_time_ms, 2),
                "cost": round(m.cost, 6),
                "model": m.model_used,
                "tools": m.tools_used,
                "mode": m.mode,
                "success": m.success,
            }
            for m in recent
        ]

    def get_performance_percentiles(self) -> Dict[str, float]:
        """Calculate response time percentiles.
        
        Returns:
            Dict with p50, p90, p95, p99 response times
        """
        if not self.query_history:
            return {
                "p50": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }
        
        response_times = sorted(m.response_time_ms for m in self.query_history)
        n = len(response_times)
        
        def percentile(p: float) -> float:
            idx = int(n * p / 100)
            return response_times[min(idx, n - 1)]
        
        return {
            "p50": round(percentile(50), 2),
            "p90": round(percentile(90), 2),
            "p95": round(percentile(95), 2),
            "p99": round(percentile(99), 2),
        }

    def get_cost_breakdown(self) -> Dict[str, Any]:
        """Get cost breakdown by model.
        
        Returns:
            Dict with cost per model
        """
        cost_by_model: Dict[str, float] = defaultdict(float)
        
        for metrics in self.query_history:
            cost_by_model[metrics.model_used] += metrics.cost
        
        return {
            "total_cost": round(self.total_cost, 4),
            "by_model": {
                model: round(cost, 4)
                for model, cost in cost_by_model.items()
            },
        }

    def reset(self):
        """Reset all metrics."""
        self.query_history.clear()
        self.total_queries = 0
        self.total_cost = 0.0
        self.total_tokens = 0
        self.total_response_time_ms = 0.0
        self.queries_by_complexity.clear()
        self.queries_by_model.clear()
        self.queries_by_mode.clear()
        self.tool_usage_count.clear()
        self.error_count = 0
        
        logger.info("Metrics reset")
