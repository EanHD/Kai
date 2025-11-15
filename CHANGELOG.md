# Changelog

All notable changes to the KAI Assistant project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-11-15

### 🚀 Major Architecture Improvements

#### Changed
- **Model Role Separation**: External models (Grok/Claude) now ONLY used for JSON planning, never for user-facing text
- **Presentation Layer**: Local model (Granite/Llama) now handles ALL user-facing responses
- **Cost Optimization**: 99% cost reduction by using free local model for presentation (~100 tokens to Grok vs full responses)
- **Privacy Enhancement**: User-facing responses never sent to cloud APIs, only structured planning data
- **Offline Capability**: Improved graceful degradation when external APIs unavailable

#### Fixed
- **Granite Presenter**: Simplified prompt template for better JSON formatting reliability
- **Citation Support**: Fixed citation formatting in local model responses [1], (1)
- **Web Search Integration**: Enhanced Perplexity-style search with Tavily AI, Brave Search, and DuckDuckGo fallback
- **Error Handling**: Better fallback behavior when external models unavailable
- **Model Configuration**: Clarified model roles in `models.yaml` with inline documentation

#### Added
- **Hybrid Architecture**: Intelligent model routing (Grok for planning, Granite for presentation)
- **Multi-Source Web Search**: Integrated Tavily AI for Perplexity-like search capabilities
- **Enhanced Logging**: Better visibility into which models are used for which tasks
- **Configuration Comments**: Detailed inline documentation in `models.yaml`

#### Technical Details
- Modified `src/core/orchestrator.py` to enforce local-only presentation
- Enhanced `src/core/presenters/granite_presenter.py` with simplified JSON prompts
- Upgraded `src/tools/web_search.py` with multi-provider fallback system
- Updated `config/models.yaml` with role-based model documentation

## [1.0.0] - 2024-11-15

### 🎉 Initial Production Release

#### Added
- **Core Orchestration**: Multi-model LLM orchestrator with cost-aware routing
- **Tool Integration**: Code execution, web search, RAG, sentiment analysis
- **Dual Interfaces**: CLI and FastAPI-compatible OpenAI endpoint
- **Cost Tracking**: Accurate token and cost tracking with budget enforcement
- **Query Analysis**: Automatic complexity detection and capability matching
- **Plan Generation**: Structured execution plans with tool orchestration
- **Safety Checks**: Sanity checking and validation for all calculations
- **Source Awareness**: Unified architecture supporting both CLI and API modes
- **Production Monitoring**: Structured logging for query types, tools, models, and costs
- **Deployment Tools**: Setup script, health check, and Docker Compose configuration

#### Testing
- **Comprehensive Test Suite**: 148 tests across 6 categories
  - Static Analysis: 8/8 (100%)
  - Unit Tests: 43/43 (100%)
  - Regression Tests: 9/10 (90%)
  - Integration Tests: ~68/75 (91%)
  - Production Validation: 9/9 (100%)
  - Stress Tests: 3/3 (100%)
- **Overall Pass Rate**: 95%

#### Performance
- Simple queries: 2-3 seconds
- Complex queries: 10-20 seconds
- Concurrent requests: 20+ supported
- Memory usage: ~120MB baseline

#### Bug Fixes During Development
1. **Battery Calculation Accuracy** (Critical)
   - Fixed: Mental math fallback causing 5x errors in battery energy calculations
   - Solution: Enhanced query analyzer + improved fallback plan generation
   - Impact: Now routes correctly to code execution for all calculations

2. **Provider Initialization** (High)
   - Fixed: Inconsistent provider initialization patterns across test suites
   - Solution: Standardized to use `model_config` dict pattern
   - Impact: All integration tests now use correct initialization

3. **CostTracker API** (High)
   - Fixed: Method name mismatches (`track_query_cost` vs `track_query`)
   - Solution: Updated all calls to use `calculate_cost()` + `track_query()`
   - Impact: Cost tracking now accurate across all test scenarios

4. **Plan Serialization** (Medium)
   - Fixed: Plan objects not serializable due to Pydantic BaseModel
   - Solution: Converted to dataclasses with `to_dict()` methods
   - Impact: Plans can now be properly serialized for storage/transmission

5. **Async Event Loop** (Medium)
   - Fixed: "Event loop is closed" errors in sequential test runs
   - Solution: Changed production test fixtures from module to function scope
   - Impact: Tests run reliably in sequence without connection issues

6. **Battery Pack Notation Parsing** (Medium)
   - Fixed: "14S5P" notation not properly parsed by generic_math task
   - Solution: Added regex parsing in code_exec_wrapper with auto-routing
   - Impact: Battery calculations now work even when LLM plan generation fails

7. **Import Path Issues** (Low)
   - Fixed: sys.path configuration missing in several test files
   - Solution: Added consistent sys.path.insert() pattern
   - Impact: All tests can import src modules correctly

### Known Limitations
- LLM plan generation can occasionally produce invalid JSON (fallback handles gracefully)
- Web search requires Brave API key (optional, system works without it)
- Code execution requires Docker (graceful degradation without it)

### Dependencies
- Python 3.11+
- Ollama (local LLM serving)
- OpenRouter (external model access)
- Docker (optional, for code execution)
- uv (package management)

### Configuration
- `.env` file for API keys
- `config/models.yaml` for model configurations
- `config/tools.yaml` for tool settings
- `config/api.yaml` for API server settings

---

## [Unreleased]

### Planned
- Conversation memory across sessions
- Advanced RAG with vector stores
- Multi-turn dialogue optimization
- Custom tool plugin system
- Web UI dashboard
- Prometheus metrics export

---

[1.0.0]: https://github.com/EanHD/kai/releases/tag/v1.0.0
