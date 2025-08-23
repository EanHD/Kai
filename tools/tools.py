import json
from anyio import to_thread
from typing import Dict, List, Tuple

import re
import os
try:
    import tiktoken
except Exception:
    tiktoken = None
from langdetect import detect
from models.ollama_client import load_model as ollama_model
from models.openai_client import run_openai
from models.gemini_client import run_gemini

from models.openrouter_client import chat as or_chat

# Optional memory injection helper (best-effort import)
try:
    from memory.store import inject_relevant_memory
except Exception:
    inject_relevant_memory = None

from rag.chroma_client import get_chroma_collection, docs_collection, facts_collection, transcripts_collection
# --- Retrieval helper ---
def retrieve_context(query: str, k: int = 6) -> str:
    """Query all memory layers and return a compact stitched context with lightweight citations."""
    ctx_parts = []
    for col, tag in ((docs_collection(), "doc"), (facts_collection(), "fact"), (transcripts_collection(), "transcript")):
        try:
            res = col.query(query_texts=[query], n_results=min(k, 3))
            for txt, meta in zip(res.get("documents", [[]])[0], res.get("metadatas", [[]])[0]):
                cite = meta.get("filename") or meta.get("title") or tag
                ctx_parts.append(f"[{tag}:{cite}] {txt}")
        except Exception:
            continue
    return "\n".join(ctx_parts[:k])

# Load Ollama models
ollama_default = ollama_model("smollm2:1.7b")
ollama_gemma = ollama_model("gemma3n:e2b")

# --- Model override and hint sets ---
BACKTICK_MAP = {
    "`kai": "smollm2:1.7b",
    "`phi": "phi4-mini:3.8b",
    "`code": "deepseek-coder:1.3b",
    "`oss": "openai/gpt-oss-120b",
    "`gpt": "openai/gpt-5",
}

CODE_HINTS = {"code", "function", "snippet", "bug", "fix", "refactor", "class", "test", "pytest", "regex"}
PLAN_HINTS = {"plan", "roadmap", "milestone", "timeline", "architecture", "design"}
RESEARCH_HINTS = {"research", "compare", "trade-off", "sources", "citations", "study"}
MATH_HINTS = {"math", "calculate", "compute", "derivative", "integral", "proof"}

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
    """
    Return an approximate token count for `text`. Prefer tiktoken when available,
    fall back to a word-count approximation otherwise.
    """
    if tiktoken is None:
        # Fallback: approximate tokens by word count
        return len(_tokenize(text))
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            return len(_tokenize(text))
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

# --- Analysis helpers ---

def _estimate_complexity(text: str) -> int:
    length = len(text)
    codey = any(k in text.lower() for k in CODE_HINTS)
    if length < 200 and not codey:
        return 1
    if length < 800 and not codey:
        return 2
    if codey and length < 500:
        return 3
    if length < 1800:
        return 3
    return 4

def _classify_intent(text: str) -> str:
    low = text.lower()
    if any(k in low for k in CODE_HINTS):
        return "code_small" if len(text) < 800 else "code_large"
    if any(k in low for k in PLAN_HINTS):
        return "plan"
    if any(k in low for k in RESEARCH_HINTS):
        return "research"
    if "rewrite" in low or "format" in low or "polish" in low:
        return "format/rewrite"
    if "explain" in low or "why" in low or "how" in low:
        return "explain"
    return "chat"

def _needs(text: str) -> List[str]:
    needs = []
    low = text.lower()
    if any(k in low for k in CODE_HINTS):
        needs.append("needs_code")
    if any(k in low for k in RESEARCH_HINTS):
        needs.append("needs_web/research")
    if any(k in low for k in MATH_HINTS):
        needs.append("needs_math")
    return needs

# --- Model chooser ---
def _choose_model(complexity: int, intent: str, text: str) -> str:
    low = text.lower()
    # Local first
    if complexity <= 1 and intent in {"chat", "explain", "format/rewrite"}:
        return "smollm2:1.7b"
    if complexity <= 3 and intent in {"explain", "plan"} and "code" not in low:
        return "phi4-mini:3.8b"
    if intent in {"code_small"}:
        return "deepseek-coder:1.3b"
    # Cloud for bigger jobs
    if complexity in {3, 4} and intent in {"plan", "explain", "code_large", "research"}:
        return "openai/gpt-oss-120b"
    if complexity >= 4 or "safety" in low:
        return "openai/gpt-5"
    # Fallback
    return "smollm2:1.7b"

# --- RAG helpers ---
def rag_should_add(answer: str) -> bool:
    # Save only durable, valuable content. Simple heuristic for now.
    long_enough = len(answer) > 500
    contains_code = "```" in answer
    looks_guide = any(k in answer.lower() for k in ["steps:", "checklist", "endpoint", "how to", "playbook", "command:"])
    return long_enough or looks_guide or contains_code

def rag_add_entry(title: str, tags: List[str], source: str, summary: str, content: str, confidence: float = 0.6) -> Dict:
    col = get_chroma_collection("kai_rag")
    doc_id = f"rag-{abs(hash(title + summary))}"
    col.add(ids=[doc_id], documents=[content], metadatas=[{"title": title, "tags": tags, "source": source, "summary": summary, "confidence": confidence}])
    return {
        "RAG_ADD": {
            "title": title,
            "tags": tags,
            "source": source,
            "summary": summary,
            "content": content,
            "confidence": confidence
        }
    }

# --- Async LLM dispatcher for kai-graph ---
async def call_llm_async(model: str, prompt: str) -> str:
    # Local Ollama models
    if model.startswith("smollm") or model.startswith("phi4-mini") or model.startswith("deepseek-coder") or model.startswith("gemma"):
        return await to_thread.run_sync(ollama_model(model).invoke, prompt)
    # Cloud via OpenRouter
    if model == "openai/gpt-oss-120b":
        return await or_chat("openai/gpt-oss-120b", [{"role": "user", "content": prompt}])
    if model == "openai/gpt-5":
        return await or_chat("openai/gpt-5", [{"role": "user", "content": prompt}])
    # Fallback to OpenAI client if specified
    if model == "gpt-4o":
        return run_openai(prompt)
    return "Unknown model."

# --- Main dynamic router (async for kai-graph) ---
async def run_kai_router(messages: List[Dict]) -> Dict:
    # Build a simple combined prompt from OpenAI-style messages
    text = "\n".join([f"{m.get('role','user').upper()}: {m.get('content','')}" for m in messages])
    text += "\nASSISTANT:"
    raw_user = messages[-1]["content"] if messages else ""
    low = raw_user.lower()

    # Memory injection (optional, controlled by env vars)
    try:
        turn_text = raw_user
        use_inject = os.getenv("ENABLE_MEMORY_INJECT", "true").lower() == "true"
        budget = int(os.getenv("MEMORY_TOKENS", "800"))
        injected = ""
        if use_inject and inject_relevant_memory is not None:
            try:
                injected = inject_relevant_memory(turn_text, token_budget=budget)
            except Exception:
                injected = ""
        preface = f"### Relevant Memory\n{injected}\n\n" if injected else ""
        if preface:
            text = preface + text
    except Exception:
        # Best-effort: do not fail routing if memory injection has issues
        pass

    # Lightweight heuristic: pull RAG if user references docs/projects or asks how/why
    used_rag = False
    if any(x in low for x in ["doc", "spec", "guide", "readme", "notes", "project", "why", "how"]):
        rag_ctx = retrieve_context(raw_user, k=6)
        if rag_ctx:
            used_rag = True
            text = f"CONTEXT (from memory):\n{rag_ctx}\n\n---\n" + text

    # Backtick override
    for k, v in BACKTICK_MAP.items():
        if low.startswith(k + " ") or low == k:
            chosen = v
            break
    else:
        # Analyze and choose dynamically
        complexity = _estimate_complexity(raw_user)
        intent = _classify_intent(raw_user)
        needs = _needs(raw_user)
        chosen = _choose_model(complexity, intent, raw_user)

    # Call primary model
    primary_text = await call_llm_async(chosen, text)

    # Style pass unless user said raw
    final_text = primary_text
    if " raw" not in low and "\nraw" not in low and not low.strip().endswith("raw"):
        final_text = await call_llm_async("smollm2:1.7b", f"Polish this for clarity and friendly tone without changing technical content.\n\n---\n{primary_text}")

    # Decide RAG add
    rag_block = None
    will_add = rag_should_add(final_text)
    if will_add:
        title = (raw_user[:60] + "…") if len(raw_user) > 60 else raw_user
        tags = ["router/auto", f"model/{chosen}"]
        summary = final_text[:160]
        rag_block = rag_add_entry(title, tags, source="kai", summary=summary, content=final_text, confidence=0.6)

    # Build analysis
    if 'complexity' not in locals():
        complexity = _estimate_complexity(raw_user)
        intent = _classify_intent(raw_user)
        needs = _needs(raw_user)

    result = {
        "analysis": {
            "complexity": complexity,
            "intent": intent,
            "needs": needs,
            "chosen_model": (
                "smollm2" if chosen.startswith("smollm2") else
                "phi4-mini" if chosen.startswith("phi4-mini") else
                "deepseek-coder-1.3b" if chosen.startswith("deepseek-coder") else
                "oss-120b" if "oss-120b" in chosen else
                "gpt-5" if "gpt-5" in chosen else chosen
            ),
            "used_rag": used_rag,
            "will_add_to_rag": will_add
        },
        "answer": final_text,
    }
    if rag_block:
        result["rag_add"] = rag_block["RAG_ADD"]
    return result
