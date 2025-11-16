"""Pytest configuration and fixtures for test suite.

Provides:
- Session-level cost tracking and reporting
- Shared fixtures for common test setup
"""

import logging

import pytest

logger = logging.getLogger(__name__)

# Global cost accumulator for test session
_session_costs = {
    "total": 0.0,
    "by_test": {},
    "by_model": {},
    "call_counts": {},  # Track number of calls per model
}


def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line("markers", "production: marks tests as production tests")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """Called before test session starts."""
    global _session_costs
    _session_costs = {
        "total": 0.0,
        "by_test": {},
        "by_model": {},
        "call_counts": {},
    }
    logger.info("💰 Cost tracking initialized for test session")


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """Called after test session finishes - report aggregated costs."""
    global _session_costs

    if _session_costs["total"] > 0:
        print("\n" + "=" * 80)
        print("💰 TEST SESSION COST SUMMARY")
        print("=" * 80)
        print(f"\n📊 Total External API Cost: ${_session_costs['total']:.4f} USD")

        if _session_costs["by_model"]:
            print("\n📈 Cost by Model (with call counts):")
            # Sort by cost descending
            sorted_models = sorted(
                _session_costs["by_model"].items(), key=lambda x: x[1], reverse=True
            )
            for model, cost in sorted_models:
                calls = _session_costs["call_counts"].get(model, 0)
                avg_cost = cost / calls if calls > 0 else 0
                print(f"  • {model:<30} ${cost:>8.4f}  ({calls:>3} calls, ${avg_cost:.4f}/call)")

        if _session_costs["by_test"]:
            print("\n🧪 Top 10 Most Expensive Tests:")
            top_tests = sorted(_session_costs["by_test"].items(), key=lambda x: x[1], reverse=True)[
                :10
            ]
            for i, (test_name, cost) in enumerate(top_tests, 1):
                # Shorten test name for readability
                short_name = test_name.split("::")[-1] if "::" in test_name else test_name
                print(f"  {i:>2}. {short_name:<50} ${cost:.4f}")

        # Cost warning thresholds
        if _session_costs["total"] > 1.0:
            print(
                f"\n⚠️  WARNING: Session cost ${_session_costs['total']:.4f} exceeds $1.00 threshold"
            )
        elif _session_costs["total"] > 0.5:
            print(f"\n⚡ Note: Session cost ${_session_costs['total']:.4f} is approaching $0.50")

        print("=" * 80 + "\n")
    else:
        print("\n💰 No external API costs incurred during test session ✓\n")


def track_test_cost(test_name: str, model: str, cost: float):
    """Track cost for a specific test.

    Args:
        test_name: Name of the test
        model: Model name that incurred the cost
        cost: Cost in USD
    """
    global _session_costs

    _session_costs["total"] += cost
    _session_costs["by_test"][test_name] = _session_costs["by_test"].get(test_name, 0.0) + cost
    _session_costs["by_model"][model] = _session_costs["by_model"].get(model, 0.0) + cost
    _session_costs["call_counts"][model] = _session_costs["call_counts"].get(model, 0) + 1


# Export cost tracking function for use in tests
pytest.track_test_cost = track_test_cost
