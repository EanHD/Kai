"""Chat completions handler."""

import uuid
import logging
from typing import AsyncIterator
from datetime import datetime

from ..models.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChunk,
    Choice,
    StreamChoice,
    Message,
    DeltaMessage,
    Usage,
)
from ..models.errors import invalid_request_error, server_error, not_found_error
from ..config import APIConfig
from ..adapter import OrchestratorAdapter

logger = logging.getLogger(__name__)


def generate_request_id() -> str:
    """Generate OpenAI-style request ID.
    
    Returns:
        Request ID in format: chatcmpl-{uuid}
    """
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


async def process_chat_completion(
    request: ChatCompletionRequest,
    config: APIConfig,
    adapter: OrchestratorAdapter,
) -> ChatCompletionResponse:
    """Process non-streaming chat completion request.
    
    Args:
        request: Validated OpenAI chat completion request
        config: API configuration
        adapter: Orchestrator adapter
        
    Returns:
        OpenAI-formatted chat completion response
        
    Raises:
        ValueError: If model not found or request invalid
    """
    # Generate request ID
    request_id = generate_request_id()
    
    # Resolve model to backend
    model_mapping = config.get_model_mapping(request.model)
    if not model_mapping:
        raise ValueError(f"Model '{request.model}' not found in configuration")
    
    provider = model_mapping["provider"]
    backend_model = model_mapping["model"]
    
    logger.info(
        f"Processing chat completion: model={request.model} -> {provider}/{backend_model}"
    )
    
    # Convert OpenAI request to orchestrator format
    orchestrator_request = adapter.convert_request(
        openai_request=request.model_dump(exclude_none=True),
        provider=provider,
        backend_model=backend_model,
    )
    
    # Invoke orchestrator
    try:
        orchestrator_response = await adapter.invoke_orchestrator(orchestrator_request)
    except Exception as e:
        logger.error(f"Orchestrator invocation failed: {e}")
        raise RuntimeError(f"Failed to generate response: {str(e)}")
    
    # Convert orchestrator response to OpenAI format
    openai_response = adapter.convert_response(
        orchestrator_response=orchestrator_response,
        model_name=request.model,
        request_id=request_id,
    )
    
    return ChatCompletionResponse(**openai_response)


async def process_chat_completion_stream(
    request: ChatCompletionRequest,
    config: APIConfig,
    adapter: OrchestratorAdapter,
) -> AsyncIterator[ChatCompletionChunk]:
    """Process streaming chat completion request.
    
    Args:
        request: Validated OpenAI chat completion request
        config: API configuration
        adapter: Orchestrator adapter
        
    Yields:
        OpenAI-formatted chat completion chunks
        
    Raises:
        ValueError: If model not found or request invalid
    """
    # Generate request ID
    request_id = generate_request_id()
    
    # Resolve model to backend
    model_mapping = config.get_model_mapping(request.model)
    if not model_mapping:
        raise ValueError(f"Model '{request.model}' not found in configuration")
    
    provider = model_mapping["provider"]
    backend_model = model_mapping["model"]
    
    logger.info(
        f"Processing streaming chat completion: model={request.model} -> {provider}/{backend_model}"
    )
    
    # Convert OpenAI request to orchestrator format
    orchestrator_request = adapter.convert_request(
        openai_request=request.model_dump(exclude_none=True),
        provider=provider,
        backend_model=backend_model,
    )
    
    # Stream from orchestrator
    try:
        async for orchestrator_chunk in adapter.invoke_orchestrator_stream(
            orchestrator_request
        ):
            # Convert chunk to OpenAI format
            openai_chunk = await adapter.convert_stream_chunk(
                orchestrator_chunk=orchestrator_chunk,
                model_name=request.model,
                request_id=request_id,
            )
            
            yield ChatCompletionChunk(**openai_chunk)
            
    except Exception as e:
        logger.error(f"Streaming failed: {e}")
        raise RuntimeError(f"Failed to stream response: {str(e)}")
