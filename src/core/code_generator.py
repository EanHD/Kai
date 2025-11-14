"""Auto-code generator for computational queries.

Generates Python code automatically for mathematical and computational problems
that can be solved programmatically.
"""

import re
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class CodeGenerator:
    """Generates Python code for computational queries."""
    
    # Patterns for different types of computational problems
    COMBINATION_PATTERNS = [
        r"how many (?:combinations?|ways?|possibilities)",
        r"(?:count|find|calculate|compute) (?:all )?(?:the )?(?:possible )?combinations?",
        r"number of combinations?",
        r"different combinations?",
        r"(?:use python|python).{0,50}combinations?",
    ]
    
    PERMUTATION_PATTERNS = [
        r"how many (?:permutations?|arrangements?|orderings?)",
        r"(?:count|find|calculate) (?:all )?permutations?",
        r"number of permutations?",
    ]
    
    ARITHMETIC_PATTERNS = [
        r"what(?:'s| is) (\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)",
        r"calculate (\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)",
        r"compute (\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)",
    ]
    
    FACTORIAL_PATTERNS = [
        r"factorial of (\d+)",
        r"(\d+) factorial",
        r"(\d+)!",
    ]
    
    def can_auto_generate(self, query: str) -> bool:
        """Check if query can be auto-generated.
        
        Args:
            query: User query text
            
        Returns:
            True if code can be auto-generated
        """
        query_lower = query.lower()
        
        # Check for combination problems
        if any(re.search(pattern, query_lower) for pattern in self.COMBINATION_PATTERNS):
            return True
        
        # Check for permutation problems
        if any(re.search(pattern, query_lower) for pattern in self.PERMUTATION_PATTERNS):
            return True
        
        # Check for arithmetic
        if any(re.search(pattern, query_lower) for pattern in self.ARITHMETIC_PATTERNS):
            return True
        
        # Check for factorial
        if any(re.search(pattern, query_lower) for pattern in self.FACTORIAL_PATTERNS):
            return True
        
        return False
    
    def generate(self, query: str) -> Optional[str]:
        """Generate Python code for the query.
        
        Args:
            query: User query text
            
        Returns:
            Python code string or None if cannot generate
        """
        query_lower = query.lower()
        
        # Try combination problems
        code = self._generate_combination_code(query, query_lower)
        if code:
            return code
        
        # Try permutation problems
        code = self._generate_permutation_code(query, query_lower)
        if code:
            return code
        
        # Try arithmetic
        code = self._generate_arithmetic_code(query, query_lower)
        if code:
            return code
        
        # Try factorial
        code = self._generate_factorial_code(query, query_lower)
        if code:
            return code
        
        return None
    
    def _generate_combination_code(self, query: str, query_lower: str) -> Optional[str]:
        """Generate code for combination problems.
        
        Handles problems like:
        - "How many combinations of boxes can be carried?"
        - "Calculate all combinations where sum <= 12"
        """
        # Check if it's a combination problem
        if not any(re.search(pattern, query_lower) for pattern in self.COMBINATION_PATTERNS):
            return None
        
        # Extract items/values from query
        # Look for patterns like: A=3.5, B=7.2, etc.
        items = self._extract_weighted_items(query)
        
        if not items:
            logger.debug("Could not extract items for combination problem")
            return None
        
        # Extract constraint (sum <= X, sum < X, etc.)
        constraint = self._extract_constraint(query_lower)
        
        if not constraint:
            logger.debug("Could not extract constraint for combination problem")
            return None
        
        # Generate code
        code = f"""from itertools import combinations

# Items and their weights
items = {items}

# Constraint: {constraint['description']}
max_value = {constraint['value']}

# Find all valid combinations
valid_combinations = []
item_names = list(items.keys())

# Check all possible subset sizes
for size in range(1, len(item_names) + 1):
    for combo in combinations(item_names, size):
        total = sum(items[item] for item in combo)
        if total {constraint['operator']} max_value:
            valid_combinations.append((combo, total))

# Print results
print(f"Found {{len(valid_combinations)}} valid combinations:")
for combo, total in sorted(valid_combinations, key=lambda x: len(x[0])):
    items_str = ", ".join(combo)
    print(f"  {{items_str}} = {{total:.1f}}")

print(f"\\nTotal: {{len(valid_combinations)}} combinations")
"""
        return code
    
    def _generate_permutation_code(self, query: str, query_lower: str) -> Optional[str]:
        """Generate code for permutation problems."""
        if not any(re.search(pattern, query_lower) for pattern in self.PERMUTATION_PATTERNS):
            return None
        
        # Extract number of items
        match = re.search(r'(\d+) (?:items?|things?|elements?)', query_lower)
        if not match:
            return None
        
        n = int(match.group(1))
        
        # Check for "choose k" pattern
        k_match = re.search(r'choose (\d+)|select (\d+)|pick (\d+)', query_lower)
        k = int(k_match.group(1) or k_match.group(2) or k_match.group(3)) if k_match else n
        
        code = f"""from itertools import permutations
import math

# Calculate permutations
n = {n}
k = {k}

# Using formula: P(n,k) = n! / (n-k)!
result = math.factorial(n) // math.factorial(n - k)

print(f"Permutations P({{n}},{{k}}) = {{result}}")

# Show first few examples
items = list(range(1, n + 1))
perms = list(permutations(items, k))
print(f"\\nFirst 5 examples:")
for i, perm in enumerate(perms[:5], 1):
    print(f"  {{i}}. {{perm}}")

print(f"\\nTotal: {{len(perms)}} permutations")
"""
        return code
    
    def _generate_arithmetic_code(self, query: str, query_lower: str) -> Optional[str]:
        """Generate code for arithmetic problems."""
        for pattern in self.ARITHMETIC_PATTERNS:
            match = re.search(pattern, query_lower)
            if match:
                num1 = match.group(1)
                operator = match.group(2)
                num2 = match.group(3)
                
                code = f"""# Arithmetic calculation
a = {num1}
b = {num2}

result = a {operator} b
print(f"{{a}} {operator} {{b}} = {{result}}")
"""
                return code
        
        return None
    
    def _generate_factorial_code(self, query: str, query_lower: str) -> Optional[str]:
        """Generate code for factorial problems."""
        for pattern in self.FACTORIAL_PATTERNS:
            match = re.search(pattern, query_lower)
            if match:
                n = match.group(1)
                
                code = f"""import math

n = {n}
result = math.factorial(n)

print(f"{{n}}! = {{result:,}}")
"""
                return code
        
        return None
    
    def _extract_weighted_items(self, query: str) -> Optional[Dict[str, float]]:
        """Extract items with weights from query.
        
        Looks for patterns like:
        - A=3.5kg, B=7.2kg
        - A: 3.5, B: 7.2
        - A is 3.5kg, B is 7.2kg
        """
        items = {}
        
        # Pattern 1: A=3.5kg, B=7.2kg
        pattern1 = r'([A-Z])\s*[=:]\s*(\d+(?:\.\d+)?)\s*(?:kg|pounds?|lbs?)?'
        matches = re.finditer(pattern1, query, re.IGNORECASE)
        for match in matches:
            name = match.group(1).upper()
            value = float(match.group(2))
            items[name] = value
        
        if items:
            return items
        
        # Pattern 2: item A weighs 3.5
        pattern2 = r'([A-Z])\s+(?:weighs?|is)\s+(\d+(?:\.\d+)?)'
        matches = re.finditer(pattern2, query, re.IGNORECASE)
        for match in matches:
            name = match.group(1).upper()
            value = float(match.group(2))
            items[name] = value
        
        return items if items else None
    
    def _extract_constraint(self, query: str) -> Optional[Dict[str, Any]]:
        """Extract constraint from query.
        
        Looks for patterns like:
        - sum <= 12
        - total < 100
        - weight not exceeding 50
        """
        # Pattern 1: <= X, < X, etc.
        patterns = [
            (r'(?:sum|total|weight)\s*<=\s*(\d+(?:\.\d+)?)', '<='),
            (r'(?:sum|total|weight)\s*<\s*(\d+(?:\.\d+)?)', '<'),
            (r'(?:max|maximum|limit).*?(\d+(?:\.\d+)?)', '<='),
            (r'not exceed(?:ing)?\s+(\d+(?:\.\d+)?)', '<='),
            (r'under\s+(\d+(?:\.\d+)?)', '<'),
            (r'at most\s+(\d+(?:\.\d+)?)', '<='),
        ]
        
        for pattern, operator in patterns:
            match = re.search(pattern, query)
            if match:
                value = float(match.group(1))
                return {
                    'value': value,
                    'operator': operator,
                    'description': f'sum {operator} {value}'
                }
        
        return None
