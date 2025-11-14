"""Tests for auto-code-generation."""

import pytest
from src.core.code_generator import CodeGenerator


@pytest.fixture
def generator():
    """Create code generator."""
    return CodeGenerator()


def test_detect_combination_problem(generator):
    """Test detection of combination problems."""
    queries = [
        "How many combinations of boxes can be carried?",
        "Calculate all combinations where sum <= 12",
        "Find the number of combinations",
        "Count all possible combinations",
    ]
    
    for query in queries:
        assert generator.can_auto_generate(query), f"Should detect: {query}"


def test_detect_arithmetic(generator):
    """Test detection of arithmetic problems."""
    queries = [
        "What's 1543 * 892?",
        "Calculate 15 + 27",
        "Compute 100 / 5",
    ]
    
    for query in queries:
        assert generator.can_auto_generate(query), f"Should detect: {query}"


def test_detect_factorial(generator):
    """Test detection of factorial problems."""
    queries = [
        "What is the factorial of 10?",
        "Calculate 5 factorial",
        "Find 12!",
    ]
    
    for query in queries:
        assert generator.can_auto_generate(query), f"Should detect: {query}"


def test_generate_combination_code(generator):
    """Test generation of combination code."""
    query = """Calculate how many combinations of boxes can be carried:
    Box weights: A=3.5kg, B=7.2kg, C=4.8kg, D=2.3kg, E=6.1kg
    Max capacity: 12kg"""
    
    code = generator.generate(query)
    
    assert code is not None
    assert "from itertools import combinations" in code
    assert "items = {" in code
    assert "'A': 3.5" in code
    assert "'B': 7.2" in code
    assert "max_value = 12" in code
    assert "<=" in code  # constraint operator


def test_generate_arithmetic_code(generator):
    """Test generation of arithmetic code."""
    query = "What's 1543 * 892?"
    
    code = generator.generate(query)
    
    assert code is not None
    assert "1543" in code
    assert "892" in code
    assert "*" in code


def test_generate_factorial_code(generator):
    """Test generation of factorial code."""
    query = "What is the factorial of 10?"
    
    code = generator.generate(query)
    
    assert code is not None
    assert "import math" in code
    assert "factorial" in code
    assert "10" in code


def test_extract_weighted_items(generator):
    """Test extraction of items with weights."""
    query = "Box weights: A=3.5kg, B=7.2kg, C=4.8kg"
    
    items = generator._extract_weighted_items(query)
    
    assert items is not None
    assert items["A"] == 3.5
    assert items["B"] == 7.2
    assert items["C"] == 4.8


def test_extract_constraint(generator):
    """Test extraction of constraints."""
    test_cases = [
        ("max capacity 12kg", 12.0, "<="),
        ("sum <= 100", 100.0, "<="),
        ("total < 50", 50.0, "<"),
        ("not exceeding 25", 25.0, "<="),
        ("at most 10", 10.0, "<="),
    ]
    
    for query, expected_value, expected_op in test_cases:
        constraint = generator._extract_constraint(query)
        assert constraint is not None, f"Should extract from: {query}"
        assert constraint["value"] == expected_value
        assert constraint["operator"] == expected_op


def test_no_generation_for_non_computational(generator):
    """Test that non-computational queries don't generate code."""
    queries = [
        "What is Python?",
        "Explain machine learning",
        "Tell me a joke",
    ]
    
    for query in queries:
        assert not generator.can_auto_generate(query), f"Should not detect: {query}"
        assert generator.generate(query) is None


def test_robot_box_problem(generator):
    """Test the actual robot box problem from the issue."""
    query = """Kai is training a robot to carry boxes.
    Each box has a weight:
    - Box A: 3.5 kilograms
    - Box B: 7.2 kilograms  
    - Box C: 4.8 kilograms
    - Box D: 2.3 kilograms
    - Box E: 6.1 kilograms
    
    The robot can carry a maximum of 12 kilograms at one time.
    
    Use Python to calculate: How many different combinations of boxes can the robot carry without exceeding the 12-kilogram limit?"""
    
    # Should detect it
    assert generator.can_auto_generate(query)
    
    # Should generate code
    code = generator.generate(query)
    assert code is not None
    assert "combinations" in code
    assert "3.5" in code
    assert "7.2" in code
    assert "12" in code
    
    # The generated code should work when executed
    # (We won't execute it in the test, but verify structure)
    assert "from itertools import combinations" in code
    assert "valid_combinations" in code
