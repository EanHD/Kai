"""OpenAI-compatible error models."""

from pydantic import BaseModel


class OpenAIError(BaseModel):
    """OpenAI error object.

    See: https://platform.openai.com/docs/guides/error-codes
    """

    message: str
    type: str
    param: str | None = None
    code: str | None = None


class ErrorResponse(BaseModel):
    """OpenAI error response wrapper."""

    error: OpenAIError


# ============================================================================
# Error Type Constants
# ============================================================================

# Error types matching OpenAI's error taxonomy
ERROR_TYPE_INVALID_REQUEST = "invalid_request_error"
ERROR_TYPE_AUTHENTICATION = "authentication_error"
ERROR_TYPE_PERMISSION = "permission_error"
ERROR_TYPE_NOT_FOUND = "not_found_error"
ERROR_TYPE_RATE_LIMIT = "rate_limit_error"
ERROR_TYPE_API_ERROR = "api_error"
ERROR_TYPE_TIMEOUT = "timeout_error"
ERROR_TYPE_SERVER = "server_error"


# ============================================================================
# Error Factory Functions
# ============================================================================


def create_error_response(
    message: str,
    error_type: str = ERROR_TYPE_API_ERROR,
    param: str | None = None,
    code: str | None = None,
) -> ErrorResponse:
    """Create an OpenAI-formatted error response.

    Args:
        message: Human-readable error message
        error_type: Type of error (see ERROR_TYPE_* constants)
        param: Parameter that caused the error (optional)
        code: Error code (optional)

    Returns:
        ErrorResponse object
    """
    return ErrorResponse(
        error=OpenAIError(
            message=message,
            type=error_type,
            param=param,
            code=code,
        )
    )


def invalid_request_error(message: str, param: str | None = None) -> ErrorResponse:
    """Create invalid request error."""
    return create_error_response(message, ERROR_TYPE_INVALID_REQUEST, param=param)


def authentication_error(message: str = "Invalid API key") -> ErrorResponse:
    """Create authentication error."""
    return create_error_response(message, ERROR_TYPE_AUTHENTICATION)


def not_found_error(message: str, param: str | None = None) -> ErrorResponse:
    """Create not found error."""
    return create_error_response(message, ERROR_TYPE_NOT_FOUND, param=param)


def rate_limit_error(message: str = "Rate limit exceeded") -> ErrorResponse:
    """Create rate limit error."""
    return create_error_response(message, ERROR_TYPE_RATE_LIMIT)


def server_error(message: str = "Internal server error") -> ErrorResponse:
    """Create server error."""
    return create_error_response(message, ERROR_TYPE_SERVER)
