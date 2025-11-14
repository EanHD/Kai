"""OpenAI chat completion models (Pydantic schemas)."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


# ============================================================================
# Request Models
# ============================================================================


class Message(BaseModel):
    """Chat message in OpenAI format."""

    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class FunctionCall(BaseModel):
    """Function call specification."""

    name: str
    arguments: str  # JSON string


class ToolCall(BaseModel):
    """Tool call specification."""

    id: str
    type: Literal["function"]
    function: FunctionCall


class Tool(BaseModel):
    """Tool definition in OpenAI format."""

    type: Literal["function"]
    function: Dict[str, Any]


class ChatCompletionRequest(BaseModel):
    """OpenAI chat completion request.
    
    See: https://platform.openai.com/docs/api-reference/chat/create
    """

    # Required
    model: str
    messages: List[Message]

    # Optional parameters
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    n: Optional[int] = Field(default=1, ge=1, le=10)
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = Field(default=None, ge=1)
    presence_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None

    # Tool/function calling
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None

    # Response format
    response_format: Optional[Dict[str, str]] = None

    # Legacy function calling (deprecated but supported)
    functions: Optional[List[Dict[str, Any]]] = None
    function_call: Optional[Union[str, Dict[str, str]]] = None


# ============================================================================
# Response Models (Non-Streaming)
# ============================================================================


class Usage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Choice(BaseModel):
    """Single completion choice."""

    index: int
    message: Message
    finish_reason: Optional[Literal["stop", "length", "tool_calls", "content_filter"]]


class ChatCompletionResponse(BaseModel):
    """OpenAI chat completion response.
    
    See: https://platform.openai.com/docs/api-reference/chat/object
    """

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage
    system_fingerprint: Optional[str] = None


# ============================================================================
# Streaming Models
# ============================================================================


class DeltaMessage(BaseModel):
    """Delta message for streaming chunks."""

    role: Optional[Literal["system", "user", "assistant", "tool"]] = None
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class StreamChoice(BaseModel):
    """Streaming choice."""

    index: int
    delta: DeltaMessage
    finish_reason: Optional[Literal["stop", "length", "tool_calls", "content_filter"]] = None


class ChatCompletionChunk(BaseModel):
    """Streaming chunk in OpenAI format.
    
    See: https://platform.openai.com/docs/api-reference/chat/streaming
    """

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: List[StreamChoice]
    system_fingerprint: Optional[str] = None
