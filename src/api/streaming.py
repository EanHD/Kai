"""Server-Sent Events (SSE) streaming utilities for OpenAI format."""

import json
import logging
from typing import AsyncIterator

from .models.chat import ChatCompletionChunk

logger = logging.getLogger(__name__)


async def stream_openai_response(
    chunks: AsyncIterator[ChatCompletionChunk],
) -> AsyncIterator[str]:
    """Convert chat completion chunks to SSE format.
    
    Formats chunks according to OpenAI's SSE specification:
    - Each chunk is prefixed with "data: "
    - Chunks are separated by double newlines
    - Stream ends with "data: [DONE]\\n\\n"
    
    Args:
        chunks: Async iterator of ChatCompletionChunk objects
        
    Yields:
        SSE-formatted strings ready for streaming
        
    Example output:
        data: {"id":"chatcmpl-123","object":"chat.completion.chunk",...}
        
        data: {"id":"chatcmpl-123","object":"chat.completion.chunk",...}
        
        data: [DONE]
        
    """
    try:
        async for chunk in chunks:
            # Convert chunk to JSON
            chunk_json = chunk.model_dump_json(exclude_none=True)
            
            # Format as SSE data
            sse_data = f"data: {chunk_json}\n\n"
            
            yield sse_data
            
        # Send final [DONE] marker
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        # Send error as SSE comment (won't break client)
        yield f": error: {str(e)}\n\n"
        yield "data: [DONE]\n\n"


async def handle_client_disconnect(chunks: AsyncIterator[ChatCompletionChunk]):
    """Wrapper to handle client disconnects gracefully.
    
    This generator wraps the chunk iterator and catches
    GeneratorExit to perform cleanup when client disconnects.
    
    Args:
        chunks: Async iterator of ChatCompletionChunk objects
        
    Yields:
        ChatCompletionChunk objects
    """
    try:
        async for chunk in chunks:
            yield chunk
    except GeneratorExit:
        logger.info("Client disconnected, stopping stream")
        # Cleanup can happen here if needed
        raise
    except Exception as e:
        logger.error(f"Error in stream: {e}")
        raise
