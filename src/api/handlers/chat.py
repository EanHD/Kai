"""Chat completions handler."""

import logging
import uuid

from ..adapter import OrchestratorAdapter
from ..config import APIConfig
from ..models.chat import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
)

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

    # Validate messages
    if not request.messages or len(request.messages) == 0:
        raise ValueError("At least one message is required")

    # Check if there's at least one user message
    has_user_message = any(msg.role == "user" for msg in request.messages)
    if not has_user_message:
        raise ValueError("At least one user message is required")

    # Resolve model to backend
    model_mapping = config.get_model_mapping(request.model)
    if not model_mapping:
        available = ", ".join(config.list_available_models())
        raise ValueError(f"Model '{request.model}' not found. Available models: {available}")

    # Check if model is actually available (has credentials)
    if not config.is_model_available(request.model):
        raise ValueError(
            f"Model '{request.model}' is configured but not available. "
            f"Check that required API keys or services are configured."
        )

    provider = model_mapping["provider"]
    backend_model = model_mapping["model"]

    logger.info(
        f"Processing chat completion: request_id={request_id}, "
        f"model={request.model} -> {provider}/{backend_model}, "
        f"messages={len(request.messages)}, temp={request.temperature}"
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
        logger.info(
            f"Orchestrator success: request_id={request_id}, "
            f"tokens={orchestrator_response.get('total_tokens', 0)}, "
            f"cost=${orchestrator_response.get('cost', 0):.4f}"
        )
    except Exception as e:
        logger.error(f"Orchestrator invocation failed: request_id={request_id}, error={e}")
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
):
    """Process streaming chat completion request.

    Args:
        request: Validated OpenAI chat completion request
        config: API configuration
        adapter: Orchestrator adapter

    Yields:
        SSE-formatted strings (not ChatCompletionChunk objects)

    Raises:
        ValueError: If model not found or request invalid
    """
    # Generate request ID
    request_id = generate_request_id()

    # Validate messages (same as non-streaming)
    if not request.messages or len(request.messages) == 0:
        raise ValueError("At least one message is required")

    has_user_message = any(msg.role == "user" for msg in request.messages)
    if not has_user_message:
        raise ValueError("At least one user message is required")

    # Resolve model to backend
    model_mapping = config.get_model_mapping(request.model)
    if not model_mapping:
        available = ", ".join(config.list_available_models())
        raise ValueError(f"Model '{request.model}' not found. Available models: {available}")

    if not config.is_model_available(request.model):
        raise ValueError(
            f"Model '{request.model}' is configured but not available. "
            f"Check that required API keys or services are configured."
        )

    provider = model_mapping["provider"]
    backend_model = model_mapping["model"]

    logger.info(
        f"Processing streaming chat completion: request_id={request_id}, "
        f"model={request.model} -> {provider}/{backend_model}, "
        f"messages={len(request.messages)}"
    )

    # Convert OpenAI request to orchestrator format
    orchestrator_request = adapter.convert_request(
        openai_request=request.model_dump(exclude_none=True),
        provider=provider,
        backend_model=backend_model,
    )

    # Stream from orchestrator
    try:
        async for orchestrator_chunk in adapter.invoke_orchestrator_stream(orchestrator_request):
            # Convert chunk to OpenAI format
            openai_chunk = await adapter.convert_stream_chunk(
                orchestrator_chunk=orchestrator_chunk,
                model_name=request.model,
                request_id=request_id,
            )

            chunk_obj = ChatCompletionChunk(**openai_chunk)

            # Yield just the JSON - EventSourceResponse will add "data: " prefix
            chunk_json = chunk_obj.model_dump_json(exclude_none=True)
            yield chunk_json

        # Send [DONE] marker
        yield "[DONE]"

        logger.info(f"Streaming completed: request_id={request_id}")

    except Exception as e:
        logger.error(f"Streaming failed: request_id={request_id}, error={e}")
        raise RuntimeError(f"Failed to stream response: {str(e)}")
