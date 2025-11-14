# Configuration Guide

Kai uses YAML configuration files in the `config/` directory and environment variables for runtime settings.

## Environment Variables

Create a `.env` file from `.env.template`:

```bash
cp .env.template .env
```

### Core Settings

```bash
# LLM Providers
OLLAMA_BASE_URL=http://localhost:11434
OPENROUTER_API_KEY=your_api_key_here  # Optional, for cloud models

# Storage
SQLITE_DB_PATH=./data/kai.db
VECTOR_DB_PATH=./data/lancedb
MEMORY_VAULT_DIR=./data/memory  # User-owned JSONL memory files

# Encryption (for personal memory storage)
ENCRYPTION_KEY=your_32_byte_encryption_key_here

# Cost Control
DEFAULT_COST_LIMIT=1.0          # Max spend per session ($)
SOFT_CAP_THRESHOLD=0.8          # Fallback to cheap models at 80%

# Embedding Model (for RAG/semantic search)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### API Server Settings

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=9000
API_RELOAD=false  # Set to true for development
```

## Configuration Files

### config/models.yaml

Defines available LLM models and their capabilities.

```yaml
models:
  # Local model (Ollama)
  - model_id: granite-local
    model_name: granite4:tiny-h
    provider: ollama
    enabled: true
    capabilities:
      - conversation
      - simple_reasoning
      - simple_code
    context_window: 4096
    cost_per_1k_input: 0.0
    cost_per_1k_output: 0.0

  # Cloud model (OpenRouter)
  - model_id: claude-opus
    model_name: anthropic/claude-4-opus
    provider: openrouter
    enabled: true
    capabilities:
      - conversation
      - complex_reasoning
      - coding
      - long_context
    context_window: 200000
    cost_per_1k_input: 0.015
    cost_per_1k_output: 0.075

  - model_id: claude-sonnet
    model_name: anthropic/claude-4-sonnet
    provider: openrouter
    enabled: true
    capabilities:
      - conversation
      - complex_reasoning
      - coding
    context_window: 200000
    cost_per_1k_input: 0.003
    cost_per_1k_output: 0.015
```

**Fields:**

- `model_id`: Internal identifier
- `model_name`: Provider-specific model name
- `provider`: `ollama` or `openrouter`
- `enabled`: Whether model is available
- `capabilities`: What the model can do (used for routing)
- `context_window`: Maximum tokens
- `cost_per_1k_input/output`: Pricing (for cost tracking)

### config/capability_specs.yaml

Defines routing rules based on query complexity and required capabilities.

```yaml
capability_specs:
  # Simple queries → local model
  - name: simple_query
    required_capabilities:
      - conversation
    complexity_threshold: 0.3
    preferred_provider: ollama

  # Math/code → either local or cloud
  - name: coding_task
    required_capabilities:
      - coding
    complexity_threshold: 0.5
    preferred_provider: openrouter

  # Complex reasoning → cloud model
  - name: complex_reasoning
    required_capabilities:
      - complex_reasoning
    complexity_threshold: 0.7
    preferred_provider: openrouter
```

**How routing works:**

1. Orchestrator analyzes query complexity (0.0-1.0)
2. Matches required capabilities
3. Selects cheapest model meeting requirements
4. Falls back if cost cap exceeded

### config/api.yaml

API server configuration and model aliases (for OpenAI compatibility).

```yaml
server:
  host: 0.0.0.0
  port: 9000
  reload: false

# Map OpenAI model names to Kai models
model_aliases:
  gpt-4: claude-opus
  gpt-4-turbo: claude-sonnet
  gpt-3.5-turbo: granite-local

streaming:
  enabled: true
  chunk_size: 512
```

**Model aliases** allow OpenAI client code to work without changes:

```python
# This works with Kai API
client.chat.completions.create(
    model="gpt-4",  # Maps to claude-opus
    messages=[...]
)
```

### config/tools.yaml

Tool configuration (web search, code execution, memory storage).

```yaml
tools:
  # Web search via DuckDuckGo
  - name: web_search
    enabled: true
    description: "Search the web for current information"
    config:
      max_results: 5
      timeout: 10

  # Safe code execution
  - name: code_executor
    enabled: true
    description: "Execute Python code in sandboxed environment"
    config:
      docker_image: kai-python-sandbox:latest
      timeout: 30
      memory_limit: 512m
      use_gvisor: false  # Set to true for extra security

  # Personal memory storage
  - name: memory_store
    enabled: true
    description: "Store and retrieve personal information"
    config:
      encryption_enabled: true

  # Sentiment analysis
  - name: sentiment_analyzer
    enabled: true
    description: "Analyze emotional tone of messages"
    config:
      threshold: 0.5  # Confidence threshold
```

**Disabling tools:**

Set `enabled: false` to disable a tool without removing it.

## Runtime Configuration

### Cost Limits

Set in `.env` or override per session:

```python
# API request with custom cost limit
{
  "model": "granite-local",
  "messages": [...],
  "metadata": {
    "cost_limit": 0.50  # Override default
  }
}
```

**Cost cap behavior:**

- **Below soft cap (80%)**: Use optimal model
- **Above soft cap**: Switch to cheaper alternatives
- **At hard cap (100%)**: Local models only
- **Manual override**: Can bypass for critical queries

### Memory Configuration

Memory vault stores typed memories in `data/memory/<user_id>/`:

```bash
# Memory types and retention
episodic.jsonl         # Conversations (90 days TTL)
reflections.jsonl      # AI reflections (180 days)
semantic.jsonl         # Rules/knowledge (indefinite)
prompts.jsonl          # Evolved prompts (indefinite)
checklists.jsonl       # Procedures (indefinite)
preferences.jsonl      # User preferences (indefinite)
bugs.jsonl             # Failure records (indefinite)
```

**Pruning:** Run `python scripts/nightly_maintenance.py` to clean old memories.

**Reflection Behavior:**
- **Always-On**: Reflection runs automatically after every interaction (CLI and API)
- **Verbose Mode**: Use `--reflect` flag in CLI to see reflection process in real-time
- **API Server**: Reflection happens in background without blocking responses
- **Storage**: Reflections stored in `reflections.jsonl` with 180-day TTL

### Logging

Configure in `src/lib/logger.py` or via CLI:

```bash
# Debug mode (verbose logging)
./kai --debug

# Show reflection process (verbose mode)
./kai --reflect

# Normal mode (quiet, reflection runs silently)
./kai
```

**Log levels:**

- `DEBUG`: All details (development)
- `INFO`: Important events (default)
- `WARNING`: Issues that don't stop execution
- `ERROR`: Failures

## Advanced Configuration

### Custom Prompts

System prompts are evolving in the memory vault (`prompts.jsonl`). To manually add:

```jsonc
// data/memory/<user_id>/prompts.jsonl
{
  "type": "prompt",
  "id": "custom_orchestrator",
  "tags": ["orchestrator", "active"],
  "confidence": 0.9,
  "payload": {
    "version": "v3",
    "text": "You are Kai, an intelligent orchestrator. Your custom instructions..."
  }
}
```

### Docker Sandbox

Build custom sandbox image:

```bash
# Edit docker/Dockerfile to add Python packages
RUN pip install numpy pandas

# Rebuild
docker build -t kai-python-sandbox:latest -f docker/Dockerfile .
```

### Multiple Users

Each user gets their own memory vault:

```python
# Generate unique user ID
import uuid
user_id = str(uuid.uuid4())

# API request with user ID
{
  "model": "granite-local",
  "messages": [...],
  "metadata": {
    "user_id": "user-123"
  }
}
```

## Troubleshooting

**Models not loading:**

Check `config/models.yaml` syntax and ensure Ollama is running:

```bash
ollama list
ollama serve
```

**Cost tracking wrong:**

Update pricing in `config/models.yaml` to match current rates.

**Tools failing:**

Check `config/tools.yaml` and ensure dependencies are installed (Docker for code execution, etc.).

For more issues, see [troubleshooting.md](troubleshooting.md).

