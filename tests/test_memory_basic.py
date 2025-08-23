import os
import time

# Use an in-memory sqlite DB for tests to avoid touching disk
os.environ["KAI_MEMORY_DB"] = ":memory:"
os.environ["MEMORY_BACKEND"] = "sqlite"

from memory.store import MemoryItem, remember, recall, gc, fusion_score, inject_relevant_memory

def test_dedupe_and_remember():
    a = MemoryItem(type="FACT", text="The sky is blue.", metadata={"source": "test"})
    id1 = remember(a)
    b = MemoryItem(type="FACT", text="  The   sky is   blue. ", metadata={"source": "other"})
    id2 = remember(b)
    assert id1 == id2

def test_ttl_and_gc():
    s = MemoryItem(type="SCRATCH", text="temp value", ttl=1)
    sid = remember(s)
    # Wait for TTL to expire
    time.sleep(1.1)
    deleted = gc()
    assert deleted >= 1

def test_fusion_score():
    higher = fusion_score(1.0, 0.0)
    lower = fusion_score(0.0, 1.0)
    assert higher > lower

def test_recall_and_injection_smoke():
    mi = MemoryItem(type="FACT", text="Alice likes pizza and walks her dog.", metadata={"source":"unit"})
    remember(mi)
    results = recall("what does alice like", k=5)
    assert any("alice" in (r.text or "").lower() for r in results)
    injected = inject_relevant_memory("what does alice like", token_budget=50)
    # injection may be empty in some environments; at minimum ensure call doesn't error
    assert isinstance(injected, str)
