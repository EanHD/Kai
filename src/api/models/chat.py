"""OpenAI chat completion models (Pydantic schemas)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ============================================================================
# Request Models
# ============================================================================


class Message(BaseModel):
    """Chat message in OpenAI format."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


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
    function: dict[str, Any]


class ChatCompletionRequest(BaseModel):
    """OpenAI chat completion request.

    See: https://platform.openai.com/docs/api-reference/chat/create
    """

    # Required
    model: str
    messages: list[Message]

    # Optional parameters
    temperature: float | None = Field(default=1.0, ge=0.0, le=2.0)
    top_p: float | None = Field(default=1.0, ge=0.0, le=1.0)
    n: int | None = Field(default=1, ge=1, le=10)
    stream: bool | None = False
    stop: str | list[str] | None = None
    max_tokens: int | None = Field(default=None, ge=1)
    presence_penalty: float | None = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float | None = Field(default=0.0, ge=-2.0, le=2.0)
    logit_bias: dict[str, float] | None = None
    user: str | None = None

    # Tool/function calling
    tools: list[Tool] | None = None
    tool_choice: str | dict[str, Any] | None = None

    # Response format
    response_format: dict[str, str] | None = None

    # Legacy function calling (deprecated but supported)
    functions: list[dict[str, Any]] | None = None
    function_call: str | dict[str, str] | None = None


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
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter"] | None


class ChatCompletionResponse(BaseModel):
    """OpenAI chat completion response.

    See: https://platform.openai.com/docs/api-reference/chat/object
    """

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage
    system_fingerprint: str | None = None


# ============================================================================
# Streaming Models
# ============================================================================


class DeltaMessage(BaseModel):
    """Delta message for streaming chunks."""

    role: Literal["system", "user", "assistant", "tool"] | None = None
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class StreamChoice(BaseModel):
    """Streaming choice."""

    index: int
    delta: DeltaMessage
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter"] | None = None


class ChatCompletionChunk(BaseModel):
    """Streaming chunk in OpenAI format.

    See: https://platform.openai.com/docs/api-reference/chat/streaming
    """

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[StreamChoice]
    system_fingerprint: str | None = None
