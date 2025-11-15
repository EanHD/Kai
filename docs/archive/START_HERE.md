# START HERE

## Quick Start (5 Minutes)

```bash
# 1. Install
uv sync
ollama pull granite4:tiny-h
pip install duckduckgo-search
cp .env.template .env

# 2. Run (auto-starts everything)
./kai
```

## What Just Happened?

✅ **Auto-started**:
- Ollama (local model)
- Docker (code execution)
- All 4 tools (web, code, memory, sentiment)

✅ **Ready to use**:
- Chat normally
- Tools execute automatically based on query
- Background learning enabled

## Try These

```
You: What's 2+2?
You: Calculate 3400mAh × 3.6V in Wh
You: Search for NCR18650B battery specs
```

## Documentation

- **Quick Setup**: [QUICKSTART.md](QUICKSTART.md)
- **All Docs**: [docs/README.md](docs/README.md)
- **Latest Changes**: [CHANGES_SUMMARY.md](CHANGES_SUMMARY.md)

## Need Help?

- **Not working?** → [docs/troubleshooting.md](docs/troubleshooting.md)
- **Want to configure?** → [docs/CONFIGURATION.md](docs/CONFIGURATION.md)
- **How does it work?** → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## One-Line Install + Run

```bash
uv sync && ollama pull granite4:tiny-h && pip install duckduckgo-search && cp .env.template .env && ./kai
```

That's it! 🚀
