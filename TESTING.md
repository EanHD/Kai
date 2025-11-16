# Testing Guide for Kai

## Quick Start

### Run All Tests
```bash
# Full test suite (includes production tests with API costs)
python scripts/run_all_tests.py

# Fast mode (skips production tests, no API costs)
python scripts/run_all_tests.py --fast

# Run specific category only
python scripts/run_all_tests.py --category unit
python scripts/run_all_tests.py --category static
```

### Run Individual Categories
```bash
# Unit tests (fast, isolated)
pytest tests/unit/ -v

# Integration tests (multi-component workflows)
pytest tests/integration/ -v

# Regression tests (bug fix validation)
pytest tests/regression/ -v

# Production tests (real API calls, $$)
pytest tests/production/ -v

# Static checks (linting, formatting, types)
pytest tests/static/ -v
```

## Test Categories

### Unit Tests (`tests/unit/`)
Fast, isolated tests for individual components:
- Code generators and sanitizers
- Response processors
- Individual tool implementations
- Helper functions

**When to add**: Testing a single function or class in isolation.

### Integration Tests (`tests/integration/`)
Tests that verify multiple components work together:
- Orchestration workflows
- Model routing
- Tool coordination
- End-to-end API flows

**When to add**: Testing interactions between 2+ components.

### Production Tests (`tests/production/`)
Tests with real API calls that validate production readiness:
- Battery pack calculations (14S5P, 10S3P)
- Multi-tool coordination
- Cost tracking accuracy
- Offline/online mode switching

**Cost**: ~$0.50-$1.00 for full suite. These tests use:
- Ollama/Granite (local, free)
- Grok-fast via OpenRouter (~$0.002/1k tokens)
- Claude Sonnet via OpenRouter (when needed)

**When to add**: Validating critical user-facing workflows with real models.

### Regression Tests (`tests/regression/`)
Tests that prevent reintroduction of fixed bugs:
- Code exec enforcement (18 tests)
- Battery calculation patterns
- JSON serialization
- API compatibility

**When to add**: After fixing any bug, add a test that would fail with the old code.

### Static Tests (`tests/static/`)
Code quality and style checks:
- Ruff linting (PEP 8, code smells)
- Ruff formatting (consistent style)
- Import validation (no circular imports)
- Type checking (mypy)
- Security checks (no hardcoded secrets)

**When to add**: Rarely. These tests evolve with coding standards.

## Cost Tracking

The test suite tracks and reports all external API costs automatically.

### Understanding Cost Reports

After running tests, you'll see a summary like:

```
💰 TEST SESSION COST SUMMARY
================================================================================

📊 Total External API Cost: $0.4250 USD

📈 Cost by Model (with call counts):
  • x-ai/grok-2-1212                 $ 0.3100  ( 15 calls, $0.0207/call)
  • anthropic/claude-sonnet-4        $ 0.1150  (  3 calls, $0.0383/call)

🧪 Top 10 Most Expensive Tests:
   1. test_battery_14s5p_calculation                   $0.1800
   2. test_battery_10s3p_calculation                   $0.1200
   3. test_multi_tool_coordination                     $0.0900

================================================================================
```

**What it means**:
- **Total Cost**: Sum of all external API calls (local Ollama is free)
- **By Model**: Which models were used and their individual costs
- **Call counts**: Number of times each model was invoked
- **Top Tests**: Which tests consumed the most API credits

**Cost controls**:
- Soft cap at 80%: System warns and prefers cheaper models
- Hard cap at 100%: System blocks further external calls
- Configured in orchestrator initialization (default $1.00)

## Offline vs Online Testing

Kai supports offline mode to test without network access.

### Offline Mode

**What it does**:
- Blocks all web search calls
- Returns structured errors from web_search tool
- Code execution still works (Docker-based, no network)
- Local Granite model still works (Ollama)

**How to enable**:
```bash
# Environment variable (highest priority)
export KAI_OFFLINE_MODE=true

# Or in config/tools.yaml
web_search:
  offline_mode: true
```

**Tests**:
- `test_offline_mode_env_var`: Verifies env var activation
- `test_offline_mode_config_file`: Verifies config activation
- `test_web_search_blocked_in_offline_mode`: Confirms blocking
- `test_code_exec_works_in_offline_mode`: Confirms code exec still works

### Online Mode

Default mode with full network access for web search.

**Tests**:
- `test_online_mode_env_var`: Verifies online stays active
- `test_web_search_allowed_in_online_mode`: Confirms search works

## Test Output Interpretation

### Successful Run
```
✅ ALL TESTS PASSED

By Category:
Category        Passed   Failed   Skipped  Time      
------------------------------------------------------------
✓ static        8        0        0        3.21s
✓ unit          12       0        0        2.45s
✓ regression    18       0        1        5.67s
✓ integration   4        0        0        8.32s
✓ production    9        0        0        45.12s
------------------------------------------------------------
TOTAL           51       0        1        64.77s

💰 No external API costs incurred during test session ✓
```

### Failed Run
```
❌ 2 TEST(S) FAILED

regression:
  - tests/regression/test_code_exec_enforcement.py::test_battery_pattern_detection

production:
  - tests/production/test_production_ready.py::test_battery_14s5p_calculation
```

### Skipped Tests

**Expected skip**:
- `test_math_routes_to_code_exec`: Intentionally skipped, validated by production tests

**Reason**: This test requires expensive API calls and duplicates coverage from:
- 18 regression tests in `test_code_exec_enforcement.py`
- 9 production tests validating real calculations

The test remains as historical documentation of Bug #2.

## Development Workflow

### Before Committing
```bash
# Run fast checks
python scripts/run_all_tests.py --fast

# Fix any formatting issues
ruff format src/ tests/

# Fix any lint issues
ruff check --fix src/ tests/
```

### Before Releasing
```bash
# Full validation with production tests
python scripts/run_all_tests.py

# Check cost summary - should be under $1.00
# All categories should pass
```

### Adding New Tests

1. **Choose the right category**:
   - Unit: Testing one function/class
   - Integration: Testing 2+ components together
   - Production: Validating with real API calls
   - Regression: Preventing a specific bug from returning

2. **Follow existing patterns**:
   - Use `pytest.mark.asyncio` for async tests
   - Use descriptive test names: `test_<what>_<does>_<when>`
   - Add docstrings explaining what's being tested

3. **Track costs in production tests**:
   ```python
   # If your test makes external API calls
   pytest.track_test_cost(
       test_name="test_my_feature",
       model="x-ai/grok-2-1212", 
       cost=0.0123
   )
   ```

4. **Run your new tests**:
   ```bash
   pytest tests/unit/test_my_new_feature.py -v
   ```

## Continuous Integration

The master test runner is designed for CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Test Suite
  run: python scripts/run_all_tests.py --fast
  
- name: Run Production Tests (scheduled)
  run: python scripts/run_all_tests.py
  if: github.event_name == 'schedule'
```

**Why `--fast` for CI**:
- No API costs for every PR
- Faster feedback (skips ~45s of production tests)
- Production tests can run on schedule (nightly, weekly)

## Troubleshooting

### Tests Hanging
- Ollama not running: `ollama serve`
- Docker not available: Start Docker daemon
- Network issues: Try `--category unit` to isolate

### Import Errors
```bash
# Reinstall dependencies
pip install -e .

# Check for circular imports
pytest tests/static/test_code_quality.py::TestImports::test_no_circular_imports -v
```

### Cost Overruns
- Use `--fast` to skip production tests
- Check `config/models.yaml` for correct cost rates
- Review cost summary to find expensive tests

### Formatting Failures
```bash
# Auto-fix all formatting
ruff format src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/
```

## Architecture Guarantees

Tests enforce these core principles (see `AGENTS.md`):

1. **No Mental Math**: All calculations must route through `code_exec`
2. **Granite is Presenter**: Only Granite generates user-facing text
3. **Plan-Execute-Present**: Complex queries follow full pipeline
4. **Offline Safety**: System degrades gracefully without network
5. **Cost Controls**: Hard and soft caps enforced

**Do not weaken these guarantees**. Tests exist to prevent regression.

## References

- **Architecture**: See `AGENTS.md` for system design
- **API**: See `docs/api.md` for endpoint docs
- **Configuration**: See `docs/CONFIGURATION.md` for settings
