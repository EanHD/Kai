# kai/tools/tools.py

import re
import os
import tiktoken
from langdetect import detect
from models.ollama_client import load_model as ollama_model
from models.openai_client import run_openai
from models.gemini_client import run_gemini

# Load Ollama models
ollama_default = ollama_model("smollm2:1.7b")
ollama_gemma = ollama_model("gemma3n:e2b")

# --- Basic Tools ---

def summarize_text(text: str) -> str:
    """Uses smollm to summarize given text."""
    prompt = f"Summarize the following:\n{text}"
    return ollama_default.invoke(prompt)

def extract_code(text: str) -> list[str]:
    """Extracts code blocks from triple backticks."""
    return re.findall(r"```(?:\w*\n)?(.*?)```", text, re.DOTALL)

def detect_language(text: str) -> str:
    try:
        return detect(text)
    except:
        return "unknown"

def token_count(text: str, model: str = "gpt-4o") -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

def estimate_cost(text: str, model: str = "gpt-4o") -> float:
    tokens = token_count(text, model)
    price_per_1k = {
        "gpt-4o": 0.005,
        "gpt-4": 0.03,
        "gpt-3.5-turbo": 0.0015,
    }
    return round(tokens / 1000 * price_per_1k.get(model, 0.005), 4)

def route_tool_model(text: str) -> str:
    """Simple model routing logic based on content."""
    if text.startswith("`gpt "):
        return "gpt-4o"
    if text.startswith("`gemini "):
        return "gemini"
    if text.startswith("`kai "):
        return "smollm2:1.7b" if len(text) <= 1000 else "gemma3n:e2b"
    if "research" in text.lower() or "explain" in text.lower():
        return "gemini"
    if "write code" in text.lower() or "debug" in text.lower():
        return "gpt-4o"
    if "```" in text or len(text) > 1000:
        return "gemma3n:e2b"
    return "smollm2:1.7b"

def call_llm(model: str, prompt: str) -> str:
    """Central dispatch for LLM calls."""
    if model.startswith("smollm") or model.startswith("gemma"):
        return ollama_model(model).invoke(prompt)
    elif model == "gpt-4o":
        return run_openai(prompt)
    elif model == "gemini":
        return run_gemini(prompt)
    else:
        return "Unknown model."