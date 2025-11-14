# Kai OpenAI-Compatible API Documentation

## Overview

Kai provides a drop-in replacement for the OpenAI API, allowing you to use local models (via Ollama) or external models (via OpenRouter) with full OpenAI compatibility.

**Base URL**: `http://localhost:9000`

**OpenAPI Docs**: `http://localhost:9000/docs`

## Quick Start

```bash
# Install dependencies
uv sync

# Start the server
uv run python main.py

# Server runs on http://localhost:9000
```

## Endpoints

### 1. Chat Completions

**POST** `/v1/chat/completions`

OpenAI-compatible chat completions with streaming support.

**Request Body**:
```json
{
  "model": "granite-local",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.7,
  "max_tokens": 150,
  "stream": false
}
```

**Response** (non-streaming):
```json
{
  "id": "chatcmpl-abc123...",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "granite-local",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 10,
    "total_tokens": 25
  }
}
```

**Streaming**: Set `"stream": true` to receive SSE chunks:
```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk",...}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk",...}

data: [DONE]
```

### 2. List Models

**GET** `/v1/models`

List all available models.

**Response**:
```json
{
  "object": "list",
  "data": [
    {
      "id": "granite-local",
      "object": "model",
      "created": 0,
      "owned_by": "kai"
    },
    {
      "id": "gpt-4",
      "object": "model",
      "created": 0,
      "owned_by": "kai"
    }
  ]
}
```

### 3. Health Check

**GET** `/health`

Check API and dependency health.

**Response**:
```json
{
  "status": "healthy",
  "services": {
    "config": {
      "name": "configuration",
      "status": "healthy",
      "message": "Configuration loaded successfully"
    },
    "models": {
      "name": "model_mapping",
      "status": "healthy",
      "message": "3 models configured"
    }
  },
  "version": "0.1.0"
}
```

## Available Models

Models are configured in `config/api.yaml`:

| Model Name | Backend | Description |
|------------|---------|-------------|
| `granite-local` | Ollama (granite4:tiny-h) | Local, fast, free |
| `gpt-4` | OpenRouter (Claude Opus) | External, high-quality |
| `gpt-3.5-turbo` | OpenRouter (Claude Sonnet) | External, balanced |

## Authentication

**Development Mode**: Authentication disabled by default (`allow_no_auth: true` in config).

**Production Mode**: Set `auth.enabled: true` and provide API keys via `Authorization: Bearer <key>` header.

## Using with OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:9000/v1",
    api_key="not-needed",  # In dev mode
)

# Use exactly like OpenAI API
response = client.chat.completions.create(
    model="granite-local",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

See `examples/openai_client.py` for more examples.

**Note**: If using the example client, run with `uv run python examples/openai_client.py`

## Error Handling

All errors follow OpenAI's error format:

```json
{
  "error": {
    "message": "Model 'invalid-model' not found in configuration",
    "type": "invalid_request_error",
    "param": null,
    "code": null
  }
}
```

**Error Types**:
- `invalid_request_error` (400): Bad request parameters
- `authentication_error` (401): Invalid API key
- `not_found_error` (404): Resource not found
- `rate_limit_error` (429): Rate limit exceeded
- `server_error` (500): Internal server error

## Configuration

Edit `config/api.yaml`:

```yaml
server:
  host: 0.0.0.0
  port: 9000
  workers: 4

model_mapping:
  granite-local:
    provider: ollama
    model: granite4:tiny-h
  
  gpt-4:
    provider: openrouter
    model: anthropic/claude-opus

default_model: granite-local

cors:
  enabled: true
  allow_origins: ["*"]
```

## Deployment

See `docs/deployment.md` for production deployment instructions.
