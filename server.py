
import os
import time
import logging
from typing import List, Dict, Optional

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Reuse our OpenRouter client
from models.openrouter_client import chat as or_chat
from models.openrouter_client import stream_chat as or_stream
# Tool routing
from tools.tools import route_tool_model, call_llm
# Import Ollama client
from models import ollama_client

# ------------------------------------------------------------
# App setup
# ------------------------------------------------------------
app = FastAPI(title="Kai OpenAI-Compatible API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
# Helpful debug context (non-sensitive): show memory backend + injection flag at startup
try:
    logger.debug("ENV memory backend=%s, memory inject=%s", os.getenv("MEMORY_BACKEND"), os.getenv("ENABLE_MEMORY_INJECT"))
except Exception:
    pass
OPENROUTER_KEY = os.getenv("OPEN_ROUTER_KEY", "")

# ------------------------------------------------------------
# Schemas (OpenAI-like)
# ------------------------------------------------------------
class OpenAIMessage(BaseModel):
    role: str
    content: str

class OpenAIChatRequest(BaseModel):
    model: str
    messages: List[OpenAIMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False  # not implemented yet

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _openai_response(model: str, content: str) -> Dict:
    now = int(time.time())
    return {
        "id": f"chatcmpl-{now}",
        "object": "chat.completion",
        "created": now,
        "model": model,
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": content}
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": len(content.split()), "total_tokens": len(content.split())}
    }

# SSE helpers for streaming
def _sse_head(model: str) -> dict:
    now = int(time.time())
    return {
        "id": f"chatcmpl-{now}",
        "object": "chat.completion.chunk",
        "created": now,
        "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]
    }

async def _sse_from_text(model: str, content: str):
    yield f"data: {JSONResponse(_sse_head(model)).body.decode()}\n\n"
    for token in content.split():
        chunk = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {"content": token + " "}, "finish_reason": None}]
        }
        yield f"data: {JSONResponse(chunk).body.decode()}\n\n"
    tail = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
    }
    yield f"data: {JSONResponse(tail).body.decode()}\n\n"
    yield "data: [DONE]\n\n"

async def _sse_from_openrouter(model: str, gen):
    yield f"data: {JSONResponse(_sse_head(model)).body.decode()}\n\n"
    async for delta in gen:
        chunk = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]
        }
        yield f"data: {JSONResponse(chunk).body.decode()}\n\n"
    tail = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
    }
    yield f"data: {JSONResponse(tail).body.decode()}\n\n"
    yield "data: [DONE]\n\n"

# Helper to join OpenAI-style messages into a plain prompt
def _messages_to_prompt(messages: List[OpenAIMessage]) -> str:
    lines = []
    for m in messages:
        lines.append(f"{m.role.upper()}: {m.content}")
    lines.append("ASSISTANT:")
    return "\n".join(lines)

# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/v1/models")
async def list_models():
    data = [
        {"id": "gpt-5", "object": "model"},
        {"id": "openrouter:oss-120b", "object": "model"},
        {"id": "kai-local:smollm2:1.7b", "object": "model"},
        {"id": "kai-local:phi4-mini:3.8b", "object": "model"},
        {"id": "kai-local:deepseek-coder:1.3b", "object": "model"},
        {"id": "kai-graph:default", "object": "model"},
        # {"id": "kai-local:gemma3-12b", "object": "model"},
    ]
    return {"object": "list", "data": data}

@app.post("/v1/chat/completions")
async def chat_completions(req: OpenAIChatRequest = Body(...)):
    model = req.model.lower()

    # Route to OpenRouter models when prefixed with openrouter:
    if model.startswith("openrouter:"):
        provider_model = model.split("openrouter:", 1)[1]
        if req.stream:
            return StreamingResponse(
                _sse_from_openrouter(
                    req.model,
                    or_stream(provider_model, [m.dict() for m in req.messages], temperature=req.temperature, max_tokens=req.max_tokens)
                ),
                media_type="text/event-stream"
            )
        text = await or_chat(provider_model, [m.dict() for m in req.messages], temperature=req.temperature, max_tokens=req.max_tokens)
        return JSONResponse(_openai_response(req.model, text))

    # Default: treat unprefixed gpt-5 as OpenRouter's gpt-5
    if model in ("gpt-5", "openai/gpt-5"):
        if req.stream:
            return StreamingResponse(
                _sse_from_openrouter(
                    req.model,
                    or_stream("openai/gpt-5", [m.dict() for m in req.messages], temperature=req.temperature, max_tokens=req.max_tokens)
                ),
                media_type="text/event-stream"
            )
        text = await or_chat("openai/gpt-5", [m.dict() for m in req.messages], temperature=req.temperature, max_tokens=req.max_tokens)
        return JSONResponse(_openai_response(req.model, text))

    # Local Ollama models via kai-local:* prefix
    if model.startswith("kai-local:"):
        ollama_slug = req.model.split("kai-local:", 1)[1]
        prompt = _messages_to_prompt(req.messages)
        if req.stream:
            text = ollama_client.invoke(ollama_slug, prompt)
            return StreamingResponse(_sse_from_text(req.model, text), media_type="text/event-stream")
        text = ollama_client.invoke(ollama_slug, prompt)
        return JSONResponse(_openai_response(req.model, text))

    # Graph model path
    if model == "kai-graph:default":
        from tools.tools import run_kai_router
        # Debug log to indicate memory injection settings (best-effort)
        use_inject = os.getenv("ENABLE_MEMORY_INJECT", "true").lower() == "true"
        budget = int(os.getenv("MEMORY_TOKENS", "800"))
        if use_inject:
            try:
                logger.debug("Memory injection enabled; token budget=%s", budget)
            except Exception:
                pass
        result = await run_kai_router([m.dict() for m in req.messages])
        text = result.get("answer", "")
        if req.stream:
            return StreamingResponse(_sse_from_text(req.model, text), media_type="text/event-stream")
        return JSONResponse(_openai_response(req.model, text))

    # Not wired yet (placeholder so testers get a clean error)
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "message": f"Model '{req.model}' is not routed yet. Use 'openrouter:oss-120b' or 'gpt-5' to test.",
                "type": "model_not_routed",
            }
        },
    )

# Note: streaming SSE can be added next by plumbing models.openrouter_client.stream_chat
