"""
FastAPI OpenAI-Compatible API Server

Provides OpenAI-compatible endpoints for chat completions, model listing,
and health checks. Routes requests to the existing orchestrator with 
intelligent model selection.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.config import APIConfig
from src.lib.logger import setup_logging
from src.core.orchestrator import Orchestrator
from src.storage.sqlite_store import SQLiteStore
from src.storage.memory_vault import MemoryVault
from src.agents.reflection_agent import ReflectionAgent
from src.core.providers.ollama_provider import OllamaProvider
from src.core.providers.openrouter_provider import OpenRouterProvider
from src.lib.config import ConfigLoader
import os

logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    # Startup
    logger.info("Starting FastAPI OpenAI-compatible API server")
    
    server_config = app.state.config.get("server", {})
    logger.info(f"Server configured for port {server_config.get('port', 9000)}")
    
    # Initialize services
    logger.info("Initializing storage and orchestrator...")
    
    # Initialize SQLite storage
    storage = SQLiteStore(db_path="data/kai.db")
    app.state.storage = storage
    
    # Load Kai configuration for LLM settings
    kai_config = ConfigLoader()
    
    # Initialize LLM connectors
    local_connector = None
    external_connectors = {}
    
    active_models = kai_config.get_active_models()
    for model_config in active_models:
        config_dict = {
            "model_id": model_config.model_id,
            "model_name": model_config.model_name,
            "provider": model_config.provider,
            "capabilities": model_config.capabilities,
            "context_window": model_config.context_window,
            "cost_per_1k_input": model_config.cost_per_1k_input,
            "cost_per_1k_output": model_config.cost_per_1k_output,
        }
        
        if model_config.provider == "ollama":
            ollama_url = kai_config.get_env("ollama_base_url")
            local_connector = OllamaProvider(config_dict, ollama_url)
            logger.info(f"Initialized Ollama: {model_config.model_name}")
        
        elif model_config.provider == "openrouter":
            api_key = kai_config.get_env("openrouter_api_key")
            if api_key:
                connector = OpenRouterProvider(config_dict, api_key)
                external_connectors[model_config.model_id] = connector
                logger.info(f"Initialized OpenRouter: {model_config.model_name}")
    
    if not local_connector:
        logger.error("No local connector initialized - API will not function properly")
    
    # Initialize orchestrator
    orchestrator = Orchestrator(
        local_connector=local_connector,
        external_connectors=external_connectors,
        tools={},  # Tools can be added later
        cost_limit=100.0,  # High limit for API usage
        soft_cap_threshold=0.8,
    )
    app.state.orchestrator = orchestrator
    
    # Initialize reflection agent for continuous learning (always-on)
    memory_vault = None
    reflection_agent = None
    if local_connector:
        # Use a system user ID for API server reflections
        memory_vault = MemoryVault(user_id="api_server")
        reflection_agent = ReflectionAgent(local_connector, memory_vault)
        app.state.memory_vault = memory_vault
        app.state.reflection_agent = reflection_agent
        logger.info("Reflection agent initialized - continuous learning enabled")
    else:
        logger.warning("No local connector - reflection disabled for API server")
    
    logger.info("Orchestrator initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down API server")
    # Clean up resources if needed


# Create FastAPI app
app = FastAPI(
    title="Kai OpenAI-Compatible API",
    description="OpenAI-compatible chat completions API powered by Kai orchestrator",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Load configuration
config = APIConfig()
app.state.config = config

# Setup logging
setup_logging(
    log_level=config.get("logging.level", "INFO"),
    structured=False,
)

# Add CORS middleware
if config.get("cors.enabled", True):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.get("cors.allow_origins", ["*"]),
        allow_credentials=True,
        allow_methods=config.get("cors.allow_methods", ["GET", "POST", "OPTIONS"]),
        allow_headers=config.get("cors.allow_headers", ["Content-Type", "Authorization"]),
    )
    logger.info("CORS enabled")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with OpenAI-compatible error format."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "server_error",
                "param": None,
                "code": "internal_error",
            }
        },
    )


# Root endpoint
@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "message": "Kai OpenAI-Compatible API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "chat_completions": "/v1/chat/completions",
            "models": "/v1/models",
            "health": "/health",
        },
    }


# Import and register route handlers
from src.api.handlers.chat import (
    process_chat_completion,
    process_chat_completion_stream,
)
from src.api.handlers.models import list_models
from src.api.handlers.health import check_health
from src.api.models.chat import ChatCompletionRequest
from src.api.models.errors import invalid_request_error, server_error
from src.api.adapter import OrchestratorAdapter
from src.api.streaming import stream_openai_response
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse


# Chat completions endpoint
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint.
    
    Supports both streaming and non-streaming requests.
    """
    try:
        # Get orchestrator and reflection components from app state
        orchestrator = app.state.orchestrator
        reflection_agent = getattr(app.state, 'reflection_agent', None)
        memory_vault = getattr(app.state, 'memory_vault', None)
        
        # Initialize orchestrator adapter with reflection support
        adapter = OrchestratorAdapter(
            orchestrator_client=orchestrator,
            reflection_agent=reflection_agent,
            memory_vault=memory_vault,
        )
        
        # Handle streaming vs non-streaming
        if request.stream:
            # Return streaming response
            chunks = process_chat_completion_stream(request, config, adapter)
            sse_stream = stream_openai_response(chunks)
            
            return EventSourceResponse(
                sse_stream,
                media_type="text/event-stream",
            )
        else:
            # Return complete response
            response = await process_chat_completion(request, config, adapter)
            return response
            
    except ValueError as e:
        # Model not found or invalid request
        error_response = invalid_request_error(str(e))
        raise HTTPException(status_code=400, detail=error_response.model_dump())
        
    except RuntimeError as e:
        # Orchestrator error
        error_response = server_error(str(e))
        raise HTTPException(status_code=500, detail=error_response.model_dump())
        
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error in chat completions: {e}", exc_info=True)
        error_response = server_error("An unexpected error occurred")
        raise HTTPException(status_code=500, detail=error_response.model_dump())


# Models list endpoint
@app.get("/v1/models")
async def get_models():
    """OpenAI-compatible models list endpoint."""
    return list_models(config)


# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint."""
    return await check_health(config)


if __name__ == "__main__":
    import uvicorn
    
    server_config = config.get("server", {})
    
    uvicorn.run(
        "main:app",
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 9000),
        reload=server_config.get("reload", False),
        workers=1 if server_config.get("reload", False) else server_config.get("workers", 4),
        log_level=config.get("logging.level", "info").lower(),
    )
