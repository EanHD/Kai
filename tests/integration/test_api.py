"""Integration tests for OpenAI-compatible API endpoints."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from main import app
from src.models.response import Response


@pytest.fixture(scope="module")
def client():
    """Create test client that properly initializes app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_response():
    """Create mock response for process_query."""
    return Response(
        query_id="test-query-id",
        mode="concise",
        content="This is a test response",
        token_count=10,
        cost=0.0001,
    )


def test_root_endpoint(client):
    """Test root endpoint returns API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "endpoints" in data
    assert "/v1/chat/completions" in str(data)


def test_models_endpoint(client):
    """Test /v1/models endpoint returns available models."""
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "object" in data
    assert data["object"] == "list"
    assert isinstance(data["data"], list)

    # Should have at least the local model
    model_ids = [m["id"] for m in data["data"]]
    assert len(model_ids) > 0


def test_health_endpoint(client):
    """Test /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_chat_completion_validation_no_messages(client):
    """Test chat completion with no messages returns error."""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "granite-local",
            "messages": [],
        },
    )
    assert response.status_code == 422  # Validation error


def test_chat_completion_validation_no_user_message(client):
    """Test chat completion with no user message returns error."""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "granite-local",
            "messages": [{"role": "system", "content": "You are helpful"}],
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "user message" in data["error"]["message"].lower()


def test_chat_completion_invalid_model(client):
    """Test chat completion with invalid model."""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "nonexistent-model",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "not found" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_chat_completion_happy_path(client, mock_orchestrator):
    """Test successful chat completion (happy path)."""
    # Patch the orchestrator
    with patch.object(app.state, "orchestrator", mock_orchestrator):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "granite-local",
                "messages": [{"role": "user", "content": "Hello, how are you?"}],
                "temperature": 0.7,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Validate OpenAI response structure
        assert "id" in data
        assert data["id"].startswith("chatcmpl-")
        assert "object" in data
        assert data["object"] == "chat.completion"
        assert "created" in data
        assert "model" in data
        assert "choices" in data
        assert len(data["choices"]) > 0

        # Validate choice structure
        choice = data["choices"][0]
        assert "index" in choice
        assert "message" in choice
        assert "finish_reason" in choice

        # Validate message structure
        message = choice["message"]
        assert "role" in message
        assert message["role"] == "assistant"
        assert "content" in message
        assert len(message["content"]) > 0

        # Validate usage
        assert "usage" in data
        usage = data["usage"]
        assert "prompt_tokens" in usage
        assert "completion_tokens" in usage
        assert "total_tokens" in usage


def test_chat_completion_streaming_format(client):
    """Test streaming response format (validates SSE structure)."""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "granite-local",
            "messages": [{"role": "user", "content": "Say hello"}],
            "stream": True,
        },
        stream=True,
    )

    # Should return 200 for streaming
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


def test_cors_headers(client):
    """Test CORS headers are present."""
    response = client.options("/v1/chat/completions")
    assert response.status_code == 200

    # Check CORS headers
    headers = response.headers
    assert "access-control-allow-origin" in headers
    assert "access-control-allow-methods" in headers


def test_chat_completion_with_system_message(client):
    """Test chat completion with system message."""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "granite-local",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"},
            ],
        },
    )

    # Should not fail - system messages are allowed with user messages
    assert response.status_code in [200, 503]  # 503 if Ollama not running


def test_chat_completion_temperature_validation(client):
    """Test temperature validation (0.0-2.0)."""
    # Valid temperature
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "granite-local",
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 1.0,
        },
    )
    assert response.status_code in [200, 503]

    # Invalid temperature (too high)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "granite-local",
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 3.0,
        },
    )
    assert response.status_code == 422


def test_api_error_format(client):
    """Test that API errors follow OpenAI format."""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "invalid-model",
            "messages": [{"role": "user", "content": "Test"}],
        },
    )

    assert response.status_code == 400
    data = response.json()

    # OpenAI error format
    assert "error" in data
    error = data["error"]
    assert "message" in error
    assert "type" in error
    assert isinstance(error["message"], str)
    assert isinstance(error["type"], str)
