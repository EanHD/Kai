"""Request logging middleware for detailed performance tracking."""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Log detailed request/response metrics."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request details and timing.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/handler
            
        Returns:
            Response object
        """
        # Start timing
        start_time = time.time()
        
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", f"req-{int(start_time * 1000)}")
        
        # Log request start
        logger.info(
            f"→ {request.method} {request.url.path} "
            f"[{request_id}] from {request.client.host if request.client else 'unknown'}"
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract model and cost from response if available
            model_info = ""
            cost_info = ""
            
            # For chat completions, these might be in response headers or body
            if hasattr(response, "headers"):
                model_info = response.headers.get("X-Model-Used", "")
                cost_info = response.headers.get("X-Cost", "")
            
            # Log response
            logger.info(
                f"← {request.method} {request.url.path} "
                f"[{request_id}] {response.status_code} "
                f"in {latency_ms:.0f}ms"
                + (f" model={model_info}" if model_info else "")
                + (f" cost=${cost_info}" if cost_info else "")
            )
            
            # Add timing header
            response.headers["X-Response-Time"] = f"{latency_ms:.2f}ms"
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Log error
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                f"✗ {request.method} {request.url.path} "
                f"[{request_id}] ERROR in {latency_ms:.0f}ms: {str(e)}"
            )
            raise
