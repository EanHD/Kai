# Kai Orchestration Blueprint - Implementation Status

## ✅ Phase 1: Core Schemas (COMPLETE)

**File**: `src/core/plan_types.py`

Implemented:
- `Plan`: Complete execution plan with steps and dependencies
- `PlanStep`: Individual step (tool_call, sanity_check, model_call, finalization)
- `ToolResult`: Results from tool executions
- `VerificationResult`: Structured data from Sonnet/Grok
- `VerifiedSpecs`, `PackCalculation`, `RangeEstimate`: Domain-specific schemas
- `FinalizationInput`, `FinalizationOutput`: Presenter schemas

**Status**: Ready for use ✅

---

## ✅ Phase 2: Plan Analyzer (COMPLETE)

**File**: `src/core/plan_analyzer.py`

Implemented:
- `PlanAnalyzer` class using Granite to generate JSON plans
- System prompt for structured plan generation
- JSON parsing with fallback logic
- Automatic complexity/safety detection
- Fallback to simple plan when analysis fails

**Status**: Ready for use ✅

---

## ✅ Phase 3: Specialist Verification (COMPLETE)

**File**: `src/core/specialists/verification.py`

Implemented:
- `SpecialistVerifier` class with fast/strong model routing
- Verification prompt for JSON-only responses
- JSON parsing and validation
- Conversion to `VerificationResult` objects
- Error handling and fallbacks

**Status**: Ready for use ✅

---

## ✅ Phase 4: Plan Executor (COMPLETE)

**File**: `src/core/plan_executor.py`

Implemented:
- `PlanExecutor` class with full dependency resolution
- Topological sort for correct step ordering
- Tool call dispatcher with input resolution
- Sanity check integration
- Smart specialist escalation (Grok vs Sonnet routing)
- Reference resolution (FROM_step_id syntax)
- Graceful error handling
- Circular dependency detection

**Key Features**:
- Executes steps in dependency order
- Routes to Grok Fast for normal queries
- Routes to Sonnet Strong for sanity failures or high safety
- Resolves references between steps
- Handles missing tools gracefully

**Status**: Ready for use ✅

---

## ✅ Phase 5: Presenter/Finalizer (COMPLETE)

**File**: `src/core/presenters/granite_presenter.py`

Implemented:
- `GranitePresenter` class using Granite for finalization
- Finalization prompt for natural language generation
- Citation extraction from tool/specialist results
- Confidence-aware tone adjustments
- JSON-only response format with fallback
- Consistent Kai voice maintenance

**Key Features**:
- Takes structured results → generates natural language
- Auto-extracts and numbers citations [1], [2]
- Adjusts tone based on confidence levels
- Falls back gracefully when finalization fails
- Maintains consistent Kai voice across all responses

**Status**: Ready for use ✅

---

## 🚧 Phase 6: Orchestrator Integration (IN PROGRESS)

**File**: `src/core/orchestrator.py` (TO MODIFY)

Changes needed:
1. Replace current `process_query` with plan-based flow:
   ```python
   async def process_query_v2(self, query_text: str, conversation: ConversationSession):
       # Step 1: Analyze → Plan
       plan = await self.plan_analyzer.analyze(query_text)
       
       # Step 2: Execute Plan → Results
       execution_results = await self.plan_executor.execute(plan)
       
       # Step 3: Finalize → Answer
       final_output = await self.presenter.finalize(
           plan=plan.to_dict(),
           **execution_results
       )
       
       return Response(
           content=final_output.final_answer,
           mode=final_output.debug_info.get("mode", "concise"),
           ...
       )
   ```

2. Add feature flag:
   ```python
   USE_ORCHESTRATION_V2 = os.getenv("KAI_ORCHESTRATION_V2", "false").lower() == "true"
   
   if USE_ORCHESTRATION_V2:
       return await self.process_query_v2(query_text, conversation)
   else:
       return await self.process_query(query_text, conversation)  # Old path
   ```

---

## 📋 Phase 7: Testing Strategy

**Unit Tests Needed**:
- `test_plan_analyzer.py`: Query → Plan mapping
- `test_plan_executor.py`: Dependency resolution, step execution
- `test_specialist_verifier.py`: JSON parsing, error handling
- `test_presenter.py`: Finalization logic

**Integration Tests Needed**:
- Battery pack query (full pipeline)
- Simple math query (code_exec only)
- Spec verification query (web_search + specialist)
- Fallback behavior (when tools/models unavailable)

---

## 🎯 Implementation Priority

### Week 1: Core Execution ✅ COMPLETE
1. ✅ Plan types
2. ✅ Plan analyzer
3. ✅ Specialist verifier
4. ✅ Plan executor (dependency resolution + tool dispatch)
5. ✅ Granite presenter
6. ✅ Basic unit testing (43 tests passing)

### Week 2: Integration & Testing ⏳ IN PROGRESS
1. ⏳ Orchestrator v2 integration
2. ⏳ Feature flag + backward compat
3. ⏳ Integration tests (battery query, etc.)
4. ⏳ End-to-end testing

### Week 3: Polish & Production
1. ⏳ Response time optimization
2. ⏳ Cost tracking integration
3. ⏳ Logging improvements
4. ⏳ Documentation
5. ⏳ Deploy behind flag

---

## 🔧 Configuration

**.env additions**:
```bash
# Orchestration
KAI_ORCHESTRATION_V2=true
KAI_USE_PLAN_ANALYZER=true

# Model routing
KAI_EXTERNAL_FAST_MODEL=grok-beta  # For normal complex queries
KAI_EXTERNAL_STRONG_MODEL=claude-sonnet-4-20250514  # For verification

# Thresholds
KAI_COMPLEXITY_THRESHOLD_EXTERNAL=0.6  # When to use external models
KAI_SAFETY_ESCALATION_ENABLED=true  # Auto-escalate sanity failures
```

---

## 📊 Expected Behavior Changes

### Before (Current):
```
User query
  ↓
Granite/Sonnet (whoever answers)
  ↓
Sanity check (maybe)
  ↓
User sees whatever model said
```

**Problems**:
- Sonnet writes prose directly to users
- Tools "not available" even when configured
- No structured handoffs
- Inconsistent voice

### After (Orchestration V2):
```
User query
  ↓
Granite Analyzer → JSON Plan
  ↓
Plan Executor:
  - web_search (if needed)
  - code_exec (if needed)
  - sanity_check (always)
  ↓
Specialist (only if sanity fails or complex):
  - Grok Fast (normal)
  - Sonnet Strong (verification)
  ↓
Granite Presenter → Final Answer
  ↓
User sees clean, consistent Kai voice
```

**Benefits**:
- ✅ Tools actually execute
- ✅ Sonnet never writes to users
- ✅ Structured JSON handoffs
- ✅ Consistent Kai voice
- ✅ Lower latency (Grok for most, Sonnet only when needed)
- ✅ Lower cost (targeted specialist use)
- ✅ Verifiable results (JSON schemas)

---

## 🚀 Next Steps

**Immediate** (this session):
1. Create `PlanExecutor` class
2. Create basic `GranitePresenter` class
3. Write integration test for battery query
4. Test end-to-end flow

**Short-term** (next commit):
1. Integrate into main orchestrator with feature flag
2. Add logging at each stage
3. Update API handlers to use new flow
4. Deploy behind flag for testing

**Long-term** (next sprint):
1. Optimize latency (parallel tool execution)
2. Add caching for plans
3. Fine-tune prompts based on real usage
4. Add monitoring/metrics
5. Document for team

---

## 💡 Key Design Decisions

1. **JSON-only specialists**: Prevents prose generation, forces structured data
2. **Two-tier external models**: Grok for speed, Sonnet for accuracy
3. **Granite bookends**: Analyzer at start, Presenter at end = consistent voice
4. **Explicit dependencies**: Steps declare deps, executor handles order
5. **Graceful degradation**: Missing tools/models don't break the system
6. **Feature flag**: Old path still works, new path opt-in

This architecture transforms Kai from a "chat wrapper" to a true **orchestration system**.
