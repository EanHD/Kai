# Test Coverage Matrix

This document maps all features to their test coverage across different test types.

Last updated: 2025-11-14

## Legend
- ✅ Fully tested with comprehensive coverage
- ⚠️  Partially tested or basic coverage only
- ❌ Not yet tested
- 🔧 Test exists but currently failing

## Core Functionality

| Feature | Unit | Integration | Production | Regression | Stress | Notes |
|---------|------|-------------|------------|------------|--------|-------|
| **Plan Generation** |
| Math query → code_exec routing | ❌ | ✅ | ✅ | ✅ | ❌ | Canonical schema enforced |
| Multi-step plan creation | ❌ | ✅ | ⚠️ | ❌ | ❌ | Basic coverage |
| Tool selection logic | ❌ | ✅ | ⚠️ | ❌ | ❌ | Needs more edge cases |
| Dependency resolution | ❌ | ⚠️ | ❌ | ❌ | ❌ | Implicit in integration tests |
| **Plan Execution** |
| Sequential step execution | ❌ | ✅ | ✅ | ❌ | ❌ | |
| Dependency tracking | ❌ | ⚠️ | ❌ | ❌ | ❌ | |
| Error handling/recovery | ❌ | ✅ | ✅ | ❌ | ❌ | |
| Parallel execution (future) | ❌ | ❌ | ❌ | ❌ | ❌ | Not yet implemented |
| **Response Presentation** |
| Natural language formatting | ❌ | ✅ | ✅ | ❌ | ❌ | |
| JSON escaping | ❌ | ⚠️ | ❌ | ❌ | ❌ | |
| Error message formatting | ❌ | ⚠️ | ✅ | ❌ | ❌ | |
| Specialist result integration | ❌ | ✅ | ⚠️ | ✅ | ❌ | Serialization regression test |

## Model Integration

| Feature | Unit | Integration | Production | Regression | Stress | Notes |
|---------|------|-------------|------------|------------|--------|-------|
| **Granite (Local)** |
| Plan generation | ❌ | ✅ | ✅ | ✅ | ❌ | Core analyzer |
| Response finalization | ❌ | ✅ | ✅ | ❌ | ❌ | GranitePresenter |
| Conversation context | ❌ | ⚠️ | ⚠️ | ❌ | ✅ | Long context stress test |
| Function calling | ❌ | ✅ | ⚠️ | ❌ | ❌ | |
| **Grok Fast (External)** |
| As reasoning specialist | ❌ | ⚠️ | ✅ | ❌ | ❌ | When local fails |
| Cost tracking | ❌ | ✅ | ✅ | ❌ | ✅ | |
| Rate limiting | ❌ | ❌ | ❌ | ❌ | ✅ | Rapid-fire tests |
| Error handling | ❌ | ⚠️ | ✅ | ❌ | ❌ | |
| **Claude Sonnet (External)** |
| As strong reasoner | ❌ | ⚠️ | ✅ | ❌ | ❌ | Complex queries |
| Cost tracking | ❌ | ✅ | ✅ | ❌ | ✅ | |
| Streaming responses | ❌ | ❌ | ❌ | ❌ | ❌ | API feature |
| Error handling | ❌ | ⚠️ | ✅ | ❌ | ❌ | |

## Tools

| Feature | Unit | Integration | Production | Regression | Stress | Notes |
|---------|------|-------------|------------|------------|--------|-------|
| **Code Execution** |
| Python code execution | ⚠️ | ✅ | ✅ | ❌ | ⚠️ | |
| Canonical schema validation | ❌ | ✅ | ✅ | ✅ | ❌ | Regression test added |
| Task mode: battery_pack_energy | ❌ | ✅ | ✅ | ❌ | ❌ | 13S4P, 14S5P |
| Task mode: battery_range | ❌ | ✅ | ✅ | ❌ | ❌ | |
| Task mode: unit_conversion | ❌ | ✅ | ⚠️ | ❌ | ❌ | Basic tests |
| Task mode: physics_calculation | ❌ | ⚠️ | ❌ | ❌ | ❌ | Limited coverage |
| Task mode: generic_math | ❌ | ✅ | ⚠️ | ❌ | ❌ | |
| Raw code mode | ❌ | ⚠️ | ❌ | ❌ | ❌ | |
| Docker isolation | ❌ | ⚠️ | ❌ | ❌ | ❌ | Implicit |
| Memory limits | ❌ | ⚠️ | ❌ | ✅ | ⚠️ | Regression + stress |
| Timeout handling | ❌ | ⚠️ | ❌ | ❌ | ✅ | Stress tests |
| Large output handling | ❌ | ❌ | ❌ | ❌ | ✅ | Stress test |
| **Web Search** |
| Brave API integration | ❌ | ⚠️ | ❌ | ❌ | ❌ | Skipped if no API key |
| Query formulation | ❌ | ❌ | ❌ | ❌ | ❌ | |
| Result parsing | ❌ | ⚠️ | ❌ | ❌ | ❌ | |
| Error handling | ❌ | ⚠️ | ❌ | ❌ | ❌ | |
| **Memory/RAG** |
| Vector storage | ❌ | ⚠️ | ❌ | ❌ | ❌ | |
| Embedding generation | ❌ | ⚠️ | ❌ | ✅ | ❌ | Optional handling regression |
| Semantic search | ❌ | ⚠️ | ❌ | ❌ | ❌ | |
| Memory encryption | ❌ | ❌ | ❌ | ❌ | ❌ | |
| **Sentiment Analysis** |
| VADER integration | ❌ | ⚠️ | ❌ | ❌ | ❌ | |
| Sentiment scoring | ❌ | ⚠️ | ❌ | ❌ | ❌ | |

## Cost Management

| Feature | Unit | Integration | Production | Regression | Stress | Notes |
|---------|------|-------------|------------|------------|--------|-------|
| Cost tracking accuracy | ⚠️ | ✅ | ✅ | ✅ | ✅ | Comprehensive |
| Soft cap (80%) warnings | ❌ | ⚠️ | ❌ | ❌ | ✅ | Stress test |
| Hard cap (100%) enforcement | ❌ | ⚠️ | ❌ | ❌ | ✅ | Stress test |
| Per-model cost breakdown | ❌ | ⚠️ | ✅ | ❌ | ❌ | Production tracking |
| Session cost accumulation | ❌ | ✅ | ✅ | ✅ | ✅ | |
| Cost reporting | ❌ | ✅ | ✅ | ❌ | ❌ | |

## Quality Assurance

| Feature | Unit | Integration | Production | Regression | Stress | Notes |
|---------|------|-------------|------------|------------|--------|-------|
| **Calculation Accuracy** |
| Battery pack energy (13S4P) | ❌ | ✅ | ✅ | ❌ | ❌ | 0.636 kWh validated |
| Battery pack energy (14S5P) | ❌ | ✅ | ✅ | ❌ | ❌ | 1.26 kWh validated |
| Battery range calculations | ❌ | ✅ | ✅ | ❌ | ❌ | 50 miles validated |
| Voltage × Capacity → Energy | ❌ | ✅ | ✅ | ❌ | ❌ | 1040 Wh validated |
| Generic math operations | ❌ | ✅ | ⚠️ | ❌ | ✅ | Basic + stress |
| **Response Quality** |
| Natural language (not JSON) | ❌ | ✅ | ✅ | ❌ | ❌ | |
| Proper grammar/punctuation | ❌ | ⚠️ | ✅ | ❌ | ❌ | |
| Appropriate detail level | ❌ | ⚠️ | ❌ | ❌ | ❌ | |
| No debug info leakage | ❌ | ⚠️ | ✅ | ❌ | ❌ | |
| **Error Recovery** |
| Graceful tool failures | ❌ | ✅ | ✅ | ❌ | ❌ | |
| Malformed LLM responses | ❌ | ⚠️ | ✅ | ❌ | ❌ | |
| Network timeouts | ❌ | ❌ | ✅ | ❌ | ❌ | |
| Invalid user input | ❌ | ⚠️ | ✅ | ❌ | ❌ | |
| Cost cap during operation | ❌ | ⚠️ | ❌ | ❌ | ✅ | |

## System Features

| Feature | Unit | Integration | Production | Regression | Stress | Notes |
|---------|------|-------------|------------|------------|--------|-------|
| **Reflection Agent** |
| Episode reflection | ❌ | ⚠️ | ❌ | ✅ | ❌ | API regression test |
| Memory storage | ❌ | ⚠️ | ❌ | ❌ | ❌ | |
| Learning from failures | ❌ | ❌ | ❌ | ❌ | ❌ | |
| **Source Awareness** |
| CLI vs API differentiation | ❌ | ⚠️ | ❌ | ❌ | ❌ | |
| Analytics tracking | ❌ | ❌ | ❌ | ❌ | ❌ | |
| **Conversation Management** |
| Message history | ❌ | ✅ | ⚠️ | ❌ | ✅ | Long context stress |
| Context window management | ❌ | ⚠️ | ❌ | ❌ | ✅ | 50+ messages |
| Multi-user isolation | ❌ | ❌ | ❌ | ❌ | ✅ | Concurrent stress |

## Static Analysis

| Feature | Unit | Integration | Production | Regression | Stress | Notes |
|---------|------|-------------|------------|------------|--------|-------|
| Ruff linting | ✅ | ❌ | ❌ | ❌ | ❌ | Static test suite |
| Ruff formatting | ✅ | ❌ | ❌ | ❌ | ❌ | Static test suite |
| Import correctness | ✅ | ❌ | ❌ | ✅ | ❌ | All modules importable |
| Circular import detection | ✅ | ❌ | ❌ | ❌ | ❌ | Critical modules |
| Type checking (mypy) | ⚠️ | ❌ | ❌ | ❌ | ❌ | Non-blocking warnings |
| No __pycache__ in git | ✅ | ❌ | ❌ | ❌ | ❌ | |
| Module docstrings | ⚠️ | ❌ | ❌ | ❌ | ❌ | Warning only |
| No hardcoded secrets | ⚠️ | ❌ | ❌ | ❌ | ❌ | Warning only |

## Known Gaps (TODO)

Priority gaps to address before production:

### High Priority (P0)
- [ ] Parallel execution testing (not implemented yet)
- [ ] Streaming response validation
- [ ] Web search comprehensive coverage (requires Brave API key)
- [ ] Memory/RAG encryption validation
- [ ] Multi-user concurrent safety (partial stress test only)

### Medium Priority (P1)
- [ ] All task mode calculations (only battery tested comprehensively)
- [ ] Raw code mode testing
- [ ] Docker isolation validation
- [ ] Tool failure simulation (network, timeout, etc.)
- [ ] Conversation context window overflow

### Low Priority (P2)
- [ ] Type checking (mypy) full enforcement
- [ ] Module docstring enforcement
- [ ] Response quality metrics (grammar, detail level)
- [ ] Analytics/telemetry validation

## Test Execution

### Quick Validation (~2 min, ~$0.05)
```bash
./run_master_tests.sh --quick
```
Runs: Static + Unit + Integration (skip production/stress)

### Full Production Validation (~10 min, ~$1.50-$2.00)
```bash
./run_master_tests.sh
```
Runs: All test suites

### Specific Suites
```bash
./run_master_tests.sh --production   # Production validation only
./run_master_tests.sh --regression   # Regression tests only
./run_master_tests.sh --stress       # Stress tests only
```

## Cost Estimates

Based on current test coverage (November 2025):

| Test Suite | Estimated Cost | Time |
|------------|----------------|------|
| Static Analysis | $0.00 | 30s |
| Unit Tests | $0.00 | 1min |
| Integration Tests | $0.20-$0.40 | 2-3min |
| Production Validation | $0.50-$1.00 | 3-5min |
| Regression Tests | $0.05-$0.10 | 1min |
| Stress Tests | $0.50-$1.00 | 3-5min |
| **TOTAL (Full Suite)** | **$1.25-$2.50** | **10-15min** |

Costs vary based on:
- External model usage (Grok Fast vs Claude Sonnet)
- Query complexity (plan generation overhead)
- Number of tool invocations
- Conversation length

---

*This matrix is automatically maintained as part of the test development process.*

