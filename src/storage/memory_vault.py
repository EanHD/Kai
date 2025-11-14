"""File-based Memory Vault for user-owned data.

Stores typed memories in human-readable JSONL files under `data/memory/<user_id>/`.
Types supported: episodic, semantic, preference, bug_fix, reflection, prompt, checklist.

Each memory record includes: id, type, created_at, last_used_at, confidence, ttl,
tags, summary, and payload (arbitrary dict specific to the type).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json
import uuid
import os


MEMORY_TYPES = {
    "episodic": "episodic.jsonl",
    "semantic": "semantic.jsonl",
    "preference": "preferences.jsonl",
    "bug_fix": "bugs.jsonl",
    "reflection": "reflections.jsonl",
    "prompt": "prompts.jsonl",
    "checklist": "checklists.jsonl",
}


@dataclass
class MemoryRecord:
    id: str
    type: str
    created_at: str
    last_used_at: Optional[str] = None
    confidence: Optional[float] = None
    ttl_days: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MemoryVault:
    """Simple JSONL-based memory store with user-owned files."""

    def __init__(self, user_id: str, base_dir: Optional[str] = None):
        self.user_id = user_id
        base = base_dir or os.environ.get("MEMORY_VAULT_DIR", "data/memory")
        self.root = Path(base) / user_id
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for_type(self, mtype: str) -> Path:
        filename = MEMORY_TYPES.get(mtype)
        if not filename:
            raise ValueError(f"Unsupported memory type: {mtype}")
        return self.root / filename

    def add(
        self,
        mtype: str,
        payload: Dict[str, Any],
        *,
        summary: Optional[str] = None,
        confidence: Optional[float] = None,
        ttl_days: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> MemoryRecord:
        rec = MemoryRecord(
            id=str(uuid.uuid4()),
            type=mtype,
            created_at=datetime.utcnow().isoformat(),
            last_used_at=None,
            confidence=confidence,
            ttl_days=ttl_days,
            tags=tags or [],
            summary=summary,
            payload=payload,
        )
        path = self._path_for_type(mtype)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
        return rec

    def add_episode(
        self,
        *,
        session_id: str,
        user_text: str,
        assistant_text: str,
        success: Optional[bool] = None,
        summary: Optional[str] = None,
        confidence: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> MemoryRecord:
        payload = {
            "session_id": session_id,
            "user": user_text,
            "assistant": assistant_text,
            "success": success,
        }
        return self.add(
            "episodic",
            payload,
            summary=summary,
            confidence=confidence,
            ttl_days=90,
            tags=tags,
        )

    def list(
        self,
        *,
        mtype: Optional[str] = None,
        limit: Optional[int] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        paths: Iterable[Path]
        if mtype:
            paths = [self._path_for_type(mtype)]
        else:
            paths = [(self.root / name) for name in MEMORY_TYPES.values()]

        results: List[Dict[str, Any]] = []
        for p in paths:
            if not p.exists():
                continue
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        if tag and tag not in (obj.get("tags") or []):
                            continue
                        results.append(obj)
                        if limit and len(results) >= limit:
                            return results
                    except json.JSONDecodeError:
                        continue
        return results

    def export_markdown(self, out_path: str) -> str:
        """Export all memories to a single Markdown file for easy viewing."""
        records = self.list()
        out = [f"# Memory Vault Export (user={self.user_id})\n"]
        for r in records:
            out.append(f"\n## {r['type'].upper()} — {r['id']}\n")
            out.append(f"Created: {r['created_at']}  ")
            if r.get("last_used_at"):
                out.append(f"Last Used: {r['last_used_at']}  ")
            if r.get("confidence") is not None:
                out.append(f"Confidence: {r['confidence']}  ")
            if r.get("ttl_days") is not None:
                out.append(f"TTL (days): {r['ttl_days']}  ")
            if r.get("tags"):
                out.append(f"Tags: {', '.join(r['tags'])}  ")
            if r.get("summary"):
                out.append(f"\n**Summary**: {r['summary']}\n")
            out.append("\n```json\n" + json.dumps(r.get("payload", {}), indent=2) + "\n```\n")
        out_text = "\n".join(out) + "\n"
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(out_text, encoding="utf-8")
        return str(out_file)

    def prune(self) -> Dict[str, int]:
        """Delete memories that have expired based on ttl_days and low-confidence heuristic.

        Returns a count of removed items per type.
        """
        removed: Dict[str, int] = {t: 0 for t in MEMORY_TYPES}
        now = datetime.utcnow()
        for mtype, filename in MEMORY_TYPES.items():
            path = self.root / filename
            if not path.exists():
                continue
            new_lines: List[str] = []
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ttl_days = obj.get("ttl_days")
                    created_at = obj.get("created_at")
                    conf = obj.get("confidence")
                    expired = False
                    if ttl_days and created_at:
                        try:
                            dt = datetime.fromisoformat(created_at)
                            if now - dt > timedelta(days=int(ttl_days)):
                                expired = True
                        except Exception:
                            pass
                    # Heuristic: very low confidence and not used recently
                    last_used_at = obj.get("last_used_at")
                    stale = False
                    if conf is not None and conf < 0.2:
                        try:
                            dt2 = datetime.fromisoformat(last_used_at) if last_used_at else datetime.fromisoformat(created_at)
                            if now - dt2 > timedelta(days=30):
                                stale = True
                        except Exception:
                            stale = True

                    if expired or stale:
                        removed[mtype] += 1
                        continue
                    new_lines.append(json.dumps(obj, ensure_ascii=False))
            # Rewrite file if changes
            if removed[mtype] > 0:
                with path.open("w", encoding="utf-8") as f:
                    for ln in new_lines:
                        f.write(ln + "\n")
        return removed
