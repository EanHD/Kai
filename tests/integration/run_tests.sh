#!/bin/bash
# Quick test runner for Kai integration tests
# Usage: ./tests/integration/run_tests.sh [quick|full|code|web|multi|quality|cost]

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Ollama is running
check_ollama() {
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "${RED}❌ Ollama is not running!${NC}"
        echo -e "${YELLOW}Start Ollama with: ollama serve${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Ollama is running${NC}"
}

# Check if model is available
check_model() {
    if ! ollama list | grep -q "granite4-micro"; then
        echo -e "${YELLOW}⚠️  granite4-micro not found${NC}"
        echo -e "${YELLOW}Pulling model...${NC}"
        ollama pull granite4-micro
    fi
    echo -e "${GREEN}✓ granite4-micro available${NC}"
}

# Check API keys
check_api_keys() {
    if [ -z "$OPENROUTER_API_KEY" ]; then
        echo -e "${YELLOW}⚠️  OPENROUTER_API_KEY not set (some tests will be skipped)${NC}"
    else
        echo -e "${GREEN}✓ OPENROUTER_API_KEY set${NC}"
    fi
    
    if [ -z "$BRAVE_API_KEY" ]; then
        echo -e "${YELLOW}⚠️  BRAVE_API_KEY not set (web search tests will be skipped)${NC}"
    else
        echo -e "${GREEN}✓ BRAVE_API_KEY set${NC}"
    fi
}

# Run tests
run_tests() {
    local test_arg=$1
    
    echo ""
    echo -e "${GREEN}🧪 Running Kai Integration Tests${NC}"
    echo "=================================="
    echo ""
    
    case $test_arg in
        quick)
            echo "Running quick tests (local only, no API costs)..."
            pytest tests/integration/test_e2e_validation.py::TestCodeExecutionAccuracy -v -s
            pytest tests/integration/test_e2e_validation.py::TestResponseQuality -v -s
            ;;
        full)
            echo "Running full end-to-end test suite..."
            pytest tests/integration/test_e2e_validation.py -v -s
            ;;
        code)
            echo "Running code execution accuracy tests..."
            pytest tests/integration/test_e2e_validation.py::TestCodeExecutionAccuracy -v -s
            ;;
        web)
            echo "Running web search tests..."
            pytest tests/integration/test_e2e_validation.py::TestWebSearchAccuracy -v -s
            ;;
        multi)
            echo "Running multi-tool orchestration tests..."
            pytest tests/integration/test_e2e_validation.py::TestMultiToolOrchestration -v -s
            ;;
        quality)
            echo "Running response quality tests..."
            pytest tests/integration/test_e2e_validation.py::TestResponseQuality -v -s
            ;;
        cost)
            echo "Running cost efficiency tests..."
            pytest tests/integration/test_e2e_validation.py::TestCostEfficiency -v -s
            ;;
        all)
            echo "Running ALL integration tests (e2e, routing, tiers, cost)..."
            pytest tests/integration/ -v -s
            ;;
        *)
            echo "Usage: $0 [quick|full|code|web|multi|quality|cost|all]"
            echo ""
            echo "  quick   - Fast tests using only local Granite (free)"
            echo "  full    - Complete E2E validation suite (~\$0.15)"
            echo "  code    - Code execution accuracy tests"
            echo "  web     - Web search tests (requires BRAVE_API_KEY)"
            echo "  multi   - Multi-tool orchestration tests"
            echo "  quality - Response quality tests"
            echo "  cost    - Cost efficiency tests"
            echo "  all     - All integration tests (~\$0.50)"
            echo ""
            exit 1
            ;;
    esac
}

# Main execution
echo -e "${GREEN}Kai Integration Test Runner${NC}"
echo "============================"
echo ""

# Pre-flight checks
check_ollama
check_model
check_api_keys

echo ""

# Run tests
run_tests "${1:-quick}"

echo ""
echo -e "${GREEN}✅ Tests complete!${NC}"
