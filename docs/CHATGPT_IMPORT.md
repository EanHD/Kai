# ChatGPT Import System

Complete guide to importing your ChatGPT history into Kai's memory vault for permanent self-improvement.

## Overview

This system allows you to import your entire ChatGPT conversation history (exported as `conversations.json`) into Kai's memory vault. The imported data becomes permanent training signal that influences Kai's behavior through:

1. **Episodic Memory** - Every user/assistant turn stored as discrete episodes
2. **Semantic Memories** - Conversation summaries and key insights  
3. **Preferences** - Extracted user preferences ("prefers concise answers", "hates markdown")
4. **Rules/Checklists** - Explicit corrections ("never do X", "always do Y")
5. **Weighted Learning** - ChatGPT imports are weighted 5× higher in distillation sweeps

## How It Works

### Import Process

1. **Parse OpenAI Format** - Traverses the conversation tree structure in `conversations.json`
2. **Extract Episodes** - Each user→assistant turn becomes an episodic memory with `confidence=1.0` and `chatgpt_import` tag
3. **LLM Analysis** - For substantial conversations (>500 chars), Kai analyzes the content to extract:
   - Title and 2-sentence summary
   - User preferences (communication style, format preferences, etc.)
   - Explicit rules or corrections
4. **Permanent Storage** - All imported data is marked with `chatgpt_import` tag and **NEVER pruned**

### Self-Improvement Loop Integration

The imported data fortifies Kai's reflection/distillation system:

**During Nightly Distillation:**
- ChatGPT-imported memories are weighted **5× higher** than normal episodes
- Repeated corrections in ChatGPT history generate permanent rules
- Preference patterns are extracted and injected into future prompts

**In Every Response:**
- Top 5 learned preferences are dynamically injected into presenter system prompt
- Preferences from ChatGPT imports are prioritized (top 3 slots)
- Presenter includes this as "MUSCLE MEMORY" context

**Memory Protection:**
- ChatGPT imports have `confidence=1.0` (maximum)
- Tagged with `chatgpt_import` for identification
- **Prune operations skip all ChatGPT imports** (sacred data)

## Usage

### CLI Command

```bash
# Import from file
python -m src.cli.main --import-chatgpt path/to/conversations.json

# Or using the kai wrapper
./kai --import-chatgpt ~/Downloads/conversations.json
```

**Output:**
```
🚀 Starting ChatGPT Import from conversations.json
This will parse conversations and extract memories/preferences...

Found 847 conversations. Starting import...
Processing 0/847...
Processing 10/847...
...

✅ Import Complete!
   - Conversations: 847
   - Episodes: 3,241
   - Semantic Memories: 156
   - Preferences: 89
   - Rules: 34

Kai now remembers 847 conversations of your chaos.
```

### API Endpoint

**POST** `/v1/memory/import/chatgpt`

**Request:**
```bash
curl -X POST http://localhost:9000/v1/memory/import/chatgpt \
  -F "file=@conversations.json"
```

**Response:**
```json
{
  "status": "success",
  "message": "Imported 847 conversations · Kai now remembers your chaos",
  "stats": {
    "conversations": 847,
    "episodes": 3241,
    "semantic": 156,
    "preferences": 89,
    "rules": 34
  }
}
```

### Test Script

For quick testing without starting full CLI/API:

```bash
python test_chatgpt_import.py path/to/conversations.json
```

## Exporting from ChatGPT

1. Go to ChatGPT Settings → Data Controls
2. Click "Export data"
3. Wait for email with download link (can take 24 hours)
4. Download and extract ZIP
5. Find `conversations.json` in the archive

## Memory Structure

### Episodic Memories

Each user→assistant turn is stored in `data/memory/<user_id>/episodic.jsonl`:

```json
{
  "id": "uuid",
  "type": "episodic",
  "created_at": "2025-11-20T12:34:56Z",
  "confidence": 1.0,
  "ttl_days": 90,
  "tags": ["chatgpt_import", "historical"],
  "summary": "Imported from ChatGPT: How to debug Python",
  "payload": {
    "session_id": "chatgpt-abc123",
    "user": "How do I debug a segfault?",
    "assistant": "Here are several approaches...",
    "success": true
  }
}
```

### Preferences

Extracted preferences in `data/memory/<user_id>/preferences.jsonl`:

```json
{
  "id": "uuid",
  "type": "preference",
  "created_at": "2025-11-20T12:34:56Z",
  "confidence": 1.0,
  "tags": ["chatgpt_import", "preference"],
  "summary": "Preference: prefers concise answers without fluff",
  "payload": {
    "preference": "prefers concise answers without fluff",
    "source": "chatgpt_import"
  }
}
```

### Rules/Checklists

Rules extracted from corrections in `data/memory/<user_id>/checklists.jsonl`:

```json
{
  "id": "uuid",
  "type": "checklist",
  "created_at": "2025-11-20T12:34:56Z",
  "confidence": 1.0,
  "tags": ["chatgpt_import", "rule"],
  "summary": "Rule: never use passive voice in code examples",
  "payload": {
    "rule": "never use passive voice in code examples",
    "source": "chatgpt_import"
  }
}
```

## Distillation Weighting

In `src/agents/reflection_agent.py`, the distillation sweep applies 5× weight:

```python
# Check if from ChatGPT import
is_chatgpt = "chatgpt_import" in tags
weight = 5 if is_chatgpt else 1

# Add weighted copies for analysis
for _ in range(weight):
    weighted_summaries.append(summary_text)
```

This ensures patterns from your ChatGPT history dominate the learning process.

## Prompt Injection

In `src/core/presenters/granite_presenter.py`, the presenter loads top 5 preferences:

```python
def _get_learned_preferences(self) -> str:
    """Extract top 5 learned preferences from memory vault."""
    # Get all preferences, prioritize ChatGPT imports
    all_prefs = self.memory_vault.list(mtype="preference", limit=50)
    
    chatgpt_prefs = [p for p in all_prefs if "chatgpt_import" in p.get("tags", [])]
    other_prefs = [p for p in all_prefs if "chatgpt_import" not in p.get("tags", [])]
    
    # Take top 3 from ChatGPT, top 2 from others
    top_prefs = chatgpt_prefs[:3] + other_prefs[:2]
```

These are injected into every system prompt:

```
MUSCLE MEMORY (from past interactions):
- prefers concise answers without fluff
- hates markdown tables
- loves sarcasm and wit
- always wants code examples
- never wants explanations of basic concepts
```

## Verification

Check what was imported:

```bash
# List all ChatGPT imports
python -m src.cli.main
> /mem list episodic

# Export to Markdown for review
> /mem export data/chatgpt_review.md
```

Or query the vault directly in Python:

```python
from src.storage.memory_vault import MemoryVault

vault = MemoryVault(user_id="your_user_id")

# Count imports
imports = [m for m in vault.list() if "chatgpt_import" in m.get("tags", [])]
print(f"Total ChatGPT imports: {len(imports)}")

# Get preferences
prefs = vault.list(mtype="preference", tag="chatgpt_import")
for pref in prefs:
    print(pref["payload"]["preference"])
```

## Performance

- **Import Speed**: ~100 conversations/second (analysis is the bottleneck)
- **Storage**: ~1KB per conversation on average
- **Memory Impact**: Preferences cached after first load (no repeated file I/O)
- **LLM Calls**: 1 analysis per substantial conversation (>500 chars)

## Troubleshooting

**Import Fails with JSON Error:**
- Verify the file is valid JSON: `jq . conversations.json > /dev/null`
- Check it's from ChatGPT export (has `mapping` structure)

**No Preferences Extracted:**
- Conversations may be too short (<500 chars triggers analysis)
- LLM analysis may have failed (check logs with `--debug`)

**Preferences Not Showing in Responses:**
- Clear presenter cache: restart Kai
- Verify imports exist: `/mem list preference`
- Check orchestrator has memory_vault injected

**Import Successful But No Learning Effect:**
- Run distillation manually: `python scripts/nightly_maintenance.py`
- Check reflection agent logs for errors
- Verify preferences are being loaded in presenter

## Architecture

```
conversations.json
        ↓
ChatGPTImporter.import_file()
        ↓
    Parse tree structure (mapping → current_node traversal)
        ↓
    For each turn:
        ├─→ MemoryVault.add_episode() → episodic.jsonl
        └─→ (if substantial) LLM analysis
                ├─→ Extract summary → semantic.jsonl
                ├─→ Extract preferences → preferences.jsonl
                └─→ Extract rules → checklists.jsonl
        ↓
All stored with confidence=1.0, chatgpt_import tag
        ↓
Nightly: ReflectionAgent.distillation_sweep()
        ├─→ Weight chatgpt_import 5× higher
        └─→ Generate new rules/prompts
        ↓
Every Response: GranitePresenter._get_learned_preferences()
        ├─→ Load top 5 preferences (prioritize chatgpt_import)
        └─→ Inject into system prompt as MUSCLE MEMORY
```

## Benefits

1. **Zero Fine-Tuning** - No model weight changes, pure memory-based learning
2. **Instant Activation** - Preferences apply immediately after import
3. **Permanent Knowledge** - Never pruned, never degraded
4. **Transparent** - All memories human-readable in JSONL files
5. **Cumulative** - Combines with ongoing Kai usage for continuous improvement
6. **Portable** - Memory vault can be backed up and restored

## Limitations

- **Analysis Quality** - Depends on local LLM's ability to extract patterns
- **Context Window** - Only analyzes first 4000 chars of long conversations
- **One-Time Process** - Re-importing overwrites existing data (no deduplication)
- **No Cross-User Learning** - Each user's vault is isolated

## Future Enhancements

- Incremental import (only new conversations)
- Multi-source import (Claude, Gemini, etc.)
- Automated pattern detection without LLM analysis
- Preference conflict resolution
- User feedback loop for preference validation

## Related Files

- `src/tools/chatgpt_importer.py` - Import logic
- `src/storage/memory_vault.py` - Storage backend
- `src/agents/reflection_agent.py` - Distillation with weighting
- `src/core/presenters/granite_presenter.py` - Preference injection
- `src/api/handlers/memory_import.py` - API endpoint
- `test_chatgpt_import.py` - Standalone test script

