from dotenv import load_dotenv
import os
import uuid
from typing import TypedDict

from models.ollama_client import load_model as ollama_model
from models.openai_client import run_openai
from models.gemini_client import run_gemini
from rag.chroma_client import get_chroma_collection
from rag.memory_view import load_memory, save_memory
from tools.tools import (
    summarize_text,
    extract_code,
    detect_language,
    token_count,
    estimate_cost,
    route_tool_model,
    call_llm,
)

from langgraph.graph import StateGraph, START, END

# Load .env
load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

# Default model fallback
default_model = "smollm2:1.7b"

# Load Ollama models
llm_smollm = ollama_model("smollm2:1.7b")
llm_gemma = ollama_model("gemma3n:e2b")

# Connect to ChromaDB
collection = get_chroma_collection()

# --- State definition ---
class State(TypedDict, total=False):
    model: str
    response: str
    user_input: str
    summarize: bool
    history: list[dict]
    memory_file: str
    retrieved_context: str

# --- Nodes ---
def load_memory_node(state: State) -> dict:
    file_name = state.get("memory_file", "memory.jsonb")
    history = load_memory(file_name)
    return {"history": history}

def chat_input_node(state: State) -> dict:
    user_input = input("You: ")
    return {"user_input": user_input}

def check_length_node(state: State) -> dict:
    history = state.get("history", [])
    return {"summarize": len(history) > 20}

def summarize_node(state: State) -> dict:
    history = state.get("history", [])
    chunk = history[:10]
    chunk_text = "\n".join(
        f"USER: {turn['user']}\nAI: {turn['ai']}" for turn in chunk
    )
    summary = llm_smollm.invoke("Summarize this:\n" + chunk_text)
    summary_md = {"source": "memory", "length": len(chunk_text)}
    unique_id = f"summary_{uuid.uuid4()}"
    collection.add(documents=[summary], metadatas=[summary_md], ids=[unique_id])
    return {"history": history[10:]}

def search_chroma_node(state: State) -> dict:
    query = state.get("user_input", "")
    results = collection.query(query_texts=[query], n_results=2)
    docs = results["documents"][0] if results["documents"] else []
    return {"retrieved_context": "\n".join(docs)}

def route_model_node(state: State) -> dict:
    user_input = state.get("user_input", "")
    return {"model": route_tool_model(user_input)}

def chat_llm_node(state: State) -> dict:
    history = state.get("history", [])
    context = state.get("retrieved_context", "")
    user_input = state.get("user_input", "")
    model = state.get("model", default_model)

    # Construct prompt
    history_text = "\n".join(
        f"USER: {turn['user']}\nAI: {turn['ai']}" for turn in history
    )
    prompt = f"{history_text}\nCONTEXT: {context}\nUSER: {user_input}\nAI:"

    print("\n--- LLM RUN ---")
    print("Model:", model)
    print("Prompt:\n", prompt[:300], "...\n")

    # Run based on model string
    if model.startswith("smollm") or model.startswith("gemma"):
        llm = ollama_model(model)
        response = llm.invoke(prompt)
    elif model == "gpt-4o":
        response = run_openai(prompt)
    elif model == "gemini":
        response = run_gemini(prompt)
    else:
        response = "Error: Unknown model selected."

    print("Response:\n", response)
    return {"response": response}

def update_memory_node(state: State) -> dict:
    history = state.get("history", [])
    user_input = state.get("user_input", "")
    response = state.get("response", "")
    history.append({"user": user_input, "ai": response})
    save_memory(history, state.get("memory_file", "memory.jsonb"))
    return {"history": history}

# --- Tool Nodes ---
def summarize_tool_node(state: State) -> dict:
    user_input = state.get("user_input", "")
    summary = summarize_text(user_input)
    return {"response": summary}

def extract_code_node(state: State) -> dict:
    return {"response": extract_code(state.get("user_input", ""))}

def detect_language_node(state: State) -> dict:
    return {"response": detect_language(state.get("user_input", ""))}

def token_count_node(state: State) -> dict:
    return {"response": token_count(state.get("user_input", ""))}

def estimate_cost_node(state: State) -> dict:
    return {"response": estimate_cost(state.get("user_input", ""))}

# --- Graph Build ---
graph = StateGraph(State)

graph.add_node("load_memory", load_memory_node)
graph.add_node("check_length", check_length_node)
graph.add_node("summarize", summarize_node)
graph.add_node("search_chroma", search_chroma_node)
graph.add_node("route_model", route_model_node)
graph.add_node("chat_llm", chat_llm_node)
graph.add_node("update_memory", update_memory_node)
graph.add_node("summarize_tool", summarize_tool_node)
graph.add_node("extract_code", extract_code_node)
graph.add_node("detect_language", detect_language_node)
graph.add_node("token_count", token_count_node)
graph.add_node("estimate_cost", estimate_cost_node)

graph.add_edge(START, "load_memory")
graph.add_edge("load_memory", "check_length")

graph.add_conditional_edges(
    "check_length",
    path=lambda state: "summarize" if state.get("summarize", False) else "search_chroma",
    path_map={
        "summarize": "summarize",
        "search_chroma": "search_chroma"
    }
)

graph.add_edge("summarize", "search_chroma")
graph.add_edge("search_chroma", "route_model")
graph.add_edge("route_model", "chat_llm")
graph.add_edge("chat_llm", "update_memory")
graph.add_edge("update_memory", END)

# Compile and run ready
runnable = graph.compile()