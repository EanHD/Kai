#!/usr/bin/env python3
"""Master test runner for Kai - runs all test categories and produces summary.

Usage:
    python scripts/run_all_tests.py [--fast] [--category CATEGORY]

Options:
    --fast: Skip production tests (faster, no API costs)
    --category: Run only specific category (unit, integration, production, regression, static)

Categories:
    - unit: Fast isolated component tests
    - integration: Multi-component workflow tests
    - production: Real API calls with battery calculations ($$)
    - regression: Bug fix validation tests
    - static: Linting, formatting, type checks
"""

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestResult:
    """Result from a test category run."""

    category: str
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    failed_tests: list[str]


def run_pytest_category(category: str, path: str) -> TestResult:
    """Run pytest for a specific category and parse results.

    Args:
        category: Name of the test category
        path: Path to test directory or file pattern

    Returns:
        TestResult with parsed counts and failures
    """
    print(f"\n{'=' * 80}")
    print(f"Running {category.upper()} tests...")
    print(f"{'=' * 80}")

    start_time = time.time()

    cmd = [
        "python",
        "-m",
        "pytest",
        path,
        "-v",
        "--tb=short",
        "-ra",  # Show summary of all test outcomes
    ]

    result = subprocess.run(
        cmd,
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    duration = time.time() - start_time

    # Print output
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Parse summary line like "5 passed, 2 failed, 1 skipped in 10.23s"
    passed = failed = skipped = errors = 0
    failed_tests = []

    for line in result.stdout.split("\n"):
        # Parse summary
        if " passed" in line or " failed" in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "passed" and i > 0:
                    passed = int(parts[i - 1])
                elif part == "failed" and i > 0:
                    failed = int(parts[i - 1])
                elif part == "skipped" and i > 0:
                    skipped = int(parts[i - 1])
                elif part == "error" and i > 0:
                    errors = int(parts[i - 1])

        # Parse failed test names
        if "FAILED " in line:
            # Extract test name from lines like "FAILED tests/unit/test_foo.py::test_bar"
            parts = line.split("FAILED ")
            if len(parts) > 1:
                test_name = parts[1].split(" - ")[0].strip()
                failed_tests.append(test_name)

    return TestResult(
        category=category,
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=errors,
        duration=duration,
        failed_tests=failed_tests,
    )


def print_summary(results: list[TestResult]):
    """Print formatted summary of all test results."""
    print("\n" + "=" * 80)
    print("TEST SUITE SUMMARY")
    print("=" * 80)

    total_passed = sum(r.passed for r in results)
    total_failed = sum(r.failed for r in results)
    total_skipped = sum(r.skipped for r in results)
    total_errors = sum(r.errors for r in results)
    total_duration = sum(r.duration for r in results)

    # Category breakdown
    print("\nBy Category:")
    print(f"{'Category':<15} {'Passed':<8} {'Failed':<8} {'Skipped':<8} {'Time':<10}")
    print("-" * 60)

    for result in results:
        status = "✓" if result.failed == 0 and result.errors == 0 else "✗"
        print(
            f"{status} {result.category:<13} "
            f"{result.passed:<8} {result.failed:<8} {result.skipped:<8} "
            f"{result.duration:.2f}s"
        )

    print("-" * 60)
    print(
        f"{'TOTAL':<15} {total_passed:<8} {total_failed:<8} {total_skipped:<8} "
        f"{total_duration:.2f}s"
    )

    # Failed tests
    if total_failed > 0 or total_errors > 0:
        print(f"\n❌ FAILED TESTS ({total_failed + total_errors}):")
        for result in results:
            if result.failed_tests:
                print(f"\n{result.category}:")
                for test in result.failed_tests:
                    print(f"  - {test}")

    # Overall status
    print("\n" + "=" * 80)
    if total_failed == 0 and total_errors == 0:
        print("✅ ALL TESTS PASSED")
    else:
        print(f"❌ {total_failed + total_errors} TEST(S) FAILED")
    print("=" * 80)

    return total_failed + total_errors


def main():
    """Run all test categories and report results."""
    import argparse

    parser = argparse.ArgumentParser(description="Run Kai test suite")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip production tests (no API costs)",
    )
    parser.add_argument(
        "--category",
        choices=["unit", "integration", "production", "regression", "static"],
        help="Run only specific category",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("KAI TEST SUITE")
    print("=" * 80)
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Define test categories
    categories = []

    if args.category:
        # Run only specified category
        if args.category == "unit":
            categories = [("unit", "tests/unit/")]
        elif args.category == "integration":
            categories = [("integration", "tests/integration/")]
        elif args.category == "production":
            categories = [("production", "tests/production/")]
        elif args.category == "regression":
            categories = [("regression", "tests/regression/")]
        elif args.category == "static":
            categories = [("static", "tests/static/")]
    else:
        # Run all categories
        categories = [
            ("static", "tests/static/"),
            ("unit", "tests/unit/"),
            ("regression", "tests/regression/"),
            ("integration", "tests/integration/"),
        ]

        if not args.fast:
            categories.append(("production", "tests/production/"))
        else:
            print("\n⚡ FAST MODE: Skipping production tests (use --no-fast to include)")

    # Run each category
    results = []
    for category, path in categories:
        result = run_pytest_category(category, path)
        results.append(result)

    # Print summary
    exit_code = print_summary(results)

    print(f"\nEnd time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Note about cost summary
    if not args.fast:
        print("\n💰 Cost summary should appear above (if any production tests ran)")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
