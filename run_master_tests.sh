#!/usr/bin/env bash
#
# Master Test Suite Runner for Kai Production Validation
#
# This script runs the complete test suite in the correct order:
# 1. Static analysis (lint, format, imports, types)
# 2. Unit tests (fast, isolated)
# 3. Integration tests (real components)
# 4. Production validation (full pipeline)
# 5. Regression tests (bug prevention)
# 6. Stress tests (load capacity)
#
# Usage:
#   ./run_master_tests.sh [OPTIONS]
#
# Options:
#   --quick          Run only static + unit + integration (skip production/stress)
#   --production     Run only production validation suite
#   --regression     Run only regression tests
#   --stress         Run only stress tests
#   --no-static      Skip static analysis
#   --cost-report    Show detailed cost breakdown at end
#   --fail-fast      Stop on first test failure
#
# Environment:
#   OPENROUTER_API_KEY   Required for production/integration tests
#   BRAVE_API_KEY        Optional for web search tests
#
# Output:
#   - Test results to stdout
#   - Cost summary at end
#   - Exit code 0 if all tests pass, 1 if any fail
#

set -e  # Exit on error unless explicitly handled

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0
TOTAL_COST=0.0

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

RUN_STATIC=1
RUN_UNIT=1
RUN_INTEGRATION=1
RUN_PRODUCTION=1
RUN_REGRESSION=1
RUN_STRESS=1
FAIL_FAST=""
COST_REPORT=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            RUN_PRODUCTION=0
            RUN_STRESS=0
            shift
            ;;
        --production)
            RUN_STATIC=0
            RUN_UNIT=0
            RUN_INTEGRATION=0
            RUN_REGRESSION=0
            RUN_STRESS=0
            RUN_PRODUCTION=1
            shift
            ;;
        --regression)
            RUN_STATIC=0
            RUN_UNIT=0
            RUN_INTEGRATION=0
            RUN_PRODUCTION=0
            RUN_STRESS=0
            RUN_REGRESSION=1
            shift
            ;;
        --stress)
            RUN_STATIC=0
            RUN_UNIT=0
            RUN_INTEGRATION=0
            RUN_PRODUCTION=0
            RUN_REGRESSION=0
            RUN_STRESS=1
            shift
            ;;
        --no-static)
            RUN_STATIC=0
            shift
            ;;
        --cost-report)
            COST_REPORT=1
            shift
            ;;
        --fail-fast)
            FAIL_FAST="-x"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with --help for usage"
            exit 1
            ;;
    esac
done

# Banner
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                 KAI MASTER TEST SUITE RUNNER                           ║${NC}"
echo -e "${BLUE}║                Production Validation - v1.0                            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Load environment from .env file if it exists
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    echo -e "${BLUE}Loading environment from .env...${NC}"
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Check environment
echo -e "${YELLOW}[ENVIRONMENT CHECK]${NC}"

if [[ -z "$OPENROUTER_API_KEY" ]] && [[ $RUN_PRODUCTION -eq 1 || $RUN_INTEGRATION -eq 1 ]]; then
    echo -e "${RED}✗ OPENROUTER_API_KEY not set${NC}"
    echo "  Production and integration tests require OpenRouter API access"
    echo "  Set in .env file or with: export OPENROUTER_API_KEY='your-key-here'"
    exit 1
else
    echo -e "${GREEN}✓ OPENROUTER_API_KEY configured${NC}"
fi

if [[ -z "$BRAVE_API_KEY" ]]; then
    echo -e "${YELLOW}⚠ BRAVE_API_KEY not set (web search tests will be skipped)${NC}"
else
    echo -e "${GREEN}✓ BRAVE_API_KEY configured${NC}"
fi

# Check Ollama
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${RED}✗ Ollama not running at localhost:11434${NC}"
    echo "  Start with: ollama serve"
    exit 1
else
    echo -e "${GREEN}✓ Ollama running${NC}"
    
    # Check for granite model
    if curl -s http://localhost:11434/api/tags | grep -q "granite4:micro-h"; then
        echo -e "${GREEN}✓ granite4:micro-h model available${NC}"
    else
        echo -e "${RED}✗ granite4:micro-h model not found${NC}"
        echo "  Pull with: ollama pull granite4:micro-h"
        exit 1
    fi
fi

echo ""

# Function to run test suite
run_test_suite() {
    local name=$1
    local path=$2
    local marker=$3
    
    echo -e "${BLUE}╭────────────────────────────────────────────────────────────────────────╮${NC}"
    echo -e "${BLUE}│ $name${NC}"
    echo -e "${BLUE}╰────────────────────────────────────────────────────────────────────────╯${NC}"
    
    local pytest_args="-v --tb=short"
    if [[ -n "$marker" ]]; then
        pytest_args="$pytest_args -m $marker"
    fi
    if [[ -n "$FAIL_FAST" ]]; then
        pytest_args="$pytest_args $FAIL_FAST"
    fi
    
    # Run tests and capture output
    if pytest $pytest_args "$path" 2>&1; then
        echo -e "${GREEN}✓ $name PASSED${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ $name FAILED${NC}"
        echo ""
        return 1
    fi
}

# Track overall success
OVERALL_SUCCESS=0

# ============================================================================
# 1. STATIC ANALYSIS
# ============================================================================

if [[ $RUN_STATIC -eq 1 ]]; then
    if run_test_suite "STATIC ANALYSIS" "tests/static/" "static"; then
        ((PASSED_TESTS++)) || true
    else
        ((FAILED_TESTS++)) || true
        OVERALL_SUCCESS=1
        [[ -n "$FAIL_FAST" ]] && exit 1
    fi
    ((TOTAL_TESTS++)) || true
fi

# ============================================================================
# 2. UNIT TESTS
# ============================================================================

if [[ $RUN_UNIT -eq 1 ]]; then
    if run_test_suite "UNIT TESTS" "tests/unit/" ""; then
        ((PASSED_TESTS++)) || true
    else
        ((FAILED_TESTS++)) || true
        OVERALL_SUCCESS=1
        [[ -n "$FAIL_FAST" ]] && exit 1
    fi
    ((TOTAL_TESTS++)) || true
fi

# ============================================================================
# 3. INTEGRATION TESTS
# ============================================================================

if [[ $RUN_INTEGRATION -eq 1 ]]; then
    if run_test_suite "INTEGRATION TESTS" "tests/integration/" ""; then
        ((PASSED_TESTS++)) || true
    else
        ((FAILED_TESTS++)) || true
        OVERALL_SUCCESS=1
        [[ -n "$FAIL_FAST" ]] && exit 1
    fi
    ((TOTAL_TESTS++)) || true
fi

# ============================================================================
# 4. PRODUCTION VALIDATION
# ============================================================================

if [[ $RUN_PRODUCTION -eq 1 ]]; then
    if run_test_suite "PRODUCTION VALIDATION" "tests/production/" "production"; then
        ((PASSED_TESTS++)) || true
    else
        ((FAILED_TESTS++)) || true
        OVERALL_SUCCESS=1
        [[ -n "$FAIL_FAST" ]] && exit 1
    fi
    ((TOTAL_TESTS++)) || true
fi

# ============================================================================
# 5. REGRESSION TESTS
# ============================================================================

if [[ $RUN_REGRESSION -eq 1 ]]; then
    if run_test_suite "REGRESSION TESTS" "tests/regression/" "regression"; then
        ((PASSED_TESTS++)) || true
    else
        ((FAILED_TESTS++)) || true
        OVERALL_SUCCESS=1
        [[ -n "$FAIL_FAST" ]] && exit 1
    fi
    ((TOTAL_TESTS++)) || true
fi

# ============================================================================
# 6. STRESS TESTS
# ============================================================================

if [[ $RUN_STRESS -eq 1 ]]; then
    echo -e "${YELLOW}⚠️  Stress tests may take several minutes...${NC}"
    echo ""
    
    if run_test_suite "STRESS TESTS" "tests/stress/" "stress"; then
        ((PASSED_TESTS++)) || true
    else
        ((FAILED_TESTS++)) || true
        OVERALL_SUCCESS=1
        # Don't fail fast on stress tests
    fi
    ((TOTAL_TESTS++)) || true
fi

# ============================================================================
# FINAL SUMMARY
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                        MASTER TEST SUMMARY                             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo "Test Suites Run: $TOTAL_TESTS"
echo -e "Passed:          ${GREEN}$PASSED_TESTS${NC}"
if [[ $FAILED_TESTS -gt 0 ]]; then
    echo -e "Failed:          ${RED}$FAILED_TESTS${NC}"
else
    echo -e "Failed:          $FAILED_TESTS"
fi

echo ""

# Cost summary (if pytest-json-report or similar installed)
if [[ $COST_REPORT -eq 1 ]]; then
    echo -e "${BLUE}Cost Summary:${NC}"
    echo "  (Cost tracking integrated in production test output)"
    echo ""
fi

# Final result
if [[ $OVERALL_SUCCESS -eq 0 ]]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    ✓ ALL TESTS PASSED                                  ║${NC}"
    echo -e "${GREEN}║              System is production-ready!                               ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════════════╝${NC}"
    exit 0
else
    echo -e "${RED}╔════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                    ✗ TESTS FAILED                                      ║${NC}"
    echo -e "${RED}║           Review failures above before deploying                       ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════════════════╝${NC}"
    exit 1
fi
