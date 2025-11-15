"""Models endpoint handler."""

import logging

from ..config import APIConfig
from ..models.models import Model, ModelList

logger = logging.getLogger(__name__)


def list_models(config: APIConfig) -> ModelList:
    """List all available models.

    Args:
        config: API configuration

    Returns:
        ModelList with all configured models
    """
    all_models = config.list_available_models()

    # Filter to only models that are actually available
    available_models = [
        model_name for model_name in all_models if config.is_model_available(model_name)
    ]

    models = [
        Model(
            id=model_name,
            created=0,  # Could use actual timestamps if needed
            owned_by="kai",
        )
        for model_name in available_models
    ]

    logger.info(
        f"Listed {len(models)} available models (filtered from {len(all_models)} configured)"
    )

    return ModelList(data=models)
