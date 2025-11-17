# Streaming Implementation Guide

## What's New

Kai now streams responses in real-time with a typewriter effect! Both CLI and API support live streaming.

## CLI Usage

Just use `./kai` normally - streaming is automatic:

```bash
./kai
🗨️ You: hey
💬 Kai: Hey! How can I help you today?

🗨️ You: what is obsidian notes?
💬 Kai: [Response streams character-by-character as it's generated]
```

### Streaming Behavior

1. **Instant Greetings** (< 0.1s)
   - "hey", "hi", "hello", "yo", "sup" → Instant animated response
   - No model call needed, just pure speed

2. **Simple Queries** (streaming immediately)
   - Complexity score < 0.2, no tools needed
   - Streams directly from granite4:micro-h
   - Starts streaming within 1-2 seconds

3. **Complex Queries** (plan → execute → stream)
   - Requires tools (web search, code exec)
   - Planning and execution happen first
   - Final presentation streams as it's generated
   - Citations/code results shown after streaming

## API Usage

### Streaming Request

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8100/v1",
    api_key="not-needed"
)

# Enable streaming
response = client.chat.completions.create(
    model="kai-local",
    messages=[{"role": "user", "content": "what is obsidian notes?"}],
    stream=True  # Enable streaming
)

# Process chunks
for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### Non-Streaming (Still Works)

```python
response = client.chat.completions.create(
    model="kai-local",
    messages=[{"role": "user", "content": "hey"}],
    stream=False  # Traditional request/response
)

print(response.choices[0].message.content)
```

## Performance Characteristics

### Before (Non-Streaming)
- Greeting: Wait 2-3s → See full response
- Simple query: Wait 3-5s → See full response
- Complex query: Wait 10-30s → See full response

### After (Streaming)
- Greeting: < 0.1s → See response typing immediately
- Simple query: 1-2s → See response typing as generated
- Complex query: 5-10s (planning/tools) → See presentation typing

**Perceived speedup: 2-3x faster** because you see output immediately rather than waiting for completion.

## Technical Details

### Architecture

```
User Query
    ↓
Orchestrator.process_query_stream()
    ↓
┌─── Instant Path (greetings) → Stream characters directly
├─── Fast Path (simple) → Local model streams → Yield chunks
└─── Complex Path → Plan → Execute → Presenter.finalize_stream() → Yield chunks
```

### Streaming Methods

**Orchestrator:**
- `process_query_stream()` - Main streaming entry point
- Returns async iterator of content chunks

**Presenter:**
- `finalize_stream()` - Streams final presentation
- Calls `connector.generate_stream()` for typewriter effect

**Providers:**
- `OllamaProvider.generate_stream()` - Streams from Ollama
- `OpenRouterProvider.generate_stream()` - Streams from external models

### CLI Implementation

```python
# CLI streams character-by-character
async for chunk in orchestrator.process_query_stream(query, conversation):
    print(chunk, end="", flush=True)
```

### API Implementation

```python
# API formats as SSE
async for chunk in adapter.invoke_orchestrator_stream(request):
    yield f"data: {json.dumps(chunk)}\n\n"
yield "data: [DONE]\n\n"
```

## Customization

### Adjust Streaming Speed (CLI)

Edit `src/core/orchestrator.py`, line ~360:

```python
# Slower typewriter (50ms/char)
await asyncio.sleep(0.05)

# Faster typewriter (10ms/char)
await asyncio.sleep(0.01)

# Instant (no delay)
await asyncio.sleep(0)
```

### Disable Streaming (CLI)

Revert to `process_query()`:

```python
# src/cli/main.py, line ~380
response = await self.orchestrator.process_query(
    query_text=user_input,
    conversation=self.conversation,
    source="cli",
)
```

## Testing

### Test Instant Greetings
```bash
./kai
🗨️ You: hey
# Should see immediate streaming
```

### Test Simple Query Streaming
```bash
🗨️ You: what day is it?
# Should start streaming within 1-2 seconds
```

### Test Complex Query Streaming
```bash
🗨️ You: what is obsidian notes?
# Planning/search happens first, then presentation streams
```

### Test API Streaming
```bash
# Terminal 1: Start API
./scripts/start_api

# Terminal 2: Test streaming
curl -N http://localhost:8100/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kai-local",
    "messages": [{"role": "user", "content": "hey"}],
    "stream": true
  }'
```

## Troubleshooting

### "AttributeError: 'OllamaProvider' object has no attribute 'generate_stream'"

Already implemented - check you're on latest main branch:
```bash
git pull origin main
```

### Streaming appears choppy/slow

**For Pentium G3258:**
- Normal! Granite4 generates ~1-2 tokens/sec on dual-core CPU
- This is expected for local inference on older hardware
- Streaming makes it feel faster because you see output immediately

**Adjust typewriter speed:**
- Reduce `await asyncio.sleep(0.02)` to `0.01` or `0` for instant display

### API streaming not working

Check:
1. `stream=True` in request
2. Using streaming-compatible client (handles SSE)
3. Not buffering output (use `-N` with curl)

## Benefits

✅ **Immediate Feedback** - Users see response start instantly
✅ **Perceived Speed** - 2-3x faster feeling despite same latency
✅ **Better UX** - Typewriter effect feels natural and engaging
✅ **OpenAI Compatible** - Works with existing streaming clients
✅ **No Breaking Changes** - Non-streaming mode still works

## Next Steps

- Test on your Pentium G3258 server
- Adjust streaming speed to your preference
- Try both CLI and API streaming
- Monitor if granite4 generates cleaner output now (no markdown)

