"""Health check utilities for external services."""

import asyncio
import logging
from typing import Dict, Any, Optional
import docker
from docker.errors import DockerException

logger = logging.getLogger(__name__)


class HealthCheck:
    """Health checker for external dependencies."""

    def __init__(self):
        """Initialize health checker."""
        pass

    async def check_ollama(self, base_url: str = "http://localhost:11434") -> Dict[str, Any]:
        """Check if Ollama service is available.
        
        Args:
            base_url: Ollama service URL
            
        Returns:
            Health status dict with available and details
        """
        try:
            import ollama
            
            # Try to list models (lightweight check)
            client = ollama.Client(host=base_url)
            models = client.list()
            
            return {
                "available": True,
                "service": "ollama",
                "url": base_url,
                "models_count": len(models.get("models", [])),
            }
        
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return {
                "available": False,
                "service": "ollama",
                "url": base_url,
                "error": str(e),
            }

    async def check_openrouter(self, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Check if OpenRouter API is accessible.
        
        Args:
            api_key: OpenRouter API key
            
        Returns:
            Health status dict with available and details
        """
        if not api_key:
            return {
                "available": False,
                "service": "openrouter",
                "error": "No API key provided",
            }
        
        try:
            import httpx
            
            # Simple ping to check API is reachable
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=5.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "available": True,
                        "service": "openrouter",
                        "models_count": len(data.get("data", [])),
                    }
                else:
                    return {
                        "available": False,
                        "service": "openrouter",
                        "error": f"HTTP {response.status_code}",
                    }
        
        except Exception as e:
            logger.warning(f"OpenRouter health check failed: {e}")
            return {
                "available": False,
                "service": "openrouter",
                "error": str(e),
            }

    async def check_docker(self) -> Dict[str, Any]:
        """Check if Docker daemon is running.
        
        Returns:
            Health status dict with available and details
        """
        try:
            client = docker.from_env()
            info = client.info()
            
            return {
                "available": True,
                "service": "docker",
                "version": info.get("ServerVersion", "unknown"),
                "containers": info.get("Containers", 0),
                "images": info.get("Images", 0),
            }
        
        except DockerException as e:
            logger.warning(f"Docker health check failed: {e}")
            return {
                "available": False,
                "service": "docker",
                "error": str(e),
            }

    async def check_all(
        self,
        ollama_url: str = "http://localhost:11434",
        openrouter_key: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Check health of all services.
        
        Args:
            ollama_url: Ollama service URL
            openrouter_key: Optional OpenRouter API key
            
        Returns:
            Dict mapping service name to health status
        """
        # Run all checks in parallel
        results = await asyncio.gather(
            self.check_ollama(ollama_url),
            self.check_openrouter(openrouter_key),
            self.check_docker(),
            return_exceptions=True,
        )
        
        health_status = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Health check exception: {result}")
                continue
            
            service = result.get("service", "unknown")
            health_status[service] = result
        
        return health_status
