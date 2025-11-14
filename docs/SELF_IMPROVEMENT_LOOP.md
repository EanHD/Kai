# Self-Improvement Loop - How Kai Gets Better Over Time

## Overview

Kai doesn't fine-tune base models. Instead, it **learns through a closed self-improvement loop** that evolves behavior without changing model weights.

## The Four-Stage Loop

**Reflection runs automatically** in both CLI and API server - use `--reflect` flag in CLI to watch it happen in real-time.

```
┌─────────────┐
│ 1. LOG      │ Every conversation stored as episode
│  Episodes   │ (messages, model, tools, cost, latency, feedback)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 2. REFLECT  │ Reflection Agent analyzes each episode (ALWAYS-ON)
│   Analysis  │ (what worked, failures, new rules, prompt tweaks)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 3. DISTILL  │ Nightly: synthesize patterns from reflections
│   Patterns  │ (rules → semantic, prompts → templates, tests)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 4. ADAPT    │ Next request uses evolved knowledge
│   Behavior  │ (RAG loads new docs, updated prompts, routing)
└─────────────┘
       │
       └──────┐ (loop continues)
```

## Memory Schema

### 1. Episodic Memory

Every conversation creates an episode:

```jsonc
{
  "type": "episodic",
  "id": "7599436d-f3cc-4146-ad30-8efd3187a5ae",
  "created_at": "2025-11-14T01:23:45Z",
  "last_used_at": "2025-11-14T01:23:45Z",
  "ttl_days": 90,
  "confidence": 1.0,
  "tags": ["python", "expert-mode"],
  "summary": "Explained Python decorators",
  "payload": {
    "session_id": "session-123",
    "user_text": "Explain Python decorators",
    "assistant_text": "Decorators are functions that modify...",
    "model_used": "granite-local",
    "tools_used": [],
    "cost": 0.0,
    "latency_ms": 743,
    "success": true,
    "feedback": "positive"  // Optional: from /good or /bad
  }
}
```

**Stored in**: `data/memory/<user_id>/episodic.jsonl`

### 2. Reflection Memory

Reflection Agent analyzes episodes:

```jsonc
{
  "type": "reflection",
  "id": "965f6ef5-8a3d-4c12-b456-789012345678",
  "created_at": "2025-11-14T01:24:10Z",
  "ttl_days": 180,
  "confidence": 0.7,
  "tags": ["auto-generated", "expert"],
  "summary": "Reflection on expert response",
  "payload": {
    "episode_id": "7599436d-f3cc-4146-ad30-8efd3187a5ae",
    "user_text": "Explain Python decorators",
    "assistant_text": "Decorators are functions...",
    "success": true,
    "mode": "expert",
    "tools_used": [],
    "reflection": "The response was clear and concise...",
    "learnings": {
      "what_went_well": [
        "Clear examples provided",
        "Covered common use cases and edge cases"
      ],
      "improvements": [
        "Could add more advanced decorator patterns",
        "Missing performance implications discussion"
      ],
      "rules": [
        "For technical topics, start with simple overview before diving deep",
        "Always include practical examples for abstract concepts"
      ],
      "prompt_suggestions": [
        "Add 'use concrete examples' to system prompt",
        "Emphasize step-by-step explanations for complex topics"
      ]
    }
  }
}
```

**Stored in**: `data/memory/<user_id>/reflections.jsonl`

### 3. Semantic Memory (Rules)

Distilled knowledge from multiple episodes:

```jsonc
{
  "type": "semantic",
  "id": "47169264-3db8-4325-ad39-5e7fde270a37",
  "created_at": "2025-11-14T02:00:00Z",
  "confidence": 0.85,
  "tags": ["rule", "distilled", "code_execution"],
  "summary": "Rule: Never call code executor for explanations",
  "payload": {
    "rule": "Never call code executor for pure natural language explanations",
    "applies_when": "intent == 'explanation' AND complexity < 0.3",
    "source": "distillation",
    "evidence": [
      "episode-abc123: unnecessary code exec for 'what is X' question",
      "episode-def456: similar failure pattern"
    ],
    "supersedes": null  // or ID of old rule
  }
}
```

**Stored in**: `data/memory/<user_id>/semantic.jsonl`

### 4. Prompt Memory (Evolvable Prompts)

Prompt templates that evolve based on performance:

```jsonc
{
  "type": "prompt",
  "id": "orchestrator_v2",
  "created_at": "2025-11-14T00:00:00Z",
  "confidence": 0.9,
  "tags": ["orchestrator", "active"],
  "summary": "Improved orchestrator prompt with code safety",
  "payload": {
    "version": "v2",
    "description": "Enhanced with code safety checks and cost awareness",
    "text": "You are Kai, an LLM orchestrator. Before executing code, verify:\n1. No unsafe operations\n2. Input validation...",
    "supersedes": "orchestrator_v1",
    "performance_metrics": {
      "success_rate": 0.94,
      "avg_cost": 0.0012,
      "avg_latency_ms": 680,
      "episodes_used": 145,
      "positive_feedback": 132,
      "negative_feedback": 8
    }
  }
}
```

**Stored in**: `data/memory/<user_id>/prompts.jsonl`

### 5. Checklist Memory (Procedural Knowledge)

Step-by-step procedures learned from experience:

```jsonc
{
  "type": "checklist",
  "id": "e89ad81f-e11e-4fb4-9ed0-11060448f0f1",
  "created_at": "2025-11-14T02:00:02Z",
  "confidence": 0.7,
  "tags": ["procedure", "distilled", "code-safety"],
  "summary": "Procedure: Verify code before execution",
  "payload": {
    "step": "Before executing code, validate syntax and check for unsafe operations",
    "domain": "code_execution",
    "source": "distillation",
    "examples": [
      "Check for os.system(), eval(), exec()",
      "Validate file paths stay within sandbox",
      "Ensure imports are from safe libraries"
    ]
  }
}
```

**Stored in**: `data/memory/<user_id>/checklists.jsonl`

### 6. Preference Memory

User-specific preferences and context:

```jsonc
{
  "type": "preference",
  "id": "pref-123",
  "created_at": "2025-11-14T01:00:00Z",
  "tags": ["user-info", "schedule"],
  "summary": "User sleep schedule",
  "payload": {
    "key": "sleep_schedule",
    "value": "11pm-7am",
    "context": "User mentioned this on 2025-11-14"
  }
}
```

**Stored in**: `data/memory/<user_id>/preferences.jsonl`

### 7. Bug Fix Memory

Failures turned into knowledge:

```jsonc
{
  "type": "bug_fix",
  "id": "bug-456",
  "created_at": "2025-11-14T03:00:00Z",
  "tags": ["bug", "routing"],
  "summary": "Fixed: Used expensive model for simple math",
  "payload": {
    "failure": "Routed '2+2' to claude-opus ($0.03) instead of granite-local (free)",
    "root_cause": "Complexity scorer didn't recognize simple arithmetic",
    "fix": "Added regex pattern for basic math to complexity analysis",
    "test_case": "tests/ai/bug_456_simple_math.yaml"
  }
}
```

**Stored in**: `data/memory/<user_id>/bugs.jsonl`

## Memory Lifecycles

### Confidence Scoring

Each memory has a `confidence` score (0-1) that tracks reliability:

- **Initial**: Based on source
  - Episodic: 1.0 (factual record)
  - Reflection: 0.7 (LLM-generated analysis)
  - Distilled rules: 0.8-0.9 (synthesized from multiple episodes)
  - User feedback: ±0.1 adjustment

- **Updates**: Confidence changes over time
  - Increases: Memory used successfully, positive feedback
  - Decreases: Memory led to failures, negative feedback, contradicted by new data

### Time-to-Live (TTL)

Default retention periods:

| Type | TTL | Rationale |
|------|-----|-----------|
| `episodic` | 90 days | Short-term context, frequent churn |
| `reflection` | 180 days | Intermediate insights |
| `semantic` | Indefinite | Core knowledge, pruned only if superseded |
| `prompt` | Indefinite | Active prompts kept, deprecated ones archived |
| `checklist` | Indefinite | Procedural knowledge |
| `preference` | Indefinite | User-specific context |
| `bug_fix` | Indefinite | Prevent regressions |

### Pruning Logic

Run via `/mem prune` or nightly maintenance:

```python
def should_prune(memory):
    # Never prune high-confidence knowledge
    if memory.confidence >= 0.9 and memory.type in ["semantic", "prompt", "checklist"]:
        return False
    
    # Expired TTL
    if memory.ttl_days and age_in_days(memory) > memory.ttl_days:
        return True
    
    # Low confidence + old
    if memory.confidence < 0.3 and age_in_days(memory) > 30:
        return True
    
    # Superseded by newer version
    if memory.payload.get("superseded_by"):
        return True
    
    return False
```

### Compression

Frequently accessed episodic memories can be compressed into semantic summaries:

```python
# Before: 100 episodes about Python decorators
episodic_001: "User asked about decorators..."
episodic_002: "User asked about @property..."
...
episodic_100: "User asked about decorator performance..."

# After distillation: 1 semantic rule
semantic_042: "User frequently asks about Python decorators. 
               Provide examples with @property, @staticmethod, and custom logging decorators."
```

## User Feedback Integration

### CLI Feedback

```bash
You: Explain decorators
Kai: [response]
You: /good  # Mark as successful

You: What's 2+2?
Kai: Let me execute code... [expensive model used]
You: /bad   # Mark as failure
```

Feedback is stored in the episode and affects:

1. **Reflection analysis**: `/bad` triggers deeper analysis of what went wrong
2. **Confidence scores**: Positive feedback boosts related rules, negative lowers them
3. **Prompt evolution**: Track which prompts lead to more `/good` vs `/bad` responses
4. **Model routing**: Learn which models work best for which tasks

### API Feedback

```json
{
  "messages": [
    {"role": "user", "content": "Explain decorators"}
  ],
  "metadata": {
    "feedback": "positive",  // or "negative"
    "feedback_detail": "Clear and helpful explanation"
  }
}
```

## Prompt Versioning

### Active Prompt Selection

The orchestrator loads the **highest-confidence, non-deprecated prompt** for each role:

```python
def get_active_prompt(role: str) -> str:
    prompts = memory_vault.list(
        mtype="prompt",
        tag=role,
        filter=lambda p: "deprecated" not in p.tags
    )
    
    # Sort by confidence * success_rate
    best = max(prompts, key=lambda p: 
        p.confidence * p.payload.get("performance_metrics", {}).get("success_rate", 0.5)
    )
    
    return best.payload["text"]
```

### Prompt Evolution Example

```
orchestrator_v1 (2025-11-10)
├─ confidence: 0.7
├─ success_rate: 0.82
├─ episodes: 89
└─ feedback: 12 negative ("uses expensive models unnecessarily")

     ↓ Reflection suggests improvement

orchestrator_v2 (2025-11-14)
├─ confidence: 0.9
├─ success_rate: 0.94
├─ episodes: 145
├─ feedback: 8 negative (much better!)
└─ changes: "Added explicit cost-awareness instructions"

     ↓ V2 outperforms V1, mark V1 as deprecated

orchestrator_v1
└─ tags: ["orchestrator", "deprecated"]
└─ superseded_by: "orchestrator_v2"
```

## AI Regression Tests

### From Failures to Tests

When a bug is fixed, the Reflection Agent can generate regression tests:

#### Code-Level Test

```python
# tests/test_routing_simple_math.py
# Auto-generated from episode 7599436d (2025-11-14)

def test_simple_math_uses_local_model():
    """Ensure simple arithmetic uses free local model, not expensive cloud."""
    response = orchestrator.route(
        messages=[{"role": "user", "content": "What's 2 + 2?"}],
        context={"intent": "calculation"}
    )
    
    assert response.model_used == "granite-local"
    assert response.cost == 0.0
    assert "code_executor" not in response.tools_used
```

#### Behavior Test Spec

```yaml
# tests/ai/episode_7599436d.yaml
episode_id: 7599436d-f3cc-4146-ad30-8efd3187a5ae
created_at: 2025-11-14T01:23:45Z
failure_type: incorrect_model_routing

input:
  messages:
    - role: user
      content: "What's 2 + 2?"

expected:
  model_used: "granite-local"
  cost: 0.0
  tools_used: []
  response_contains:
    - "4"
  response_not_contains:
    - "Let me execute code"

actual:
  model_used: "claude-opus"
  cost: 0.03
  failure_reason: "Used expensive cloud model for trivial arithmetic"

fix:
  rule_added: "Route basic arithmetic (patterns: \\d+\\s*[+\\-*/]\\s*\\d+) to granite-local"
  confidence: 0.85
  test_created: "tests/test_routing_simple_math.py"
```

### Running AI Tests

```bash
# Run all regression tests
pytest tests/ai/ -v

# Check specific episode
pytest tests/ai/episode_7599436d.yaml
```

## Dataset Export for Fine-Tuning

While Kai doesn't fine-tune models today, the JSONL memory format is **ready for future fine-tuning**:

### Export Training Data

```bash
# Export all successful episodes as training pairs
python scripts/export_training_data.py \
  --user-id default \
  --min-confidence 0.8 \
  --feedback positive \
  --output training_data.jsonl
```

Output format (compatible with OpenAI/Llama fine-tuning):

```jsonl
{"messages": [{"role": "user", "content": "Explain decorators"}, {"role": "assistant", "content": "Decorators are functions..."}], "metadata": {"episode_id": "...", "model": "granite-local", "cost": 0.0}}
{"messages": [{"role": "user", "content": "What's 2+2?"}, {"role": "assistant", "content": "4"}], "metadata": {...}}
```

### Future: LoRA Fine-Tuning

```bash
# Hypothetical future workflow
python scripts/train_lora.py \
  --base-model granite4:tiny-h \
  --training-data training_data.jsonl \
  --output models/kai-granite-v2.gguf
```

This would create a **Kai-specific local model** trained on your own usage patterns.

## Workflow Examples

### Example 1: Learning from Code Execution Mistake

**Episode**: User asks "What is Python?" → Kai unnecessarily calls code executor

```
1. LOG: Episode recorded with tools_used=["code_executor"], cost=0.0, latency=2300ms
   User feedback: /bad

2. REFLECT: 
   - What went wrong: "Used code execution for a definition question"
   - Root cause: "Complexity scorer incorrectly flagged as 'programming task'"
   - New rule: "Definition questions (what is X?) should not trigger code execution"
   - Test case: "Ensure 'What is X?' pattern routes to explanation, not code"

3. DISTILL (next nightly run):
   - Semantic rule added: "Never use code_executor for intent='definition'"
   - Checklist updated: "Before code exec, verify task requires computation/validation"
   - Test generated: tests/test_no_code_for_definitions.py

4. ADAPT (next similar query):
   - User: "What is asyncio?"
   - Orchestrator loads semantic rule via RAG
   - Routes to explanation mode, no code execution
   - Fast response, $0 cost
```

### Example 2: Prompt Evolution from User Feedback

**Pattern**: Users frequently give `/bad` feedback when responses are too verbose

```
1. LOG: 15 episodes in past week with negative feedback + tag "too-verbose"

2. REFLECT: Each episode notes "response could be more concise"

3. DISTILL (nightly):
   - Analyzes 15 reflections
   - Common theme: "Users prefer shorter answers"
   - Prompt suggestion: "Add 'be concise unless asked to elaborate' to system prompt"
   - Creates prompt variant: orchestrator_v3_concise

4. A/B TEST (future enhancement):
   - 50% of queries use v2, 50% use v3_concise
   - Track success rates and feedback
   - After 100 episodes: v3_concise has 0.92 success vs 0.84 for v2
   - Promote v3_concise to active, deprecate v2
```

## Summary

The self-improvement loop makes Kai a **learning system** rather than a static orchestrator:

- **No fine-tuning required**: Behavior evolves through memory, not weights
- **User-owned data**: All learning stored in human-readable JSONL
- **Traceable changes**: Every rule, prompt, and test links back to source episodes
- **Regression-safe**: Failed episodes become tests to prevent future mistakes
- **Confidence-driven**: Low-confidence knowledge naturally decays, high-confidence persists
- **Future-proof**: Memory format ready for fine-tuning when needed

**The result**: A system that gets better the more you use it, learning your preferences and domain specifics without requiring ML expertise.

