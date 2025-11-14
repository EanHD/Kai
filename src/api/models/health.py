"""Health check models."""

from typing import Dict, Literal
from pydantic import BaseModel


class ServiceStatus(BaseModel):
    """Individual service health status."""

    name: str
    status: Literal["healthy", "unhealthy", "unknown"]
    message: str = ""


class HealthStatus(BaseModel):
    """Overall health status."""

    status: Literal["healthy", "degraded", "unhealthy"]
    services: Dict[str, ServiceStatus]
    version: str = "0.1.0"
