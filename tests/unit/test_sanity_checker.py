"""Tests for sanity checker."""

import pytest
from src.core.sanity_checker import SanityChecker


@pytest.fixture
def checker():
    """Create sanity checker."""
    return SanityChecker()


def test_detect_unrealistic_21700_capacity(checker):
    """Test detection of unrealistic 21700 cell capacity."""
    query = "What's the capacity of Samsung 50E 21700 cells?"
    response = "The Samsung 50E has a capacity of 25Ah."
    
    result = checker.check_response(response, query)
    
    assert result["suspicious"] is True
    assert len(result["issues"]) > 0
    assert "25" in result["issues"][0]
    assert "21700" in result["issues"][0].lower()


def test_accept_realistic_21700_capacity(checker):
    """Test that realistic values pass."""
    query = "What's the capacity of Samsung 50E 21700 cells?"
    response = "The Samsung 50E has a capacity of 5.0Ah."
    
    result = checker.check_response(response, query)
    
    assert result["suspicious"] is False
    assert len(result["issues"]) == 0


def test_detect_unrealistic_ebike_range(checker):
    """Test detection of unrealistic e-bike range."""
    query = "What's the range of my e-bike with 500Wh battery?"
    response = "With a 500Wh battery, you can expect around 150 miles of range."
    
    result = checker.check_response(response, query)
    
    assert result["suspicious"] is True
    assert any("150" in issue for issue in result["issues"])


def test_accept_realistic_ebike_range(checker):
    """Test that realistic range passes."""
    query = "What's the range of my e-bike with 500Wh battery?"
    response = "With a 500Wh battery, you can expect around 30-40 miles of range."
    
    result = checker.check_response(response, query)
    
    assert result["suspicious"] is False


def test_detect_unrealistic_18650_capacity(checker):
    """Test detection of unrealistic 18650 cell capacity."""
    query = "What's the best 18650 cell capacity?"
    response = "The best 18650 cells can achieve 5.0Ah."
    
    result = checker.check_response(response, query)
    
    assert result["suspicious"] is True
    assert "18650" in result["issues"][0].lower()


def test_escalation_decision(checker):
    """Test that high-severity issues trigger escalation."""
    query = "Samsung 50E 21700 specs?"
    response = "Samsung 50E has 25Ah capacity."
    
    result = checker.check_response(response, query)
    should_escalate = checker.should_escalate(result)
    
    assert should_escalate is True


def test_no_escalation_for_clean_response(checker):
    """Test that clean responses don't trigger escalation."""
    query = "Samsung 50E 21700 specs?"
    response = "Samsung 50E has 5.0Ah capacity."
    
    result = checker.check_response(response, query)
    should_escalate = checker.should_escalate(result)
    
    assert should_escalate is False


def test_multiple_issues_detected(checker):
    """Test that multiple issues can be detected."""
    query = "E-bike with 21700 cells, what's the range?"
    response = "With 10Ah 21700 cells and 500W motor, you'll get 80 miles range."
    
    result = checker.check_response(response, query)
    
    # Should detect both unrealistic cell capacity and possibly range
    assert result["suspicious"] is True
    assert len(result["issues"]) >= 1  # At least the cell capacity


def test_energy_sanity_check(checker):
    """Test sanity check for energy values."""
    query = "How much energy in the battery?"
    response = "The battery pack has 25,000 Wh of capacity."
    
    result = checker.check_response(response, query)
    
    # 25kWh is huge for consumer products
    assert result["suspicious"] is True


def test_samsung_50e_real_world_query(checker):
    """Test the actual Samsung 50E query from the issue."""
    query = """I saw conflicting specs for Samsung 50E 21700 cells online.
    Can you check at least two reliable sources and tell me the real capacity?
    Watch for fake spec sheets."""
    
    # Bad response (hallucinated)
    bad_response = "The Samsung 50E has a capacity of 25Ah and 3.7V nominal."
    
    result = checker.check_response(bad_response, query)
    
    assert result["suspicious"] is True
    assert checker.should_escalate(result) is True
    
    # Good response (realistic)
    good_response = "The Samsung 50E has a capacity of 5.0Ah and 3.6V nominal."
    
    result2 = checker.check_response(good_response, query)
    
    assert result2["suspicious"] is False
