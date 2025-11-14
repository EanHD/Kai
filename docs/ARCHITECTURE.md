# Kai Architecture

This document describes the high-level architecture of Kai, a local-first LLM orchestrator with intelligent routing, tool integration, and an OpenAI-compatible API.

## Request Flow

1. Client (CLI or API) sends a user message
2. Adapter prepares the request for the Orchestrator
3. Orchestrator analyzes the query (complexity, topic, required capabilities)
4. Orchestrator executes tools if needed (web search, code execution, memory)
5. Orchestrator chooses a model via intelligent routing
6. Connector calls the chosen model (Ollama for local, OpenRouter for cloud)
7. Orchestrator formats the final response and returns it

```
Client (CLI/API)
   │
   ▼
Adapter (CLI/API adapter)
   │
   ▼
Orchestrator
  ├─ Query Analyzer (complexity, topic shift, needs tools)
  ├─ Tool Runner (web_search, code_exec, memory)
  └─ Router (capability-spec guided, cost-aware)
   │
   ▼
Connectors
  ├─ Ollama (local)
  └─ OpenRouter (cloud)
```

## Intelligent Routing

Kai prefers local models when they can confidently handle the task:
- Uses YAML capability specs in `config/capability_specs.yaml`
- Considers complexity score, tool availability, and privacy preference
- Falls back to external models for complex reasoning or creative tasks

Key signals used:
- Complexity score (0.0–1.0)
- Topic shift detection (semantic embeddings)
- Required capabilities (web_search, code_exec, rag)
- Time-aware context filtering (30 minutes)

## Capability Specs

Example (granite4-micro):
```yaml
models:
  granite4-micro:
    routing_guidance:
      optimal_complexity_range: [0.0, 0.5]
      with_tools_range: [0.0, 0.65]
      confidence_multiplier_with_tools: 1.3
      prefer_over_external_when:
        - has_web_search: true
        - has_code_exec: true
        - complexity_below: 0.5
```

## OpenAI-Compatible API

- Endpoint: `/v1/chat/completions`
- Non-streaming and streaming (SSE, with chunked fallback today)
- Model mapping via `config/api.yaml` (e.g., `granite-local` → `ollama/granite4:tiny-h`)

## Context Management

- Accurate token counting via `tiktoken`
- Topic-shift-aware context inclusion
- Time window: recent 30 minutes prioritized

## Source Tracking

- Sessions tagged as `cli` or `api`
- Enables future source-specific behavior and policies

## Performance & Cost

- Local-first routing reduces external API usage
- Cost tracker with soft-cap threshold
- Average local response time target ≈ 800 ms (granite4-micro)

## Future Enhancements

- True streaming from orchestrator
- Rich health checks (Ollama/OpenRouter reachability)
- Persistent API conversations across requests
- Authentication and rate limiting
