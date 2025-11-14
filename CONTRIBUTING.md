# Contributing to Kai

Thank you for your interest in contributing to Kai!

## Development Setup

```bash
# Clone repository
git clone <repository-url>
cd kai

# Install dependencies with development tools
uv sync

# Install Ollama for testing
ollama pull granite4:tiny-h
ollama serve
```

## Project Structure

```
kai/
├── src/
│   ├── api/          # FastAPI OpenAI-compatible endpoints
│   ├── cli/          # Interactive CLI interface
│   ├── core/         # Orchestrator, LLM connectors, routing
│   ├── agents/       # Reflection agent for self-improvement
│   ├── storage/      # Memory vault, SQLite, vector stores
│   ├── tools/        # Web search, code executor, memory tools
│   ├── models/       # Data models
│   └── lib/          # Config, logging, utilities
├── tests/            # Unit and integration tests
├── scripts/          # Maintenance scripts
├── config/           # YAML configuration files
├── docs/             # Documentation
└── examples/         # Usage examples
```

## Code Style

We use **Ruff** for linting and formatting:

```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_orchestrator.py

# Run specific test
pytest tests/test_orchestrator.py::test_model_routing
```

## Making Changes

1. **Create a branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes:**
   - Write clean, well-documented code
   - Add tests for new functionality
   - Update documentation if needed

3. **Test your changes:**
   ```bash
   pytest
   ruff check .
   ```

4. **Commit with clear messages:**
   ```bash
   git commit -m "Add feature: description of what you added"
   ```

5. **Push and create pull request:**
   ```bash
   git push origin feature/your-feature-name
   ```

## Architecture Overview

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design details.

**Key concepts:**

- **Orchestrator**: Routes queries to appropriate models based on complexity/cost
- **Memory Vault**: File-based JSONL storage for user-owned data
- **Reflection Agent**: Learns from interactions without fine-tuning
- **Tools**: Web search, code execution, memory storage

## Adding New Features

### Adding a New Tool

1. Create tool class in `src/tools/`:
   ```python
   from src.tools.base import BaseTool
   
   class MyTool(BaseTool):
       name = "my_tool"
       description = "What this tool does"
       
       async def execute(self, **kwargs):
           # Implementation
           return result
   ```

2. Register in `config/tools.yaml`:
   ```yaml
   tools:
     - name: my_tool
       enabled: true
       config:
         param: value
   ```

3. Add tests in `tests/tools/test_my_tool.py`

### Adding a New LLM Provider

1. Create provider in `src/core/providers/`:
   ```python
   from src.core.llm_connector import LLMConnector, Message
   
   class MyProvider(LLMConnector):
       async def generate(self, messages: List[Message], **kwargs):
           # Implementation
           pass
   ```

2. Update `src/lib/config.py` to load new provider

3. Add model config in `config/models.yaml`

### Adding Memory Types

See [docs/SELF_IMPROVEMENT_LOOP.md](docs/SELF_IMPROVEMENT_LOOP.md) for memory schema details.

1. Add type to `src/storage/memory_vault.py`:
   ```python
   MEMORY_TYPES = {
       "my_type": "my_type.jsonl",
       # ...
   }
   ```

2. Document schema in `docs/SELF_IMPROVEMENT_LOOP.md`

## Documentation

Update relevant docs when adding features:

- **README.md**: High-level overview and features
- **QUICKSTART.md**: Getting started guide
- **docs/ARCHITECTURE.md**: System design changes
- **docs/SELF_IMPROVEMENT_LOOP.md**: Memory/learning features
- **docs/api.md**: API endpoint changes

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md (if exists)
3. Create git tag: `git tag v1.x.x`
4. Push tag: `git push origin v1.x.x`

## Code Review Guidelines

**What we look for:**

- ✅ Clear, readable code
- ✅ Comprehensive tests
- ✅ Updated documentation
- ✅ No breaking changes (or clearly documented)
- ✅ Follows existing patterns and conventions
- ✅ Performance considerations (especially for LLM calls)

**What to avoid:**

- ❌ Hardcoded credentials or API keys
- ❌ Unnecessary dependencies
- ❌ Breaking existing functionality
- ❌ Untested code
- ❌ Poor error handling

## Getting Help

- **Architecture questions**: See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Memory system**: See [docs/SELF_IMPROVEMENT_LOOP.md](docs/SELF_IMPROVEMENT_LOOP.md)
- **Troubleshooting**: See [docs/troubleshooting.md](docs/troubleshooting.md)
- **Issues**: Check existing GitHub issues or create a new one

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

