"""Sanity checker for detecting unrealistic values in responses.

Catches obvious hallucinations before they reach the user.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class SanityChecker:
    """Detects unrealistic or impossible values in model responses."""

    # Known physical limits for common items
    PHYSICAL_LIMITS = {
        # Battery cells
        "21700_cell_capacity_ah": (2.5, 6.0),  # Realistic range for 21700 cells
        "18650_cell_capacity_ah": (1.5, 3.6),  # Realistic range for 18650 cells
        "cell_voltage": (2.5, 4.5),  # Lithium cell voltage range
        # E-bike/scooter ranges
        "ebike_range_miles": (10, 100),  # Typical e-bike range
        "escooter_range_miles": (5, 60),  # Typical e-scooter range
        # Power consumption
        "motor_watts": (100, 10000),  # Consumer motors
        "battery_wh": (100, 10000),  # Consumer battery packs
    }

    def check_response(self, response_text: str, query_text: str) -> dict[str, Any]:
        """Check response for unrealistic values.

        Args:
            response_text: Model's response
            query_text: Original query

        Returns:
            Dict with suspicious=True/False and details
        """
        issues = []

        # Check battery cell capacities
        cell_issues = self._check_battery_cells(response_text, query_text)
        if cell_issues:
            issues.extend(cell_issues)

        # Check range calculations
        range_issues = self._check_range_values(response_text, query_text)
        if range_issues:
            issues.extend(range_issues)

        # Check energy calculations
        energy_issues = self._check_energy_values(response_text)
        if energy_issues:
            issues.extend(energy_issues)

        # Determine severity based on number and type of issues
        severity = "none"
        if len(issues) > 0:
            # Cell capacity hallucinations are always high severity
            if any("cell" in issue.lower() and "unrealistic" in issue.lower() for issue in issues):
                severity = "high"
            # Range issues are high severity
            elif any(
                "range" in issue.lower() and "unrealistic" in issue.lower() for issue in issues
            ):
                severity = "high"
            # Multiple issues = high severity
            elif len(issues) > 1:
                severity = "high"
            else:
                severity = "medium"

        return {
            "suspicious": len(issues) > 0,
            "issues": issues,
            "severity": severity,
        }

    def _check_battery_cells(self, response: str, query: str) -> list[str]:
        """Check for unrealistic battery cell specifications."""
        issues = []

        # Detect 21700 cell mentions
        if "21700" in query.lower() or "21700" in response.lower():
            # Look for capacity claims
            capacity_pattern = r"(\d+(?:\.\d+)?)\s*ah"
            matches = re.finditer(capacity_pattern, response.lower())

            for match in matches:
                capacity = float(match.group(1))
                min_cap, max_cap = self.PHYSICAL_LIMITS["21700_cell_capacity_ah"]

                if capacity > max_cap:
                    issues.append(
                        f"Unrealistic 21700 cell capacity: {capacity}Ah "
                        f"(realistic range: {min_cap}-{max_cap}Ah). "
                        f"Highest production cells are ~5.5Ah."
                    )
                    logger.warning(f"Sanity check FAILED: 21700 cell claimed {capacity}Ah")
                elif capacity < min_cap:
                    issues.append(
                        f"Suspiciously low 21700 cell capacity: {capacity}Ah "
                        f"(typical range: {min_cap}-{max_cap}Ah)"
                    )

        # Detect 18650 cell mentions
        if "18650" in query.lower() or "18650" in response.lower():
            capacity_pattern = r"(\d+(?:\.\d+)?)\s*ah"
            matches = re.finditer(capacity_pattern, response.lower())

            for match in matches:
                capacity = float(match.group(1))
                min_cap, max_cap = self.PHYSICAL_LIMITS["18650_cell_capacity_ah"]

                if capacity > max_cap:
                    issues.append(
                        f"Unrealistic 18650 cell capacity: {capacity}Ah "
                        f"(realistic range: {min_cap}-{max_cap}Ah)"
                    )
                    logger.warning(f"Sanity check FAILED: 18650 cell claimed {capacity}Ah")

        return issues

    def _check_range_values(self, response: str, query: str) -> list[str]:
        """Check for unrealistic range claims."""
        issues = []

        # Look for e-bike/scooter context
        is_ebike = any(word in query.lower() for word in ["e-bike", "ebike", "electric bike"])
        is_scooter = any(word in query.lower() for word in ["scooter", "e-scooter", "escooter"])

        if is_ebike or is_scooter:
            # Look for range claims in miles
            range_pattern = r"(\d+(?:\.\d+)?)\s*(?:miles?|mi\b)"
            matches = re.finditer(range_pattern, response.lower())

            for match in matches:
                range_val = float(match.group(1))

                if is_ebike:
                    min_range, max_range = self.PHYSICAL_LIMITS["ebike_range_miles"]
                    vehicle_type = "e-bike"
                else:
                    min_range, max_range = self.PHYSICAL_LIMITS["escooter_range_miles"]
                    vehicle_type = "e-scooter"

                if range_val > max_range:
                    issues.append(
                        f"Unrealistic {vehicle_type} range: {range_val} miles "
                        f"(typical range: {min_range}-{max_range} miles). "
                        f"Double-check battery capacity and motor power."
                    )
                    logger.warning(f"Sanity check FAILED: {vehicle_type} range {range_val} miles")

        return issues

    def _check_energy_values(self, response: str) -> list[str]:
        """Check for unrealistic energy calculations."""
        issues = []

        # Look for Wh claims that seem wrong
        wh_pattern = r"(\d+(?:,\d+)?(?:\.\d+)?)\s*wh"
        matches = re.finditer(wh_pattern, response.lower())

        for match in matches:
            wh_str = match.group(1).replace(",", "")
            wh_val = float(wh_str)

            min_wh, max_wh = self.PHYSICAL_LIMITS["battery_wh"]

            # Super high values are suspicious for consumer products
            if wh_val > max_wh:
                issues.append(
                    f"Unusually high battery capacity: {wh_val}Wh. "
                    f"Verify the calculation (typical consumer range: {min_wh}-{max_wh}Wh)"
                )

        return issues

    def should_escalate(self, check_result: dict[str, Any]) -> bool:
        """Determine if issues are severe enough to escalate to better model.

        Args:
            check_result: Result from check_response()

        Returns:
            True if should re-route to more capable model
        """
        return check_result["suspicious"] and check_result["severity"] == "high"
