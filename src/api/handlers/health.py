"""Health check endpoint handler."""

import logging

from ..config import APIConfig
from ..models.health import HealthStatus, ServiceStatus

logger = logging.getLogger(__name__)


async def check_health(config: APIConfig) -> HealthStatus:
    """Check health of API and dependencies.

    Args:
        config: API configuration

    Returns:
        HealthStatus with service statuses
    """
    services = {}

    # Check API configuration
    try:
        if config.config:
            services["config"] = ServiceStatus(
                name="configuration",
                status="healthy",
                message="Configuration loaded successfully",
            )
        else:
            services["config"] = ServiceStatus(
                name="configuration",
                status="unhealthy",
                message="Configuration not loaded",
            )
    except Exception as e:
        services["config"] = ServiceStatus(
            name="configuration",
            status="unhealthy",
            message=f"Configuration error: {str(e)}",
        )

    # Check model mappings
    try:
        models = config.list_available_models()
        if models:
            services["models"] = ServiceStatus(
                name="model_mapping",
                status="healthy",
                message=f"{len(models)} models configured",
            )
        else:
            services["models"] = ServiceStatus(
                name="model_mapping",
                status="unhealthy",
                message="No models configured",
            )
    except Exception as e:
        services["models"] = ServiceStatus(
            name="model_mapping",
            status="unhealthy",
            message=f"Model mapping error: {str(e)}",
        )

    # TODO: Add checks for orchestrator, Ollama, OpenRouter when integrated
    services["orchestrator"] = ServiceStatus(
        name="orchestrator",
        status="unknown",
        message="Not yet integrated",
    )

    # Determine overall health
    statuses = [s.status for s in services.values()]

    if all(s == "healthy" for s in statuses):
        overall_status = "healthy"
    elif all(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    logger.info(f"Health check: {overall_status}")

    return HealthStatus(
        status=overall_status,
        services=services,
    )
