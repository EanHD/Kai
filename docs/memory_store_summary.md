Summary of memory/store.py

Purpose
-------
A compact, pure-Python Memory subsystem that provides a single source-of-truth for Kai's long- and short-term memories. Default storage is SQLite (file ./kai_memory.db). Optionally uses Chroma when MEMORY_BACKEND=chroma and chromadb is available. Embeddings use sentence-transformers when available, otherwise a deterministic hashing fallback.

Key behaviors
-------------
- Single canonical storage (no duplicated writes).
- Deduplication by normalized sha256 hash of (type, normalized_text, anchors).
- Per-item TTL defaults and exponential decay applied to relevance scoring.
- Hybrid retrieval: dense (embedding cosine) + sparse (FTS5 or token-overlap), with deterministic fusion.
- Small, stable API surface to be used by server/tools modules.

Public types
------------
- MemoryItem: Pydantic-like model representing a memory item with these fields:
    id: Optional[str]
    type: str
    text: str
    metadata: Dict[str, Any]
    created_at: Optional[float]
    last_seen: Optional[float]
    ttl: Optional[float]
    decay: float
    source: Optional[str]
    hash: Optional[str]
    embedding: Optional[List[float]]

Public functions (signatures)
-----------------------------
- remember(item: MemoryItem, anchors: Optional[List[str]] = None) -> str
  Store a memory item (compute embedding if missing). Deduplicates by hash; if duplicate, updates last_seen and merges metadata. Returns the stored id.

- recall(query: str, k: int = 8, filters: Optional[Dict[str, Any]] = None) -> List[MemoryItem]
  Hybrid retrieval: computes query embedding, scores items by dense cosine and sparse token/FTS match, normalizes both, fuses via score = 0.7*dense + 0.3*sparse, applies exponential time decay and TTL filtering, applies optional type/metadata filters. Returns up to k MemoryItem objects (and updates last_seen for returned items).

- update(id: str, patch: Dict[str, Any]) -> bool
  Patch fields on an existing memory (text, type, metadata, ttl, decay, last_seen, embedding). Returns True if an update occurred.

- forget(id: str) -> bool
  Hard-delete a memory by id. Returns True if deleted.

- gc() -> int
  Garbage-collect hard-expired items (TTL exceeded). Returns number of deleted items.

- snapshot(session_id: Optional[str] = None) -> str
  Export stored memories as JSON string. When session_id provided, only export items whose metadata.session == session_id.

- restore(snapshot_json: str) -> int
  Restore/ingest items from a snapshot JSON string. Returns number of inserted items (deduped via remember()).

- inject_relevant_memory(turn: str, token_budget: int = 500) -> str
  Build a compact, token-budget-limited context block from relevant memories to prepend to agent prompts. Token budget approximated by word count.

- fusion_score(dense: float, sparse: float, alpha: float = 0.7) -> float
  Deterministic re-ranker used for unit tests and clarity: returns alpha * dense + (1-alpha) * sparse.

Backend selection
-----------------
- MEMORY_BACKEND environment variable selects backend: "sqlite" (default) or "chroma".
- SQLite backend implemented fully in this module. Chroma backend is detected but falls back to SQLite unless chromadb wiring is later added.

Notable implementation details
------------------------------
- Embeddings: sentence-transformers ("all-MiniLM-L6-v2") used if present; otherwise a deterministic 32-d vector derived from sha256 bytes (fast no-deps fallback).
- Sparse retrieval: uses SQLite FTS5 if available; otherwise token Jaccard on text+metadata.
- TTL defaults per type (FACT long, SCRATCH short, etc.) configurable in _TTL_DEFAULTS.
- Decay: exponential decay multiplier exp(-decay * days_since(last_seen)).
- Deduplication: _make_hash(type, text, anchors) normalized to lower-case, collapsed whitespace.
- API keeps functions small and composable for easy testing and integration.

Tests included
--------------
Unit tests (tests/test_memory.py) exercise:
- Deduplication behavior
- TTL + gc
- Fusion re-ranking
- Snapshot/restore
- inject_relevant_memory smoke behavior

Usage notes
-----------
- Import the module: from memory import store as mem
- Example:
    from memory.store import MemoryItem, remember, recall
    mi = MemoryItem(type="FACT", text="The sky is blue.")
    id = remember(mi)
    results = recall("color of sky", k=3)

This file is a concise reference for the memory/store.py module created in this change set.
