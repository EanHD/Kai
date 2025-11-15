# Quick Start

Get Kai running in 5 minutes with automatic setup.

## Prerequisites

- **Python 3.11+** - Check: `python3 --version`
- **Docker** - For code execution ([install](https://docs.docker.com/get-docker/))
- **Ollama** - For local models ([install](https://ollama.ai))

## Installation

```bash
# 1. Install dependencies
uv sync

# 2. Pull local model
ollama pull granite4:tiny-h

# 3. Setup environment
cp .env.template .env

# 4. Install tool dependencies
pip install duckduckgo-search
```

**Optional**: Add `OPENROUTER_API_KEY` to `.env` for external models (Claude, GPT)

## Run Kai

### Interactive CLI (Recommended)

```bash
./kai
```

**Auto-starts for you**:
- ✅ Ollama (local model)
- ✅ Docker (code execution)
- ✅ Web search tools
- ✅ Background learning

### API Server (OpenAI-compatible)

```bash
uv run python main.py
# Visit: http://localhost:9000/docs
```

## Quick Test

```
You: What's the capital of France?
```

```
You: Calculate: 3400mAh at 3.6V = how many Wh?
```

```
You: Search for Panasonic NCR18650B specs and calculate range at 25Wh/mile
```

## How It Works

```
Your Query
    ↓
Granite Analyzer → Creates plan (tools needed?)
    ↓
Executor → Runs web search, code execution, etc.
    ↓
Granite Presenter → Natural language answer
    ↓
Reflection → Learns from interaction (background)
```

## Tools Available

| Tool | What It Does | Auto-Starts |
|------|--------------|-------------|
| `web_search` | DuckDuckGo search | ✅ Yes |
| `code_exec` | Safe Python sandbox | ✅ Yes (Docker) |
| `rag` | Personal memory | ✅ Yes |
| `sentiment` | Emotional tone | ✅ Yes |

## Commands

In CLI:
- `/cost` - Check spending
- `/mem list` - Show memories
- `/help` - All commands
- `quit` - Exit

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Ollama not found | Install from https://ollama.ai |
| Docker not running | Start Docker Desktop or `systemctl start docker` |
| Slow first query | Normal - model loads once (then fast) |

**Still stuck?** → [docs/troubleshooting.md](docs/troubleshooting.md)

## Advanced

- **Configuration**: [docs/CONFIGURATION.md](docs/CONFIGURATION.md)
- **Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)  
- **Self-Learning**: [docs/SELF_IMPROVEMENT_LOOP.md](docs/SELF_IMPROVEMENT_LOOP.md)
- **API Docs**: [docs/api.md](docs/api.md)

## Cost Control

- **Local (Granite)**: $0 - always tries first
- **External (Claude/GPT)**: Set limits in `.env`
  - Default: $1 soft cap
  - Check: `./kai --cost`
