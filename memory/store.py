"""
Memory subsystem for Kai.

Provides a small, stable Memory API:
  - remember(item: MemoryItem) -> str
  - recall(query: str, k: int = 8, filters: dict | None = None) -> List[MemoryItem]
  - update(id: str, patch: dict) -> bool
  - forget(id: str) -> bool
  - gc() -> int
  - snapshot(session_id: str | None) -> str (JSON)
  - restore(snapshot_json: str) -> int
  - inject_relevant_memory(turn: str, token_budget: int = 500) -> str

Design choices:
- Default backend: SQLite (file: ./kai_memory.db)
- Optional backend: Chroma if MEMORY_BACKEND=chroma and chromadb import available.
- Embeddings: sentence-transformers if available, otherwise a lightweight hashing fallback.
- Sparse scoring: simple token-overlap scoring (fast and dependency-free). If SQLite has FTS5, we also populate an FTS table as an optimization but do not depend on it.
- Fusion ranking: deterministic score = 0.7 * dense + 0.3 * sparse
- TTL & decay: per-item TTL + exponential time decay applied to final score; GC removes hard-expired items.
- Dedup: normalized sha256 hash of (type, normalized_text, anchor_keys).
"""

from __future__ import annotations

import os
import time
import json
import math
import sqlite3
import hashlib
import threading
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

try:
    from pydantic import BaseModel, Field
except Exception:
    # Minimal fallback - lightweight dataclass wrapper if pydantic absent
    BaseModel = object
    Field = lambda *a, **k: None

# Try to import sentence-transformers; fall back to hashing embedder
try:
    from sentence_transformers import SentenceTransformer
    _SENTENCE_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
except Exception:
    _SENTENCE_MODEL = None

# Feature flag: choose backend via env var MEMORY_BACKEND={sqlite,chroma}
_MEMORY_BACKEND = os.getenv("MEMORY_BACKEND", "sqlite").lower()
_DB_PATH = os.getenv("KAI_MEMORY_DB", "./kai_memory.db")
_LOCK = threading.RLock()


# ---------------------------
# Schemas
# ---------------------------
class MemoryItem(BaseModel):
    """
    Memory item schema.

    Fields:
        id: optional unique id (if not provided, created from hash)
        type: one of FACT, PERSONAL_PREF, SESSION, TRANSCRIPT, TASK, TOOL_OUTPUT, SCRATCH
        text: primary textual content
        metadata: free-form dict
        created_at: unix ts
        last_seen: unix ts
        ttl: seconds (None means infinite)
        decay: float decay rate per day (how fast relevance decays)
        source: origin string
        hash: dedup hash (sha256)
    """
    id: Optional[str] = Field(default=None)
    type: str = Field(default="SCRATCH")
    text: str = Field(default="")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[float] = Field(default=None)
    last_seen: Optional[float] = Field(default=None)
    ttl: Optional[float] = Field(default=None)
    decay: float = Field(default=0.0)
    source: Optional[str] = Field(default=None)
    hash: Optional[str] = Field(default=None)
    embedding: Optional[List[float]] = Field(default=None)


# ---------------------------
# Utilities
# ---------------------------
def _now() -> float:
    return time.time()


def _normalize_text(t: str) -> str:
    return " ".join(t.strip().split()).lower()


def _make_hash(item_type: str, text: str, anchors: Optional[List[str]] = None) -> str:
    norm = _normalize_text(text)
    parts = [item_type.strip().lower(), norm]
    if anchors:
        parts.extend(a.strip().lower() for a in anchors)
    h = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return h


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    sa = math.sqrt(sum(x * x for x in a))
    sb = math.sqrt(sum(y * y for y in b))
    if sa == 0 or sb == 0:
        return 0.0
    return num / (sa * sb)


def _tokenize(text: str) -> List[str]:
    return [t for t in _normalize_text(text).split() if t]


def _jaccard_score(a: List[str], b: List[str]) -> float:
    sa = set(a)
    sb = set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _days_since(ts: float) -> float:
    return max(0.0, (_now() - ts) / 86400.0)


def _embedding_for(text: str) -> List[float]:
    if _SENTENCE_MODEL is not None:
        vec = _SENTENCE_MODEL.encode(text, convert_to_numpy=False).tolist()
        return [float(x) for x in vec]
    # fallback: deterministic small vector based on sha256 -> floats
    h = hashlib.sha256(text.encode("utf-8")).digest()
    # create 32-d vector from bytes
    return [((b / 255.0) * 2.0 - 1.0) for b in h[:32]]


# ---------------------------
# SQLite storage implementation (default)
# ---------------------------
class _SQLiteBackend:
    def __init__(self, path: str = _DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                type TEXT,
                text TEXT,
                metadata TEXT,
                created_at REAL,
                last_seen REAL,
                ttl REAL,
                decay REAL,
                source TEXT,
                hash TEXT,
                embedding TEXT
            )
            """
        )
        # Optional FTS table for quick sparse match (if SQLite compiled with FTS5).
        try:
            cur.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(id, text, metadata)"
            )
        except sqlite3.OperationalError:
            # FTS unavailable; that's OK.
            pass
        self.conn.commit()

    def upsert(self, item: MemoryItem) -> str:
        with _LOCK:
            cur = self.conn.cursor()
            item_dict = {
                "id": item.id,
                "type": item.type,
                "text": item.text,
                "metadata": json.dumps(item.metadata or {}),
                "created_at": item.created_at or _now(),
                "last_seen": item.last_seen or _now(),
                "ttl": item.ttl,
                "decay": item.decay or 0.0,
                "source": item.source,
                "hash": item.hash,
                "embedding": json.dumps(item.embedding or []),
            }
            if not item_dict["id"]:
                item_dict["id"] = item.hash or hashlib.sha256(os.urandom(32)).hexdigest()
            cur.execute(
                """
                INSERT OR REPLACE INTO memories
                (id, type, text, metadata, created_at, last_seen, ttl, decay, source, hash, embedding)
                VALUES (:id,:type,:text,:metadata,:created_at,:last_seen,:ttl,:decay,:source,:hash,:embedding)
                """,
                item_dict,
            )
            # populate FTS if available
            try:
                cur.execute(
                    "INSERT OR REPLACE INTO memories_fts (id, text, metadata) VALUES (?,?,?)",
                    (item_dict["id"], item_dict["text"], item_dict["metadata"]),
                )
            except sqlite3.OperationalError:
                pass
            self.conn.commit()
            return item_dict["id"]

    def get_all(self) -> List[MemoryItem]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM memories")
        rows = cur.fetchall()
        return [_row_to_item(r) for r in rows]

    def get(self, id: str) -> Optional[MemoryItem]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM memories WHERE id = ?", (id,))
        r = cur.fetchone()
        return _row_to_item(r) if r else None

    def delete(self, id: str) -> bool:
        with _LOCK:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM memories WHERE id = ?", (id,))
            try:
                cur.execute("DELETE FROM memories_fts WHERE id = ?", (id,))
            except sqlite3.OperationalError:
                pass
            self.conn.commit()
            return cur.rowcount > 0

    def query_text_match(self, query: str, limit: int = 50) -> List[Tuple[str, float]]:
        """
        Return list of (id, sparse_score) for items matching query.
        Best-effort: if FTS5 available, use MATCH; otherwise use token
        Jaccard on text+metadata.
        """
        cur = self.conn.cursor()
        # Try FTS5 first
        try:
            cur.execute(
                "SELECT id FROM memories_fts WHERE text MATCH ? LIMIT ?",
                (query, limit),
            )
            rows = cur.fetchall()
            results = [(r["id"], 1.0) for r in rows]
            if results:
                return results
        except sqlite3.OperationalError:
            pass

        # Fallback: naive token overlap on text + metadata
        qtokens = set(_tokenize(query))
        cur.execute("SELECT id, text, metadata FROM memories LIMIT ?", (limit,))
        rows = cur.fetchall()
        out: List[Tuple[str, float]] = []
        for r in rows:
            text = (r["text"] or "") + " " + (r["metadata"] or "")
            score = _jaccard_score(list(qtokens), _tokenize(text))
            if score > 0:
                out.append((r["id"], score))
        return out

    def all_embeddings(self) -> List[Tuple[str, List[float], float, float, Optional[float]]]:
        """
        Return list of (id, embedding, created_at, last_seen, ttl) for all items.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT id, embedding, created_at, last_seen, ttl FROM memories")
        rows = cur.fetchall()
        out = []
        for r in rows:
            emb = json.loads(r["embedding"] or "[]")
            out.append((r["id"], emb, r["created_at"] or 0.0, r["last_seen"] or (r["created_at"] or 0.0), r["ttl"]))
        return out

    def update_fields(self, id: str, patch: Dict[str, Any]) -> bool:
        with _LOCK:
            cur = self.conn.cursor()
            cols = []
            params = {}
            for k, v in patch.items():
                if k in {"text", "type", "source"}:
                    cols.append(f"{k} = :{k}")
                    params[k] = v
                elif k == "metadata":
                    cols.append("metadata = :metadata")
                    params["metadata"] = json.dumps(v)
                elif k in {"ttl", "decay", "last_seen"}:
                    cols.append(f"{k} = :{k}")
                    params[k] = v
                elif k == "embedding":
                    cols.append("embedding = :embedding")
                    params["embedding"] = json.dumps(v)
            if not cols:
                return False
            params["id"] = id
            sql = f"UPDATE memories SET {', '.join(cols)} WHERE id = :id"
            cur.execute(sql, params)
            self.conn.commit()
            return cur.rowcount > 0

    def find_by_hash(self, h: str) -> Optional[MemoryItem]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM memories WHERE hash = ? LIMIT 1", (h,))
        r = cur.fetchone()
        return _row_to_item(r) if r else None

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


def _row_to_item(r: sqlite3.Row) -> MemoryItem:
    if not r:
        return None
    data = {
        "id": r["id"],
        "type": r["type"],
        "text": r["text"],
        "metadata": json.loads(r["metadata"] or "{}"),
        "created_at": r["created_at"],
        "last_seen": r["last_seen"],
        "ttl": r["ttl"],
        "decay": r["decay"],
        "source": r["source"],
        "hash": r["hash"],
        "embedding": json.loads(r["embedding"] or "[]"),
    }
    return MemoryItem(**data)


# ---------------------------
# In-memory wrapper + public API
# ---------------------------
_backend_impl = None


def _get_backend():
    global _backend_impl
    if _backend_impl is not None:
        return _backend_impl
    if _MEMORY_BACKEND == "chroma":
        try:
            import chromadb  # type: ignore
            # For this initial iteration we prefer sqlite; full chroma wiring will be added later.
            # Fall back to sqlite if chromadb isn't desired in this environment.
        except Exception:
            pass
    _backend_impl = _SQLiteBackend(_DB_PATH)
    return _backend_impl


# TTL defaults by type (seconds)
_TTL_DEFAULTS = {
    "FACT": 60 * 60 * 24 * 365 * 10,  # 10 years
    "PERSONAL_PREF": 60 * 60 * 24 * 365 * 5,  # 5 years
    "SESSION": 60 * 60 * 24 * 30,  # 30 days
    "TRANSCRIPT": 60 * 60 * 24 * 7,  # 7 days
    "TASK": 60 * 60 * 24 * 90,  # 90 days
    "TOOL_OUTPUT": 60 * 60 * 24 * 30,  # 30 days
    "SCRATCH": 60 * 60 * 2,  # 2 hours
}


def _default_ttl_for(item_type: str) -> Optional[float]:
    return _TTL_DEFAULTS.get(item_type.upper(), None)


def remember(item: MemoryItem, anchors: Optional[List[str]] = None) -> str:
    """
    Store a memory item. Returns the id. Deduplicates by hash (type + text + anchors).
    Updates existing item.last_seen if duplicate found.
    """
    backend = _get_backend()
    # prepare fields
    if not item.hash:
        item.hash = _make_hash(item.type, item.text, anchors)
    if not item.created_at:
        item.created_at = _now()
    if not item.last_seen:
        item.last_seen = item.created_at
    if item.ttl is None:
        item.ttl = _default_ttl_for(item.type)
    if item.embedding is None:
        item.embedding = _embedding_for(item.text)

    existing = backend.find_by_hash(item.hash)
    if existing:
        # Reinforce last_seen and optionally merge metadata
        patch = {"last_seen": _now()}
        # optionally merge metadata keys (preserve existing unless new provided)
        merged = dict(existing.metadata or {})
        merged.update(item.metadata or {})
        patch["metadata"] = merged
        backend.update_fields(existing.id, patch)
        return existing.id
    # write new
    if not item.id:
        item.id = item.hash
    return backend.upsert(item)


def _apply_time_decay(base_score: float, item: MemoryItem) -> float:
    """
    Apply exponential decay to a base score depending on age and decay rate.
    decay is per-day; final multiplier = exp(-decay * days_since(last_seen))
    """
    days = _days_since(item.last_seen or item.created_at or _now())
    if item.decay and item.decay > 0:
        mult = math.exp(-item.decay * days)
        return base_score * mult
    return base_score


def recall(query: str, k: int = 8, filters: Optional[Dict[str, Any]] = None) -> List[MemoryItem]:
    """
    Recall top-k relevant memories for query.
    Steps:
      - compute query embedding
      - get dense scores (cosine) across store
      - get sparse scores (token overlap or FTS)
      - normalize both to 0..1 and fuse: 0.7*dense + 0.3*sparse
      - apply time decay multiplier
      - apply filters (type, metadata contains...)
      - return top-k items (and update last_seen for returned)
    """
    backend = _get_backend()
    q_emb = _embedding_for(query)
    # dense candidates
    all_embs = backend.all_embeddings()
    dense_scores: Dict[str, float] = {}
    for id_, emb, created_at, last_seen, ttl in all_embs:
        dense_scores[id_] = _cosine(q_emb, emb)

    # sparse candidates (id -> score)
    sparse_list = backend.query_text_match(query, limit=200)
    sparse_scores = {id_: s for id_, s in sparse_list}

    # union ids
    candidate_ids = set(dense_scores.keys()) | set(sparse_scores.keys())

    scored: List[Tuple[str, float]] = []
    # normalization helpers
    def _norm_map(m: Dict[str, float]) -> Dict[str, float]:
        if not m:
            return {}
        vmin = min(m.values())
        vmax = max(m.values())
        if vmax - vmin < 1e-12:
            return {k: 1.0 for k in m.keys()}
        return {k: (v - vmin) / (vmax - vmin) for k, v in m.items()}

    nd = _norm_map(dense_scores)
    ns = _norm_map(sparse_scores)

    ALPHA = 0.7
    for id_ in candidate_ids:
        d = nd.get(id_, 0.0)
        s = ns.get(id_, 0.0)
        fused = ALPHA * d + (1.0 - ALPHA) * s
        # load item to consider TTL/decay/filtering
        item = backend.get(id_)
        if not item:
            continue
        # filter by type or metadata if requested
        if filters:
            typ = filters.get("type")
            if typ and item.type != typ:
                continue
            # metadata contains
            meta_contains = filters.get("metadata_contains")
            if meta_contains:
                ok = True
                for k, v in meta_contains.items():
                    if item.metadata.get(k) != v:
                        ok = False
                        break
                if not ok:
                    continue
        # TTL hard-exclude
        if item.ttl is not None:
            age = _now() - (item.created_at or 0.0)
            if age > item.ttl:
                continue
        # apply decay
        final_score = _apply_time_decay(fused, item)
        scored.append((id_, final_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = [backend.get(id_) for id_, _ in scored[:k] if backend.get(id_)]
    # update last_seen for returned items
    for it in top:
        backend.update_fields(it.id, {"last_seen": _now()})
    return top


def update(id: str, patch: Dict[str, Any]) -> bool:
    """
    Patch fields of an existing memory.
    Accepts keys: text, type, metadata (dict), ttl, decay, last_seen, embedding.
    Returns True if updated.
    """
    backend = _get_backend()
    return backend.update_fields(id, patch)


def forget(id: str) -> bool:
    backend = _get_backend()
    return backend.delete(id)


def gc() -> int:
    """
    Garbage-collect expired items (hard TTL exceeded).
    Returns number of deleted items.
    """
    backend = _get_backend()
    deleted = 0
    now = _now()
    for item in backend.get_all():
        if item.ttl is not None:
            age = now - (item.created_at or 0.0)
            if age > item.ttl:
                if backend.delete(item.id):
                    deleted += 1
    return deleted


def snapshot(session_id: Optional[str] = None) -> str:
    """
    Snapshot memories as JSON.
    If session_id provided, only include items whose metadata.session == session_id.
    """
    backend = _get_backend()
    out = []
    for item in backend.get_all():
        if session_id:
            if item.metadata.get("session") != session_id:
                continue
        out.append(asdict(item) if hasattr(item, "__dataclass_fields__") else json.loads(item.json()))
        # pydantic: item.dict() would be better, but we guard above
    return json.dumps(out, indent=2)


def restore(snapshot_json: str) -> int:
    """
    Restore items from snapshot JSON string.
    Returns number of inserted items.
    """
    data = json.loads(snapshot_json)
    inserted = 0
    for d in data:
        # normalize keys to MemoryItem
        if isinstance(d, str):
            continue
        mi = MemoryItem(**d)
        # ensure hash exists
        if not mi.hash:
            mi.hash = _make_hash(mi.type, mi.text)
        mi.embedding = mi.embedding or _embedding_for(mi.text)
        if remember(mi) is not None:
            inserted += 1
    return inserted


def inject_relevant_memory(turn: str, token_budget: int = 500) -> str:
    """
    Return a compact context block built from the most relevant memories to the `turn`.
    Stop when token_budget (approx words) is exhausted.
    """
    parts = []
    used_tokens = 0
    # approximate tokens by words
    def _tok_count(s: str) -> int:
        return len(_tokenize(s))

    candidates = recall(turn, k=20)
    for c in candidates:
        text = f"[{c.type}:{c.id[:8]}] {c.text}"
        t = _tok_count(text)
        if used_tokens + t > token_budget:
            break
        parts.append(text)
        used_tokens += t
    if not parts:
        return ""
    return "\n".join(parts)


# For testability, expose internal fusion function
def fusion_score(dense: float, sparse: float, alpha: float = 0.7) -> float:
    """
    Deterministic fusion: combine normalized dense and sparse scores.
    """
    return alpha * dense + (1.0 - alpha) * sparse


# Ensure backend is initialized on import
_get_backend()
