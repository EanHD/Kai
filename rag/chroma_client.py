import os
import hashlib
from typing import Callable, Optional

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

_EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
_OPENAI_KEY = os.getenv("OPENAI_API_KEY")
_CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma")

# Cache the client and embedding function so we don't re-init every call
_client: Optional[chromadb.PersistentClient] = None
_embedder: Optional[Callable] = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=_CHROMA_PATH)
    return _client


def _get_embedder() -> Optional[Callable]:
    """Return an embedding function for Chroma (OpenAI by default).
    If OPENAI_API_KEY isn't set, returns None (Chroma will expect pre-embedded vectors).
    """
    global _embedder
    if _embedder is not None:
        return _embedder
    if _OPENAI_KEY:
        _embedder = OpenAIEmbeddingFunction(api_key=_OPENAI_KEY, model_name=_EMBED_MODEL)
    else:
        _embedder = None
    return _embedder


def get_collection(name: str):
    client = _get_client()
    embedder = _get_embedder()
    if embedder is None:
        # Falls back to no embedding function; callers must provide vectors
        return client.get_or_create_collection(name=name)
    return client.get_or_create_collection(name=name, embedding_function=embedder)

# --- Backward compatibility: alias for get_chroma_collection ---
def get_chroma_collection(name: str):
    """Backward-compat alias. Some modules still import get_chroma_collection."""
    return get_collection(name)


# Convenience handles for Kai's memory layers

def facts_collection():
    return get_collection("kai_facts")


def persona_collection():
    return get_collection("kai_persona")


def transcripts_collection():
    return get_collection("kai_transcripts")


def docs_collection():
    return get_collection("kai_docs")


def make_chunk_id(source: str, text: str) -> str:
    h = hashlib.sha256((source + "\n" + text).encode("utf-8")).hexdigest()[:16]
    return f"{source}:{h}"