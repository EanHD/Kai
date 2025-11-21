"""API configuration loader."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class APIConfig:
    """Load and manage API configuration from api.yaml."""

    def __init__(self, config_path: str | None = None):
        """Initialize configuration.

        Args:
            config_path: Path to api.yaml config file (default: config/api.yaml)
        """
        if config_path is None:
            config_path = os.path.join("config", "api.yaml")

        self.config_path = Path(config_path)
        self.config: dict[str, Any] = {}

        self._load_config()

    def _load_config(self):
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}, using defaults")
            self._load_defaults()
            return

        try:
            with open(self.config_path) as f:
                self.config = yaml.safe_load(f) or {}

            logger.info(f"Loaded API configuration from {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._load_defaults()

    def _load_defaults(self):
        """Load default configuration."""
        self.config = {
            "server": {
                "host": "0.0.0.0",
                "port": 9000,
                "workers": 4,
                "reload": False,
            },
            "auth": {
                "enabled": False,
                "allow_no_auth": True,
            },
            "model_mapping": {
                "granite-local": {
                    "provider": "ollama",
                    "model": "granite4:tiny-h",
                },
            },
            "default_model": "qwen-local",
            "cors": {
                "enabled": True,
                "allow_origins": ["*"],
                "allow_methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
            },
            "rate_limiting": {
                "enabled": False,
                "default_limit": "60/minute",
            },
            "logging": {
                "level": "INFO",
                "log_requests": True,
                "log_responses": False,
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated key.

        Args:
            key: Dot-separated key path (e.g., "server.port")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def get_model_mapping(self, model_name: str) -> dict[str, str] | None:
        """Get backend mapping for a model name.

        Args:
            model_name: Client-requested model name

        Returns:
            Dict with provider and model, or None if not found
        """
        mappings = self.get("model_mapping", {})
        return mappings.get(model_name)

    def get_default_model(self) -> str:
        """Get default model name.

        Returns:
            Default model name
        """
        return self.get("default_model", "qwen-local")

    def list_available_models(self) -> list[str]:
        """Get list of all available model names.

        Returns:
            List of model names
        """
        mappings = self.get("model_mapping", {})
        return list(mappings.keys())

    def get_openrouter_api_key(self) -> str | None:
        """Get OpenRouter API key from environment.

        Returns:
            API key or None if not set
        """
        return os.getenv("OPENROUTER_API_KEY")

    def is_model_available(self, model_name: str) -> bool:
        """Check if a model is actually available (has required credentials).

        Args:
            model_name: Model name to check

        Returns:
            True if model can be used, False otherwise
        """
        mapping = self.get_model_mapping(model_name)
        if not mapping:
            return False

        provider = mapping.get("provider")

        # Ollama models are always available (local)
        if provider == "ollama":
            return True

        # OpenRouter models need API key
        if provider == "openrouter":
            api_key = self.get_openrouter_api_key()
            if not api_key:
                logger.debug(f"Model '{model_name}' unavailable: No OpenRouter API key")
                return False
            return True

        # Unknown provider
        return False
