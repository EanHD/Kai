"""Configuration loader for models, tools, and environment variables."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Model configuration."""

    model_id: str
    model_name: str
    provider: str
    capabilities: list[str]
    context_window: int
    cost_per_1k_input: float
    cost_per_1k_output: float
    routing_priority: int
    is_local: bool
    active: bool


@dataclass
class ToolConfig:
    """Tool configuration."""

    enabled: bool
    provider: str
    config: dict[str, Any]


class ConfigLoader:
    """Loads and manages application configuration."""

    def __init__(self, config_dir: str | None = None, env_file: str | None = None):
        """Initialize configuration loader.

        Args:
            config_dir: Directory containing config files (default: ./config)
            env_file: Path to .env file (default: ./.env)
        """
        self.config_dir = Path(config_dir or "config")
        self.env_file = Path(env_file or ".env")

        # Load environment variables
        if self.env_file.exists():
            load_dotenv(self.env_file)
            logger.info(f"Loaded environment from {self.env_file}")
        else:
            logger.warning(f"Environment file not found: {self.env_file}")

        # Load configurations
        self.models = self._load_models()
        self.tools = self._load_tools()
        self.env = self._load_env_vars()

    def _load_models(self) -> dict[str, ModelConfig]:
        """Load model configurations from models.yaml."""
        models_file = self.config_dir / "models.yaml"

        if not models_file.exists():
            logger.warning(f"Models config not found: {models_file}")
            return {}

        with open(models_file) as f:
            data = yaml.safe_load(f)

        models = {}
        for model_data in data.get("models", []):
            config = ModelConfig(
                model_id=model_data["model_id"],
                model_name=model_data["model_name"],
                provider=model_data["provider"],
                capabilities=model_data["capabilities"],
                context_window=model_data["context_window"],
                cost_per_1k_input=model_data["cost_per_1k_input"],
                cost_per_1k_output=model_data["cost_per_1k_output"],
                routing_priority=model_data["routing_priority"],
                is_local=model_data["is_local"],
                active=model_data.get("active", True),
            )
            models[config.model_id] = config

        logger.info(f"Loaded {len(models)} model configurations")
        return models

    def _load_tools(self) -> dict[str, ToolConfig]:
        """Load tool configurations from tools.yaml."""
        tools_file = self.config_dir / "tools.yaml"

        if not tools_file.exists():
            logger.warning(f"Tools config not found: {tools_file}")
            return {}

        with open(tools_file) as f:
            data = yaml.safe_load(f)

        tools = {}
        for tool_name, tool_data in data.get("tools", {}).items():
            config = ToolConfig(
                enabled=tool_data.get("enabled", True),
                provider=tool_data["provider"],
                config=tool_data.get("config", {}),
            )
            tools[tool_name] = config

        logger.info(f"Loaded {len(tools)} tool configurations")
        return tools

    def _load_env_vars(self) -> dict[str, Any]:
        """Load environment variables."""
        env_vars = {
            # API Keys
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
            "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            # Database paths
            "sqlite_db_path": os.getenv("SQLITE_DB_PATH", "./data/kai.db"),
            "vector_db_path": os.getenv("VECTOR_DB_PATH", "./data/vectors"),
            # Cost controls
            "default_cost_limit": float(os.getenv("DEFAULT_COST_LIMIT", "1.0")),
            "soft_cap_threshold": float(os.getenv("SOFT_CAP_THRESHOLD", "0.8")),
            # Tool settings
            "web_search_max_results": int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5")),
            "code_exec_timeout": int(os.getenv("CODE_EXEC_TIMEOUT", "30")),
            "code_exec_memory_limit": int(os.getenv("CODE_EXEC_MEMORY_LIMIT", "512")),
            # Encryption
            "encryption_key": os.getenv("ENCRYPTION_KEY"),
            # Embedding model
            "embedding_model": os.getenv(
                "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            ),
        }

        # Validate required keys
        required_keys = ["encryption_key"]
        missing = [k for k in required_keys if not env_vars.get(k)]
        if missing:
            logger.error(f"Missing required environment variables: {missing}")
            raise ValueError(f"Missing required environment variables: {missing}")

        logger.info("Loaded environment variables")
        return env_vars

    def get_model(self, model_id: str) -> ModelConfig | None:
        """Get model configuration by ID."""
        return self.models.get(model_id)

    def get_active_models(self) -> list[ModelConfig]:
        """Get all active model configurations."""
        return [m for m in self.models.values() if m.active]

    def get_tool(self, tool_name: str) -> ToolConfig | None:
        """Get tool configuration by name."""
        return self.tools.get(tool_name)

    def get_enabled_tools(self) -> dict[str, ToolConfig]:
        """Get all enabled tool configurations."""
        return {name: config for name, config in self.tools.items() if config.enabled}

    def get_env(self, key: str, default: Any = None) -> Any:
        """Get environment variable value."""
        return self.env.get(key, default)
