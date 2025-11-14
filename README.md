# Kai - Intelligent LLM Orchestrator

**Kai** is an intelligent local-first LLM orchestrator with tool integration, adaptive response modes, and cost-aware model routing. It provides a conversational AI assistant that seamlessly combines local models (Ollama) with powerful cloud models (OpenRouter/Claude) while maintaining privacy and cost control.

**NEW**: OpenAI-compatible REST API on port 9000 — [See Quick Start →](QUICKSTART.md)

## Features

- 🌐 **OpenAI-Compatible API**: Drop-in replacement for OpenAI API with full chat completions + streaming support
- 🤖 **Intelligent Model Routing**: Automatically routes simple queries to fast local models and complex reasoning to powerful external models
- 🧠 **Self-Improving Memory**: Reflection agent learns from past interactions, distills patterns, and evolves knowledge over time
- 🔍 **Web Search Integration**: Grounded information retrieval with DuckDuckGo and Ollama fallback
- 🧠 **Personal Memory**: RAG-based personal information storage with encryption
- 🎭 **Adaptive Response Modes**: Automatically adjusts tone (concise/expert/advisor) based on context and emotion
- 🐍 **Safe Code Execution**: Sandboxed Python execution in Docker containers with gVisor support
- 💰 **Cost Control**: Soft caps, smart fallbacks, and detailed cost tracking
- 🔒 **Privacy-First**: Local-first architecture with encrypted storage
- 📊 **Comprehensive Metrics**: Response times, costs, tool usage tracking

## Quick Start

**Get running in 5 minutes** → [QUICKSTART.md](QUICKSTART.md)

```bash
# Install
uv sync
ollama pull granite4:tiny-h
cp .env.template .env

# Run CLI
./kai

# Run CLI with visible reflection (shows learning in real-time)
./kai --reflect

# Run API server (reflection always active in background)
uv run python main.py
```

## How Kai Improves Over Time

Kai doesn't fine-tune base models. Instead, it learns through a **closed self-improvement loop** that runs automatically in the background:

1. **Log Episodes** → Every conversation stored with metadata
2. **Reflect (Always-On)** → AI analyzes what worked/failed after each interaction
3. **Distill (Nightly)** → Synthesize patterns into rules/prompts
4. **Adapt** → Use evolved knowledge on next request

**No model weights change** — behavior evolves by updating prompts, rules, and checklists.

**Continuous Learning**: Reflection runs automatically in both CLI and API server. Use `./kai --reflect` to watch the learning process in real-time, or leave it silent in the background.

👉 **Full details:** [docs/SELF_IMPROVEMENT_LOOP.md](docs/SELF_IMPROVEMENT_LOOP.md)

## Quick Start (Expanded)

### Prerequisites

- Python 3.11+
- Docker (for code execution)
- Ollama (for local models)
- OpenRouter API key (optional, for external models)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd kai
   ```

2. **Install dependencies**:

   ```bash
   # Using uv (recommended)
   uv sync

   # Or with pip
   pip install -e .
   ```

3. **Set up Ollama**:
   ```bash
   # Install Ollama (https://ollama.ai)
   # Pull the local Granite model used by Kai
   ollama pull granite4:tiny-h
   ollama serve
   ```

4. **Configure environment**:
   ```bash
   cp .env.template .env
   # Edit .env with your settings
   ```

5. **Build Docker sandbox image** (optional, for code execution):
   ```bash
   docker build -t kai-python-sandbox:latest -f docker/Dockerfile .
   ```

### Usage

**Start interactive chat (CLI)**:

```bash
python -m src.cli.main

# With reflection enabled (learns from each interaction)
python -m src.cli.main --reflect
```

**Start the API server (FastAPI, OpenAI-compatible)**:

```bash
# Dev mode with reload
./scripts/start_api_dev

# Or production mode
./scripts/start_api
```

Once running, visit `http://localhost:9000/docs`.

**Test the API (non-streaming)**:

```bash
curl -s -X POST http://localhost:9000/v1/chat/completions \
   -H "Content-Type: application/json" \
   -d '{
      "model": "granite-local",
      "messages": [{"role": "user", "content": "What is 2+2?"}],
      "temperature": 0.3
   }' | python -m json.tool
```

**Python client example (OpenAI-compatible)**:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:9000/v1", api_key="not-needed")

resp = client.chat.completions.create(
      model="granite-local",
      messages=[{"role": "user", "content": "Explain RAG in one paragraph."}],
)
print(resp.choices[0].message.content)
```

### Memory Vault (user-owned data)

Kai stores **typed memories** in JSONL files under `data/memory/<user_id>/` so you can browse, export, and control your data. The **Reflection Agent** learns from past interactions to improve over time.

**Memory Types**: `episodic`, `reflection`, `semantic`, `prompt`, `checklist`, `preference`, `bug_fix`

**CLI commands:**

- `/mem help` — show commands
- `/mem list [type]` — list recent memories (optionally by type)
- `/mem export [path]` — export all memories to Markdown
- `/mem prune` — remove expired/low-confidence memories
- `/good` — mark last response as successful (boosts confidence)
- `/bad` — mark last response as poor (triggers deeper reflection)

**Enable reflection mode:**

```bash
./kai --reflect  # Auto-generates reflections after each episode
```

**Run nightly distillation sweep:**

```bash
python scripts/nightly_maintenance.py --user-id <user_id>
```

The sweep analyzes recent episodes, generates rules/prompts/checklists, and prunes old memories. Run via cron for continuous improvement.

**See detailed documentation:**

- [docs/SELF_IMPROVEMENT_LOOP.md](docs/SELF_IMPROVEMENT_LOOP.md) — Complete guide to how Kai learns
- [docs/MEMORY_VAULT.md](docs/MEMORY_VAULT.md) — Memory types and schemas
- [docs/REFLECTION_AGENT.md](docs/REFLECTION_AGENT.md) — Reflection and distillation workflows


**First Run**: You may see warnings about optional components:

- `No API key for OpenRouter` - External models disabled (local-only mode works fine)
- `sentence-transformers not installed` - Optional; install with `uv add sentence-transformers` for better semantic features
- `Image kai-python-sandbox:latest not found` - Build with `docker build -t kai-python-sandbox:latest -f docker/Dockerfile .` or it will use `python:3.11-slim`

**Example interactions**:

```
You: What's 1543 * 892?
🎓 Kai: Let me calculate that for you.

🔬 Code Execution:
   Output: 1376356

The result is 1,376,356.

You: Remember my sleep schedule is 11pm-7am
💬 Kai: I've stored your sleep schedule: 11pm-7am.

You: What time do I wake up?
💬 Kai: Based on what you told me, you wake up at 7am.
```

## Configuration

### Environment Variables

Create `.env` file from `.env.template`:

```bash
# LLM Providers
OLLAMA_BASE_URL=http://localhost:11434
OPENROUTER_API_KEY=your_api_key_here  # Optional

# Storage
SQLITE_DB_PATH=./data/kai.db
VECTOR_DB_PATH=./data/lancedb
ENCRYPTION_KEY=your_32_byte_encryption_key_here

# Cost Control
DEFAULT_COST_LIMIT=1.0
SOFT_CAP_THRESHOLD=0.8

# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Model Configuration

Edit `config/models.yaml`:

```yaml
models:
  - model_id: granite-local
    model_name: granite4:micro-h
    provider: ollama
    enabled: true
    capabilities: [conversation, simple_reasoning]
    context_window: 4096
    cost_per_1k_input: 0.0
    cost_per_1k_output: 0.0
    
  - model_id: claude-opus
    model_name: anthropic/claude-4-opus
    provider: openrouter
    enabled: true
    capabilities: [conversation, reasoning, analysis, code_generation]
    context_window: 200000
    cost_per_1k_input: 0.015
    cost_per_1k_output: 0.075
```

### Tool Configuration

Edit `config/tools.yaml`:

```yaml
tools:
  web_search:
    enabled: true
    provider: hybrid
    config:
      max_results: 5
      timeout_seconds: 10
      cache_ttl: 3600
      
  code_executor:
    enabled: true
    config:
      timeout_seconds: 30
      memory_limit: "128m"
      cpu_quota: 100000
      use_gvisor: true
      network_disabled: true
```

## Architecture

See `docs/ARCHITECTURE.md` for a full system diagram and request flow. Quick overview:

```
┌─────────────────────────────────────────┐
│            CLI Interface                │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│         Orchestrator                    │
│  ┌──────────────────────────────────┐   │
│  │   Query Analyzer                 │   │
│  │   - Complexity Detection         │   │
│  │   - Capability Requirements      │   │
│  │   - Sentiment Analysis           │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │   Model Router                   │   │
│  │   - Cost-aware Selection         │   │
│  │   - Fallback Strategies          │   │
│  └──────────────────────────────────┘   │
└─────────────┬───────────────────────────┘
              │
    ┌─────────┴──────────┐
    │                    │
┌───▼────┐          ┌────▼────┐
│ Ollama │          │OpenRouter│
│ Local  │          │  Cloud   │
└────────┘          └──────────┘
    │                    │
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │                    │
┌───▼────┐  ┌────▼────┐  ┌────▼────┐
│  Web   │  │ Memory  │  │  Code   │
│ Search │  │  Store  │  │Executor │
└────────┘  └─────────┘  └─────────┘
```

## Development

### Project Structure

```
kai/
├── src/
│   ├── cli/              # CLI interface
│   ├── core/             # Core orchestration logic
│   │   ├── orchestrator.py
│   │   ├── query_analyzer.py
│   │   ├── cost_tracker.py
│   │   └── providers/    # LLM provider implementations
│   ├── models/           # Data models
│   ├── tools/            # Tool implementations
│   ├── storage/          # Persistence layer
│   └── lib/              # Utilities
├── config/               # Configuration files
├── docker/               # Docker images
├── tests/                # Test suite
└── specs/                # Feature specifications
```

### Running Tests

```bash
# Run all tests (from repo root)
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_cost_tracker.py
```

### Code Quality

```bash
# Lint code
ruff check .

# Format code
ruff format .
```

## Response Modes

Kai automatically adjusts its response style based on context:

### 💬 Concise Mode
**When**: Simple queries, factual questions  
**Style**: 1-2 sentences, direct answers  
**Example**: "The capital of France is Paris."

### 🎓 Expert Mode
**When**: Complex queries, multi-step reasoning, tool usage  
**Style**: Structured breakdown with headings and details  
**Example**:
```
**Analysis**
The problem requires three steps:

1. Data collection
2. Statistical analysis
3. Recommendation generation

**Methodology**
...
```

### 🤝 Advisor Mode
**When**: Distressed/frustrated users, goal deviation detected  
**Style**: Supportive, protective guidance  
**Example**: "I understand this is challenging. Let me help you break this down into manageable steps..."

## Cost Management

Kai provides three-tier cost control:

1. **Soft Cap (80%)**: Switches to cheaper models automatically
2. **Hard Cap (100%)**: Local models only
3. **Manual Override**: Critical queries can bypass limits

Check costs at any time:
```
   You: /cost
   💰 Cost Summary:
      Session Cost: $0.0234 / $1.00
      Queries: 15
      Remaining: $0.9766
      Status: ✓ 2% of budget used
   ```

### Feedback (Optional)

The CLI supports lightweight feedback markers to help Kai learn from your preferences:

```bash
You: /good  # Mark last response as successful
You: /bad   # Mark last response as poor
```

These flags are stored with the corresponding `episode` and used during:
- Reflection analysis (what patterns lead to good/bad outcomes)
- Prompt evaluation (which prompt variants work better)
- Model routing decisions (which models perform best for specific tasks)

**API Usage**: Include feedback in your requests:
```json
{
  "messages": [...],
  "metadata": {
    "feedback": "positive"  // or "negative"
  }
}
```

### Memory Vault
```

## Privacy & Security

- **Local-First**: Ollama runs locally, no data leaves your machine unless using cloud models
- **Encrypted Storage**: Personal memories encrypted with AES-256
- **Sandboxed Execution**: Code runs in isolated Docker containers with gVisor
- **Access Controls**: User-level data isolation
- **Retention Policies**: Configurable data cleanup

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for common issues and solutions.

## Documentation

### Getting Started

- **[Quick Start](QUICKSTART.md)**: Get running in 5 minutes
- **[Contributing](CONTRIBUTING.md)**: Development setup and guidelines
- **[Configuration](docs/CONFIGURATION.md)**: Complete configuration reference

### Core Concepts

- **[Architecture](docs/ARCHITECTURE.md)**: System design and request flow
- **[Self-Improvement Loop](docs/SELF_IMPROVEMENT_LOOP.md)**: How Kai learns and evolves

### Reference

- **[API Documentation](docs/api.md)**: OpenAI-compatible API reference
- **[Deployment](docs/deployment.md)**: Production deployment guide
- **[Troubleshooting](docs/troubleshooting.md)**: Common issues and solutions

### Examples

Check the `examples/` directory for code samples:

- `examples/openai_client.py`: Using OpenAI Python client with Kai
- More examples coming soon

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup
- Code style guidelines
- Testing requirements
- Pull request process


## License

[License information]

## Acknowledgments

Built with:

- [LangGraph](https://github.com/langchain-ai/langgraph) for orchestration
- [Ollama](https://ollama.ai) for local models
- [OpenRouter](https://openrouter.ai) for cloud model access
- [LanceDB](https://lancedb.com) for vector storage
- [VADER](https://github.com/cjhutto/vaderSentiment) for sentiment analysis
