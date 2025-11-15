# Memory Integration TODO

## Current State
- Conversation messages ARE being saved to SQLite via `conversation_service`
- Memory vault IS logging episodes to file-based storage
- BUT: Orchestrator doesn't retrieve or pass conversation history to the LLM
- Result: Kai can't actually "remember" previous messages in the conversation

## What Needs to be Fixed

### 1. Pass Conversation History to Presenter
**File**: `src/core/orchestrator.py`

The orchestrator needs to:
```python
# In process_query method, before calling presenter.finalize():

# Get recent conversation history (last 10 messages or so)
conversation_history = []
if hasattr(self, 'conversation_service') and self.conversation_service:
    messages = self.conversation_service.get_messages(
        conversation.session_id, 
        limit=10
    )
    conversation_history = messages

# Pass to presenter
final_output = await self.presenter.finalize(
    original_query=query_text,
    plan=plan.to_dict(),
    tool_results=execution_results["tool_results"],
    specialist_results=execution_results["specialist_results"],
    conversation_history=conversation_history,  # NEW
)
```

### 2. Update Presenter to Use History
**File**: `src/core/presenters/granite_presenter.py`

```python
async def finalize(
    self,
    original_query: str,
    plan: dict[str, Any],
    tool_results: dict[str, Any],
    specialist_results: dict[str, Any],
    conversation_history: list[dict[str, Any]] = None,  # NEW
    style_profile: str = "kai_default",
) -> FinalizationOutput:
```

Then include conversation_history in the finalization_input that goes to the LLM.

### 3. Inject Conversation Service into Orchestrator
**File**: `src/cli/main.py`

```python
# When creating orchestrator:
self.orchestrator = Orchestrator(
    local_connector=self.local_connector,
    external_connectors=self.external_connectors,
    tools=self.tools,
    cost_limit=cost_limit,
)
# Add after creation:
self.orchestrator.conversation_service = self.conversation_service
```

**File**: `src/api/server.py` (or wherever API orchestrator is created)
Do the same for API consistency.

### 4. Update Presenter System Prompt
Once conversation history is working, update `PRESENTER_SYSTEM_PROMPT` to:
- Remove the "limitations" section about not seeing previous messages
- Add guidance on using conversation_history to maintain context
- Make it clear Kai can reference earlier parts of the conversation

## Testing After Implementation

1. **Basic Memory Test**:
   ```
   User: "Remember that my favorite color is blue"
   Kai: [acknowledges]
   User: "What's my favorite color?"
   Kai: "Blue" (should work from conversation history)
   ```

2. **Multi-turn Context**:
   ```
   User: "I asked you about days a week from today earlier"
   Kai: [should reference the earlier question about November 22]
   ```

3. **API Consistency**:
   - Test same conversation via API endpoints
   - Should maintain context across API calls with same session_id

## Priority
**HIGH** - This is core functionality that users expect from an AI assistant.

## Estimated Effort
- Small code changes (1-2 hours)
- Testing and validation (1 hour)
- Total: ~3 hours

## Related Files
- `src/core/orchestrator.py` - Main orchestration logic
- `src/core/presenters/granite_presenter.py` - Response generation
- `src/cli/main.py` - CLI interface
- `src/api/adapter.py` - API adapter
- `src/core/conversation_service.py` - Already working correctly
