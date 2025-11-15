# Orchestration V2 Integration Guide

## Status: Ready for Integration

All core components are complete and tested. This guide explains how to integrate the new orchestration system into the main `Orchestrator` class.

---

## ✅ What's Complete

1. **Plan Types** (`src/core/plan_types.py`) - Type system for all schemas
2. **Plan Analyzer** (`src/core/plan_analyzer.py`) - Granite generates JSON plans
3. **Specialist Verifier** (`src/core/specialists/verification.py`) - Grok/Sonnet verification
4. **Plan Executor** (`src/core/plan_executor.py`) - Executes plans with dependencies
5. **Granite Presenter** (`src/core/presenters/granite_presenter.py`) - Finalizes responses

**Tests**: 43 unit tests passing ✅

---

## 🔧 Integration Steps

### Step 1: Update Orchestrator Imports

**File**: `src/core/orchestrator.py`

Add at top:
```python
from src.core.plan_analyzer import PlanAnalyzer
from src.core.plan_executor import PlanExecutor
from src.core.presenters.granite_presenter import GranitePresenter
from src.core.specialists.verification import SpecialistVerifier
```

### Step 2: Initialize New Components

In `Orchestrator.__init__()`, add:
```python
# Orchestration V2 components
self.plan_analyzer = PlanAnalyzer(self.local_connector)

# Get fast/strong external connectors
fast_connector = self.external_connectors.get("grok-beta")
strong_connector = self.external_connectors.get("claude-sonnet")

self.specialist_verifier = SpecialistVerifier(
    fast_connector=fast_connector,
    strong_connector=strong_connector,
)

self.plan_executor = PlanExecutor(
    tools=self.tools,
    sanity_checker=self.sanity_checker,
    specialist_verifier=self.specialist_verifier,
)

self.presenter = GranitePresenter(self.local_connector)

# Feature flag
self.use_orchestration_v2 = os.getenv(
    "KAI_ORCHESTRATION_V2", "false"
).lower() == "true"
```

### Step 3: Add process_query_v2 Method

Add new method to `Orchestrator`:
```python
async def process_query_v2(
    self,
    query_text: str,
    conversation: ConversationSession,
) -> Response:
    """Process query using orchestration v2 pipeline.
    
    Flow:
    1. Analyzer generates JSON plan
    2. Executor runs steps in dependency order
    3. Presenter generates final answer
    
    Args:
        query_text: User's query
        conversation: Conversation session
        
    Returns:
        Response object with final answer
    """
    logger.info("Using Orchestration V2 pipeline")
    
    # Step 1: Analyze → Plan
    plan = await self.plan_analyzer.analyze(query_text)
    
    logger.info(
        f"Plan generated: intent={plan.intent}, "
        f"complexity={plan.complexity.value}, "
        f"steps={len(plan.steps)}"
    )
    
    # Step 2: Execute Plan → Results
    execution_results = await self.plan_executor.execute(plan)
    
    logger.info(
        f"Plan executed: tools={len(execution_results['tool_results'])}, "
        f"specialists={len(execution_results['specialist_results'])}"
    )
    
    # Step 3: Finalize → Answer
    final_output = await self.presenter.finalize(
        original_query=query_text,
        plan=plan.to_dict(),
        **execution_results
    )
    
    logger.info(f"Finalization complete: {len(final_output.final_answer)} chars")
    
    # Create response object
    response = Response(
        query_id=str(uuid.uuid4()),
        mode="concise",  # TODO: derive from plan
        content=final_output.final_answer,
        token_count=0,  # TODO: sum from execution
        cost=0.0,  # TODO: sum from execution
    )
    
    # Add citations
    for citation_id in final_output.citations_used:
        # TODO: extract from execution_results citation_map
        pass
    
    # Add debug info
    response.metadata = final_output.debug_info
    
    return response
```

### Step 4: Route to V2 in main process_query

Modify existing `process_query` method:
```python
async def process_query(
    self,
    query_text: str,
    conversation: ConversationSession,
) -> Response:
    """Process a query (routes to v1 or v2)."""
    
    # Route to V2 if enabled
    if self.use_orchestration_v2:
        return await self.process_query_v2(query_text, conversation)
    
    # Otherwise use existing V1 logic
    # ... (current implementation) ...
```

### Step 5: Add Environment Variable

**File**: `.env`

Add:
```bash
# Orchestration V2
KAI_ORCHESTRATION_V2=false  # Set to 'true' to enable
```

### Step 6: Update Config for Model Names

Make sure config has correct model identifiers:
```bash
# External models for orchestration
KAI_EXTERNAL_FAST=grok-beta
KAI_EXTERNAL_STRONG=claude-sonnet-4-20250514
```

---

## 🧪 Testing Strategy

### Unit Tests (Already Passing ✅)
- Plan types
- Plan analyzer
- Specialist verifier
- Plan executor (dependency resolution)
- Granite presenter

### Integration Tests (To Add)

**Test 1: Battery Query**
```python
async def test_battery_query_orchestration_v2():
    """Test full pipeline with battery pack query."""
    query = """I'm building a 10s4p pack with Molicel P42A cells.
    I've seen conflicting specs online. Can you check at least
    two sources and calculate the total Wh and estimated range
    for a 500W e-scooter at 18mph? Show your work."""
    
    # Enable V2
    os.environ["KAI_ORCHESTRATION_V2"] = "true"
    
    # Create orchestrator (with real or mocked components)
    orchestrator = create_test_orchestrator()
    
    # Process query
    response = await orchestrator.process_query(query, conversation)
    
    # Verify
    assert "P42A" in response.content
    assert "Wh" in response.content
    assert len(response.citations) > 0
    # Should NOT contain <search> tags
    assert "<search>" not in response.content
```

**Test 2: Simple Math (No Escalation)**
```python
async def test_simple_math_no_escalation():
    """Test that simple queries don't call external models."""
    query = "What's 1543 * 892?"
    
    os.environ["KAI_ORCHESTRATION_V2"] = "true"
    
    orchestrator = create_test_orchestrator()
    response = await orchestrator.process_query(query, conversation)
    
    # Should use code_exec but not specialists
    assert "1376356" in response.content or "1,376,356" in response.content
    # Verify no external model was called
    assert response.metadata.get("used_specialists", []) == []
```

**Test 3: Fallback When Tools Disabled**
```python
async def test_fallback_when_tools_disabled():
    """Test graceful degradation when tools unavailable."""
    query = "Calculate 10s4p battery pack Wh"
    
    os.environ["KAI_ORCHESTRATION_V2"] = "true"
    
    # Create orchestrator with no tools
    orchestrator = create_test_orchestrator(tools={})
    response = await orchestrator.process_query(query, conversation)
    
    # Should still return answer (from Granite alone)
    assert response.content
    assert len(response.content) > 0
```

---

## 📊 Expected Behavior Changes

### Before (V1):
```
Query → Granite/Sonnet → Sanity → User
```
- Tools show "not available"
- Sonnet writes prose with <search> tags
- No structured handoffs
- Inconsistent voice

### After (V2):
```
Query → Analyzer → Executor (tools + sanity + specialists) → Presenter → User
```
- Tools actually execute
- Specialists return JSON only
- Granite maintains voice
- Citations numbered
- No internal tags leak

---

## 🎯 Migration Path

### Phase 1: Testing (Week 1)
1. Set `KAI_ORCHESTRATION_V2=false` (default)
2. Add integration tests
3. Test with real queries
4. Fix any issues

### Phase 2: Canary (Week 2)
1. Enable for 10% of requests
2. Monitor logs for errors
3. Compare V1 vs V2 quality
4. Tune prompts based on results

### Phase 3: Rollout (Week 3)
1. Enable for 50% of requests
2. Monitor metrics (latency, cost, quality)
3. Enable for 100% if stable
4. Remove V1 code path

### Phase 4: Optimization (Week 4)
1. Parallel tool execution
2. Plan caching
3. Prompt tuning
4. Cost optimization

---

## 🔍 Monitoring & Logging

Add structured logging at each stage:

```python
# After analyzer
logger.info("plan_generated", extra={
    "plan_id": plan.plan_id,
    "complexity": plan.complexity.value,
    "capabilities": plan.capabilities,
    "step_count": len(plan.steps),
})

# After executor
logger.info("plan_executed", extra={
    "plan_id": plan.plan_id,
    "tools_used": list(execution_results["tool_results"].keys()),
    "specialist_used": "verification" in execution_results["specialist_results"],
})

# After presenter
logger.info("finalization_complete", extra={
    "plan_id": plan.plan_id,
    "answer_length": len(final_output.final_answer),
    "citations": len(final_output.citations_used),
})
```

---

## 🚨 Known Issues & Workarounds

### Issue 1: Tool Registration Mismatch
**Problem**: Tools registered as "code_execution" but orchestrator expects "code_exec"

**Solution**: Already fixed in `src/cli/main.py` - tools now registered with correct names

### Issue 2: External Model Not Configured
**Problem**: `grok-beta` or `claude-sonnet` not in external_connectors

**Workaround**: Specialist verifier handles this gracefully, falls back to local model

### Issue 3: JSON Parsing Failures
**Problem**: Granite sometimes wraps JSON in markdown

**Solution**: All parsers have robust fallback logic (try direct parse, try markdown extraction, try first { to last })

---

## 🎓 Example Plans

### Battery Query Plan (Generated by Analyzer):
```json
{
  "intent": "battery_pack_design_with_verification",
  "complexity": "complex",
  "safety_level": "high",
  "capabilities": ["web_search", "code_exec", "sanity_check", "verification"],
  "steps": [
    {
      "id": "search_specs",
      "type": "tool_call",
      "tool": "web_search",
      "description": "Find P42A specs from 2+ sources",
      "depends_on": []
    },
    {
      "id": "compute_pack",
      "type": "tool_call",
      "tool": "code_exec",
      "description": "Calculate Wh and range",
      "depends_on": ["search_specs"]
    },
    {
      "id": "sanity",
      "type": "sanity_check",
      "depends_on": ["compute_pack"]
    },
    {
      "id": "finalize",
      "type": "finalization",
      "depends_on": ["search_specs", "compute_pack", "sanity"]
    }
  ]
}
```

### Simple Math Plan:
```json
{
  "intent": "arithmetic_calculation",
  "complexity": "simple",
  "safety_level": "normal",
  "capabilities": ["code_exec"],
  "steps": [
    {
      "id": "calculate",
      "type": "tool_call",
      "tool": "code_exec"
    },
    {
      "id": "finalize",
      "type": "finalization",
      "depends_on": ["calculate"]
    }
  ]
}
```

---

## ✅ Pre-Integration Checklist

- [x] Plan types defined
- [x] Plan analyzer implemented
- [x] Specialist verifier implemented
- [x] Plan executor implemented
- [x] Granite presenter implemented
- [x] Unit tests passing (43/43)
- [ ] Integration tests written
- [ ] Orchestrator v2 method added
- [ ] Feature flag configured
- [ ] Logging added
- [ ] Metrics added
- [ ] Documentation updated

---

## 🚀 Next Steps

1. **Add integration tests** (test_orchestration_v2.py)
2. **Integrate into Orchestrator** (follow steps 1-5 above)
3. **Test with real queries** (enable flag locally)
4. **Deploy behind feature flag** (KAI_ORCHESTRATION_V2=false initially)
5. **Monitor and tune** (watch logs, adjust prompts)
6. **Gradual rollout** (10% → 50% → 100%)

Once complete, Kai will be a true orchestration system with:
- ✅ Structured JSON handoffs
- ✅ Tools that actually execute
- ✅ Specialists that don't write prose
- ✅ Consistent Kai voice
- ✅ Verifiable results
- ✅ Cost-efficient routing (Grok → Sonnet only when needed)

---

**Questions?** See ORCHESTRATION_BLUEPRINT.md for architecture details.
