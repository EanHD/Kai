# Kai - AI Backend

Intelligent LLM orchestrator with local-first architecture, tool integration, and cost-aware routing.

## Features

- 🤖 **Smart Routing**: Auto-routes queries to local (Ollama) or cloud (OpenRouter) models
- 🧠 **Memory**: RAG-based personal memory with encryption
- 🔍 **Web Search**: DuckDuckGo integration
- 🐍 **Code Execution**: Sandboxed Python in Docker
- 💰 **Cost Control**: Soft caps and automatic fallbacks
- 🎭 **Adaptive Responses**: Adjusts tone based on context
- 📡 **OpenAI-Compatible API**: Drop-in replacement

## Quick Start

```bash
# Install
./install.sh

# Run (dev mode with logs)
./dev.sh

# Or production mode (background)
./prod.sh
```

**API**: http://localhost:9000  
**Docs**: http://localhost:9000/docs

## Configuration

### Environment (`.env`)

```bash
OLLAMA_BASE_URL=http://localhost:11434
OPENROUTER_API_KEY=your_key          # Optional
ENCRYPTION_KEY=your_32_byte_key      # Required for memory
MONTHLY_COST_CAP=3.0                 # USD
```

### Models (`config/models.yaml`)

```yaml
models:
  - model_id: qwen-3b-instruct       # Local (free)
    model_name: qwen2.5:3b-instruct-q5_K_M
    provider: ollama
    
  - model_id: grok-fast              # Cloud (cheap)
    model_name: x-ai/grok-4-fast
    provider: openrouter
```

### Tools (`config/tools.yaml`)

```yaml
tools:
  web_search:
    enabled: true
  code_execution:
    enabled: true
  rag:
    enabled: true
```

## API Usage

```bash
# Simple request
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'

# With streaming
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [...], "stream": true}'
```

```python
# Python (OpenAI client)
from openai import OpenAI
client = OpenAI(base_url="http://localhost:9000/v1", api_key="unused")
response = client.chat.completions.create(
    model="qwen-3b-instruct",
    messages=[{"role": "user", "content": "Hello"}]
)
```

## Project Structure

```
kai/
├── main.py              # API entry point
├── config/              # YAML configs
├── src/
│   ├── core/            # Orchestrator, routing, cost tracking
│   ├── tools/           # Web search, code exec, RAG
│   ├── storage/         # Memory vault
│   └── lib/             # Utilities
├── dev.sh               # Dev mode launcher
├── prod.sh              # Production launcher
└── install.sh           # Setup script
```

## Hardware Requirements

- **GPU**: 4GB+ VRAM for local models (1650 Super works)
- **RAM**: 8GB+ recommended
- **Storage**: ~5GB for models

## License

MIT
