# Integration Test Suite

Comprehensive end-to-end tests that validate the Kai orchestration system with **real API calls**.

## What These Tests Validate

### ✅ Code Execution Accuracy (`test_e2e_validation.py`)
- Battery pack energy calculations are mathematically correct
- Unit conversions work properly (V×Ah→Wh, mAh→Ah→kWh)
- Multi-step calculations complete successfully
- Implicit tool routing (no keywords like "calculate" needed)

### ✅ Web Search Accuracy
- Real battery cell specs are found and returned
- Comparison queries work correctly
- Latest information is retrieved

### ✅ Multi-Tool Orchestration
- Web search → calculation workflows
- Verification workflows (search + calculate + verify)
- Tools are used in correct sequence

### ✅ Memory Operations
- Preferences are stored
- Retrieval works correctly

### ✅ Error Handling
- Impossible calculations handled gracefully
- Ambiguous queries don't crash
- Error messages are helpful

### ✅ Response Quality
- Answers are complete sentences with proper punctuation
- Natural language, not JSON dumps
- Readable and well-formatted
- Contain correct numerical answers

### ✅ Cost Efficiency
- Local queries are free (or <$0.001)
- Cost tracking accumulates correctly
- External calls only when necessary

### ✅ Self-Learning (Reflection)
- Reflection agent generates insights
- Memory vault integration works

## Prerequisites

1. **Ollama with Granite**:
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Pull Granite model
   ollama pull granite4-micro
   
   # Start Ollama (runs on port 11434)
   ollama serve
   ```

2. **API Keys** (set as environment variables):
   ```bash
   export OPENROUTER_API_KEY="your_openrouter_key_here"
   export BRAVE_API_KEY="your_brave_api_key_here"  # Optional for web search
   ```

3. **Python Environment**:
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Running Tests

### Run All End-to-End Tests (Recommended)
```bash
pytest tests/integration/test_e2e_validation.py -v -s
```

### Run Specific Test Classes
```bash
# Only code execution tests
pytest tests/integration/test_e2e_validation.py::TestCodeExecutionAccuracy -v -s

# Only web search tests
pytest tests/integration/test_e2e_validation.py::TestWebSearchAccuracy -v -s

# Only multi-tool orchestration tests
pytest tests/integration/test_e2e_validation.py::TestMultiToolOrchestration -v -s

# Only response quality tests
pytest tests/integration/test_e2e_validation.py::TestResponseQuality -v -s

# Only cost efficiency tests
pytest tests/integration/test_e2e_validation.py::TestCostEfficiency -v -s
```

### Run Quick Validation (No External APIs)
```bash
# Only tests that use local Granite (free)
pytest tests/integration/test_e2e_validation.py::TestCodeExecutionAccuracy -v -s
pytest tests/integration/test_e2e_validation.py::TestResponseQuality -v -s
```

### Run All Integration Tests
```bash
# Includes routing tests, model tier tests, cost tests, and e2e tests
pytest tests/integration/ -v -s
```

## Expected Costs

| Test Suite | External API Calls | Estimated Cost |
|------------|-------------------|----------------|
| Code Execution Tests | 0-2 (sanity checks) | $0.00-$0.02 |
| Web Search Tests | 2-4 | $0.02-$0.05 |
| Multi-Tool Tests | 3-5 | $0.03-$0.08 |
| Response Quality | 0-1 | $0.00-$0.01 |
| Cost Efficiency | 0 | $0.00 |
| Error Handling | 0-1 | $0.00-$0.01 |
| **Full E2E Suite** | **~10-15** | **$0.10-$0.20** |

All integration tests combined: **~$0.30-$0.50**

## What Success Looks Like

### Passing Tests
```
tests/integration/test_e2e_validation.py::TestCodeExecutionAccuracy::test_battery_pack_energy_calculation PASSED
✓ Calculation validated: Found correct value in [0.636, 636.48]

tests/integration/test_e2e_validation.py::TestCodeExecutionAccuracy::test_voltage_capacity_to_energy PASSED
✓ Correct answer found in [1040.0, 52.0, 20.0]

tests/integration/test_e2e_validation.py::TestWebSearchAccuracy::test_battery_spec_lookup PASSED
✓ Spec lookup successful - found capacity and voltage info

tests/integration/test_e2e_validation.py::TestMultiToolOrchestration::test_lookup_and_calculate PASSED
✓ Multi-tool orchestration successful

tests/integration/test_e2e_validation.py::TestResponseQuality::test_response_completeness PASSED
✓ All responses are complete

tests/integration/test_e2e_validation.py::TestCostEfficiency::test_local_queries_are_cheap PASSED
✓ Local queries are cost-efficient

======================== 15 passed in 45.2s ========================
```

### What Failures Indicate

| Failure Type | Likely Cause | Fix |
|--------------|--------------|-----|
| **Math incorrect** | Plan analyzer not routing to code_exec | Check `ANALYZER_SYSTEM_PROMPT` |
| **No web results** | BRAVE_API_KEY missing or web_search not routing | Check API key, verify plan routing |
| **JSON response** | Presenter not working | Check `GranitePresenter` prompt |
| **Cost too high** | External models being called unnecessarily | Check sanity checker/specialist routing |
| **Reflection fails** | Reflection agent not initialized | Check orchestrator setup |

## Debugging Failed Tests

### Verbose Output
```bash
pytest tests/integration/test_e2e_validation.py -v -s --tb=long
```

### Single Test with Full Debug
```bash
pytest tests/integration/test_e2e_validation.py::TestCodeExecutionAccuracy::test_battery_pack_energy_calculation -v -s --tb=long --log-cli-level=DEBUG
```

### Check Orchestrator Logs
```bash
# Run with debug logging
export LOG_LEVEL=DEBUG
pytest tests/integration/test_e2e_validation.py -v -s
```

## Test Coverage Matrix

| Feature | E2E Test | Model Tier Test | Cost Test | Routing Test |
|---------|----------|-----------------|-----------|--------------|
| Code execution accuracy | ✅ | ✅ | ✅ | ✅ |
| Web search routing | ✅ | - | - | ✅ |
| Multi-tool coordination | ✅ | - | - | ✅ |
| Memory operations | ✅ | - | - | ✅ |
| Granite→Grok→Sonnet | - | ✅ | - | - |
| Cost tracking | ✅ | - | ✅ | - |
| Response quality | ✅ | ✅ | - | - |
| Error handling | ✅ | ✅ | - | - |
| Source awareness | ✅ | - | - | ✅ |
| Reflection/self-learning | ✅ | - | - | - |

## Continuous Integration

Add to CI/CD pipeline:
```yaml
# .github/workflows/integration-tests.yml
- name: Run Integration Tests
  env:
    OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
    BRAVE_API_KEY: ${{ secrets.BRAVE_API_KEY }}
  run: |
    ollama serve &
    sleep 5
    ollama pull granite4-micro
    pytest tests/integration/ -v --tb=short
```

## Troubleshooting

### Ollama Not Running
```
Error: Cannot connect to Ollama at http://localhost:11434
```
**Fix**: Start Ollama: `ollama serve`

### API Key Missing
```
SKIPPED [1] Web search not configured (BRAVE_API_KEY not set)
```
**Fix**: Export API key: `export BRAVE_API_KEY="your_key"`

### Model Not Found
```
Error: Model 'granite4-micro' not found
```
**Fix**: Pull model: `ollama pull granite4-micro`

### Tests Take Too Long
Some tests make real API calls and may take 30-60 seconds each. This is expected for thorough validation.

To run faster subset:
```bash
pytest tests/integration/test_e2e_validation.py::TestCodeExecutionAccuracy -v -s
```

## Contributing

When adding features, add corresponding E2E tests:

1. **New Tool**: Add test in `TestMultiToolOrchestration`
2. **New Calculation**: Add test in `TestCodeExecutionAccuracy`
3. **New Routing Logic**: Add test in `test_intelligent_routing.py`
4. **New Cost Feature**: Add test in `test_cost_aware_routing.py`

Always validate with real API calls before merging!
