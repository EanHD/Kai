# Quick Start

Get Kai running in under 5 minutes.

## Prerequisites

- **Python 3.11+**
- **Docker** (for code execution sandbox)
- **Ollama** (for local models)
- **OpenRouter API key** (optional, for cloud models)

## Installation

```bash
# 1. Clone repository
git clone <repository-url>
cd kai

# 2. Install dependencies (using uv - recommended)
uv sync

# Or with pip
pip install -e .

# 3. Set up Ollama
# Install from https://ollama.ai
ollama pull granite4:tiny-h
ollama serve

# 4. Configure environment
cp .env.template .env
# Edit .env with your settings (OPENROUTER_API_KEY is optional)

# 5. Build Docker sandbox (optional, for code execution)
docker build -t kai-python-sandbox:latest -f docker/Dockerfile .
```

## Usage

### CLI (Interactive Chat)

```bash
# Basic chat (reflection runs silently in background)
./kai

# Watch the learning process in real-time
./kai --reflect
```

**Example session:**

```
You: What's 2 + 2?
Kai: 4

🔮 Reflecting on this interaction...
✓ Reflection complete - learning stored

You: Remember my favorite color is blue
Kai: I've stored that you prefer blue.

You: /cost
💰 Cost Summary:
   Session Cost: $0.00 / $1.00
   Queries: 2
   Remaining: $1.00
   Status: ✓ 0% of budget used

You: /help
Available commands:
  /cost    - Show cost summary
  /mem     - Memory commands
  /good    - Mark last response as good
  /bad     - Mark last response as poor
  /help    - Show this help
  quit     - Exit
```

### API Server (OpenAI-compatible)

```bash
# Start API server (reflection runs automatically in background)
uv run python main.py

# Visit API docs
open http://localhost:9000/docs
```

**Example API call:**

```bash
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "granite-local",
    "messages": [{"role": "user", "content": "Explain Python decorators"}]
  }'
```

**Streaming:**

```bash
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "granite-local",
    "messages": [{"role": "user", "content": "Count to 5"}],
    "stream": true
  }'
```

**Using OpenAI Python client:**

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:9000/v1",
    api_key="not-needed"  # API key not required for local
)

response = client.chat.completions.create(
    model="granite-local",
    messages=[
        {"role": "user", "content": "What is RAG?"}
    ]
)

print(response.choices[0].message.content)
```

## Self-Improvement Mode

Enable Kai to learn from every interaction:

```bash
# 1. Run with reflection enabled
./kai --reflect

# 2. Chat normally - reflections auto-generated after each response

# 3. Set up nightly distillation (via cron)
# Analyzes recent episodes, generates rules/prompts/checklists
crontab -e

# Add this line (runs at 2 AM daily):
0 2 * * * cd /path/to/kai && python scripts/nightly_maintenance.py --user-id default
```

**Feedback commands:**

```bash
You: /good  # Boost confidence in last response
You: /bad   # Trigger deeper reflection on failure
```

## Configuration

### Model Selection

Edit `config/models.yaml` to add/remove models:

```yaml
models:
  - model_id: granite-local
    model_name: granite4:tiny-h
    provider: ollama
    enabled: true
    capabilities: [conversation, simple_reasoning]

  - model_id: claude-opus
    model_name: anthropic/claude-4-opus
    provider: openrouter
    enabled: true
    capabilities: [complex_reasoning, coding]
```

### API Aliases

Edit `config/api.yaml` for OpenAI-compatible model names:

```yaml
model_aliases:
  gpt-4: claude-opus
  gpt-3.5-turbo: granite-local
```

## Memory Management

```bash
# List memories
You: /mem list episodic
You: /mem list reflection

# Export memories to Markdown
You: /mem export memories.md

# Prune old/low-confidence memories
You: /mem prune
```

## Troubleshooting

**Ollama connection error:**

```bash
# Ensure Ollama is running
ollama serve

# Check models
ollama list
```

**Code execution fails:**

```bash
# Build Docker image
docker build -t kai-python-sandbox:latest -f docker/Dockerfile .

# Or disable code execution in config/tools.yaml
```

**High costs:**

```bash
# Check cost limits in .env
DEFAULT_COST_LIMIT=1.0  # Max spend per session
SOFT_CAP_THRESHOLD=0.8  # Fallback to cheap models at 80%

# Monitor in CLI
You: /cost
```

## Next Steps

- **Architecture**: See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Self-Improvement**: See [docs/SELF_IMPROVEMENT_LOOP.md](docs/SELF_IMPROVEMENT_LOOP.md)
- **API Reference**: See [docs/api.md](docs/api.md)
- **Deployment**: See [docs/deployment.md](docs/deployment.md)
- **Examples**: Check `examples/` directory for code samples

