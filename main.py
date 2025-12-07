"""
FastAPI OpenAI-Compatible API Server

Provides OpenAI-compatible endpoints for chat completions, model listing,
and health checks. Routes requests to the existing orchestrator with
intelligent model selection.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.config import APIConfig
from src.lib.logger import setup_logging
from src.core.orchestrator import Orchestrator
from src.storage.sqlite_store import SQLiteStore
from src.storage.vector_store import VectorStore
from src.storage.memory_vault import MemoryVault
from src.agents.reflection_agent import ReflectionAgent
from src.feedback.rage_trainer import RageTrainer
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

    # Initialize Vector storage
    vector_store = VectorStore(db_path="data/vectors")
    app.state.vector_store = vector_store

    # Load Kai configuration for LLM settings
    kai_config = ConfigLoader()

    # Initialize LLM connectors
    local_connectors = {}
    external_connectors = {}
    primary_local_connector = None

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
            connector = OllamaProvider(config_dict, ollama_url)
            local_connectors[model_config.model_id] = connector
            logger.info(f"Initialized Ollama: {model_config.model_name}")
            
            # Set primary local connector (prefer high priority or first one)
            if not primary_local_connector or model_config.routing_priority > 9:
                primary_local_connector = connector

        elif model_config.provider == "openrouter":
            api_key = kai_config.get_env("openrouter_api_key")
            if api_key:
                connector = OpenRouterProvider(config_dict, api_key)
                external_connectors[model_config.model_id] = connector
                logger.info(f"Initialized OpenRouter: {model_config.model_name}")

    if not primary_local_connector:
        logger.error("No local connector initialized - API will not function properly")

    # Identify Planner and Narrator connectors based on config
    planner_model_id = kai_config.get_env("planner_model")
    narrator_model_id = kai_config.get_env("narrator_model")
    
    planner_connector = None
    narrator_connector = None
    
    # Find planner connector
    if planner_model_id:
        if planner_model_id in external_connectors:
            planner_connector = external_connectors[planner_model_id]
            logger.info(f"Planner configured: {planner_model_id}")
        elif planner_model_id in local_connectors:
            planner_connector = local_connectors[planner_model_id]
            logger.info(f"Planner configured: {planner_model_id} (Local)")
        else:
            logger.warning(f"Configured planner model {planner_model_id} not found in active connectors")
            
    # Find narrator connector
    if narrator_model_id:
        if narrator_model_id in external_connectors:
            narrator_connector = external_connectors[narrator_model_id]
            logger.info(f"Narrator configured: {narrator_model_id}")
        elif narrator_model_id in local_connectors:
            narrator_connector = local_connectors[narrator_model_id]
            logger.info(f"Narrator configured: {narrator_model_id} (Local)")
        else:
            logger.warning(f"Configured narrator model {narrator_model_id} not found in active connectors")

    # Initialize tools
    tools = {}
    enabled_tools = kai_config.get_enabled_tools()
    
    # Initialize web search tool
    if "web_search" in enabled_tools:
        try:
            from src.tools.web_search import WebSearchTool
            tool_config = enabled_tools["web_search"]
            web_search_config = {
                "max_results": tool_config.config.get("max_results", 10),
                "timeout_seconds": tool_config.config.get("timeout_seconds", 15),
                "max_days_old": tool_config.config.get("max_days_old", 30),
                "api_key": kai_config.get_env("brave_api_key"),
                "tavily_api_key": kai_config.get_env("tavily_api_key"),
            }
            tools["web_search"] = WebSearchTool(web_search_config)
            logger.info("WebSearchTool initialized for API server")
        except Exception as e:
            logger.error(f"Failed to initialize WebSearchTool: {e}")
    
    # Initialize memory vault and reflection agent BEFORE orchestrator
    memory_vault = None
    reflection_agent = None
    rage_trainer = None
    if primary_local_connector:
        # Use a system user ID for API server reflections
        memory_vault = MemoryVault(user_id="api_server")
        reflection_agent = ReflectionAgent(primary_local_connector, memory_vault)
        rage_trainer = RageTrainer(memory_vault)
        app.state.memory_vault = memory_vault
        app.state.reflection_agent = reflection_agent
        app.state.rage_trainer = rage_trainer
        logger.info("Reflection agent initialized - continuous learning enabled")
    else:
        logger.warning("No local connector - reflection disabled for API server")

    # Initialize orchestrator
    orchestrator = Orchestrator(
        local_connector=primary_local_connector,
        external_connectors=external_connectors,
        tools=tools,
        cost_limit=100.0,  # High limit for API usage
        soft_cap_threshold=0.8,
        sqlite_store=storage,
        vector_store=vector_store,
        planner_connector=planner_connector,
        narrator_connector=narrator_connector,
        memory_vault=memory_vault,
    )

    # Inject conversation service for memory (create simple conversation service for API)
    from src.core.conversation_service import ConversationService

    conversation_service = ConversationService(storage)
    orchestrator.conversation_service = conversation_service
    app.state.conversation_service = conversation_service

    app.state.orchestrator = orchestrator

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

# Add request logging middleware
from src.api.middleware.request_logger import RequestLoggerMiddleware

app.add_middleware(RequestLoggerMiddleware)
logger.info("Request logging middleware enabled")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with OpenAI-compatible error format."""
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)

    # Detect specific error types and provide helpful messages
    error_message = "Internal server error"
    error_code = "internal_error"

    if "Ollama" in str(exc) or "ollama" in str(exc).lower():
        error_message = "AI model service (Ollama) unavailable. Please ensure Ollama is running."
        error_code = "model_unavailable"
    elif "connection" in str(exc).lower() or "timeout" in str(exc).lower():
        error_message = "Connection to AI model failed. Service may be down or overloaded."
        error_code = "connection_error"
    elif "not found" in str(exc).lower():
        error_message = "Requested model not found. Check available models at /v1/models"
        error_code = "model_not_found"

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": error_message,
                "type": "server_error",
                "param": None,
                "code": error_code,
                "details": str(exc) if logger.level <= logging.DEBUG else None,
            }
        },
    )


# HTTPException handler - unwrap ErrorResponse from detail
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException and unwrap ErrorResponse from detail.

    FastAPI wraps HTTPException.detail in {"detail": ...}, but OpenAI format
    expects errors at the top level as {"error": {...}}.
    """
    # If detail is a dict with 'error' key (ErrorResponse), unwrap it
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,  # Already has {"error": {...}} structure
        )

    # Otherwise, wrap plain detail in error format
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": str(exc.detail),
                "type": "api_error",
                "param": None,
                "code": None,
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
from src.api.handlers.memory_import import router as memory_router
from src.api.handlers.rage_feedback import router as rage_router
from src.api.handlers.tts import router as tts_router
from src.api.handlers.deepgram_stt import router as stt_router
from src.api.models.chat import ChatCompletionRequest
from src.api.models.errors import invalid_request_error, server_error
from src.api.adapter import OrchestratorAdapter
from src.api.streaming import stream_openai_response
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

# Include routers
app.include_router(memory_router)
app.include_router(rage_router)
app.include_router(tts_router)  # Google TTS
app.include_router(stt_router)  # Deepgram STT


# Chat completions endpoint
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, http_request: Request = None):
    """OpenAI-compatible chat completions endpoint.

    Supports both streaming and non-streaming requests.
    Accepts X-Rage-Feedback header for instant learning.
    """
    try:
        # Get orchestrator and reflection components from app state
        orchestrator = app.state.orchestrator
        reflection_agent = getattr(app.state, "reflection_agent", None)
        memory_vault = getattr(app.state, "memory_vault", None)
        rage_trainer = getattr(app.state, "rage_trainer", None)

        # Check for rage feedback header
        if http_request and rage_trainer:
            rage_emoji = http_request.headers.get("X-Rage-Feedback")
            if rage_emoji in ["😭", "🤓", "💀"]:
                await rage_trainer.record_reaction(rage_emoji)

        # Initialize orchestrator adapter with reflection support
        adapter = OrchestratorAdapter(
            orchestrator_client=orchestrator,
            reflection_agent=reflection_agent,
            memory_vault=memory_vault,
        )

        # Handle streaming vs non-streaming
        if request.stream:
            # Return streaming response (already SSE formatted)
            sse_stream = process_chat_completion_stream(request, config, adapter)

            return EventSourceResponse(
                sse_stream,
                media_type="text/event-stream",
            )
        else:
            # Return complete response
            response = await process_chat_completion(request, config, adapter)

            # Extract metadata for headers
            metadata = response.model_dump().get("_metadata", {})

            # Create JSONResponse with custom headers
            from fastapi.responses import JSONResponse as FastAPIJSONResponse

            response_dict = response.model_dump(exclude={"_metadata"})

            return FastAPIJSONResponse(
                content=response_dict,
                headers={
                    "X-Model-Used": metadata.get("model_used", ""),
                    "X-Cost": str(metadata.get("cost", 0.0)),
                },
            )

    except ValueError as e:
        # Model not found or invalid request
        logger.warning(f"Invalid request: {e}")
        error_response = invalid_request_error(str(e))
        raise HTTPException(status_code=400, detail=error_response.model_dump())

    except RuntimeError as e:
        # Orchestrator error - provide helpful context
        error_msg = str(e)
        if "Ollama" in error_msg:
            error_msg = f"Ollama service error: {error_msg}. Ensure Ollama is running and the model is loaded."

        logger.error(f"Runtime error: {error_msg}")
        error_response = server_error(error_msg)
        raise HTTPException(status_code=503, detail=error_response.model_dump())

    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error in chat completions: {e}", exc_info=True)
        error_response = server_error(
            "An unexpected error occurred. Check logs for details."
            if logger.level > logging.DEBUG
            else f"Error: {str(e)}"
        )
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
    ssl_config = server_config.get("ssl", {})

    # Build uvicorn kwargs
    uvicorn_kwargs = {
        "app": "main:app",
        "host": server_config.get("host", "0.0.0.0"),
        "port": server_config.get("port", 9000),
        "reload": server_config.get("reload", False),
        "workers": 1 if server_config.get("reload", False) else server_config.get("workers", 4),
        "log_level": config.get("logging.level", "info").lower(),
    }

    # Add SSL configuration if enabled
    if ssl_config.get("enabled", False):
        ssl_certfile = ssl_config.get("certfile")
        ssl_keyfile = ssl_config.get("keyfile")
        ssl_ca_certs = ssl_config.get("ca_certs")

        if ssl_certfile and ssl_keyfile:
            uvicorn_kwargs["ssl_certfile"] = ssl_certfile
            uvicorn_kwargs["ssl_keyfile"] = ssl_keyfile
            if ssl_ca_certs:
                uvicorn_kwargs["ssl_ca_certs"] = ssl_ca_certs
            logger.info(f"🔒 HTTPS enabled with certificate: {ssl_certfile}")
        else:
            logger.warning("⚠️  SSL enabled but certfile/keyfile not configured - falling back to HTTP")

    uvicorn.run(**uvicorn_kwargs)
