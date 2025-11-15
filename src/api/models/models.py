"""OpenAI models list models."""

from typing import Literal

from pydantic import BaseModel


class Model(BaseModel):
    """Individual model object.

    See: https://platform.openai.com/docs/api-reference/models/object
    """

    id: str
    object: Literal["model"] = "model"
    created: int = 0  # Unix timestamp (can use actual creation time if available)
    owned_by: str = "kai"


class ModelList(BaseModel):
    """List of available models.

    See: https://platform.openai.com/docs/api-reference/models/list
    """

    object: Literal["list"] = "list"
    data: list[Model]
