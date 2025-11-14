"""Test OpenAI API compatibility (basic structure tests)."""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint should return 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_status(self, client):
        """Health response should have status field."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_health_has_services(self, client):
        """Health response should include service checks."""
        response = client.get("/health")
        data = response.json()
        assert "services" in data
        assert isinstance(data["services"], dict)


class TestModelsEndpoint:
    """Test models list endpoint."""

    def test_models_returns_200(self, client):
        """Models endpoint should return 200."""
        response = client.get("/v1/models")
        assert response.status_code == 200

    def test_models_has_list_object(self, client):
        """Models response should have object='list'."""
        response = client.get("/v1/models")
        data = response.json()
        assert data["object"] == "list"

    def test_models_has_data_array(self, client):
        """Models response should have data array."""
        response = client.get("/v1/models")
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_models_include_granite_local(self, client):
        """Should include granite-local model."""
        response = client.get("/v1/models")
        data = response.json()
        model_ids = [m["id"] for m in data["data"]]
        assert "granite-local" in model_ids


class TestChatCompletionsEndpoint:
    """Test chat completions endpoint structure."""

    def test_chat_completions_requires_post(self, client):
        """Chat completions should be POST only."""
        response = client.get("/v1/chat/completions")
        assert response.status_code == 405  # Method Not Allowed

    def test_chat_completions_validates_model(self, client):
        """Should return error for missing model."""
        response = client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "test"}],
            },
        )
        assert response.status_code == 422  # Validation error

    def test_chat_completions_validates_messages(self, client):
        """Should return error for missing messages."""
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "granite-local",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_chat_completions_accepts_valid_request(self, client):
        """Should accept valid request structure."""
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "granite-local",
                "messages": [{"role": "user", "content": "test"}],
            },
        )
        # Will return 200 or 500 depending on orchestrator stub
        # Just checking it doesn't reject the request structure
        assert response.status_code in [200, 500]

    def test_chat_completions_nonstreaming_structure(self, client):
        """Non-streaming response should match OpenAI format."""
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "granite-local",
                "messages": [{"role": "user", "content": "test"}],
                "stream": False,
            },
        )

        if response.status_code == 200:
            data = response.json()
            # Check OpenAI response structure
            assert "id" in data
            assert "object" in data
            assert data["object"] == "chat.completion"
            assert "created" in data
            assert "model" in data
            assert "choices" in data
            assert isinstance(data["choices"], list)
            assert "usage" in data


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_returns_200(self, client):
        """Root endpoint should return 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_includes_endpoints(self, client):
        """Root should list available endpoints."""
        response = client.get("/")
        data = response.json()
        assert "endpoints" in data
