Status summary — Memory subsystem audit (concise)

What I changed so far
- Added a new memory subsystem module: memory/store.py
  - SQLite-backed default, optional Chroma feature flag
  - MemoryItem schema, remember/recall/update/forget/gc/snapshot/restore/inject_relevant_memory
  - Hybrid retrieval (dense embeddings + sparse FTS/token-overlap) with deterministic fusion_score
  - TTL defaults, decay multiplier, deduplication via normalized hash
- Wired memory injection into prompt assembly:
  - tools/tools.py: best-effort import of inject_relevant_memory and prepend "### Relevant Memory" when ENABLE_MEMORY_INJECT=true
  - server.py: added a guarded debug log when injection enabled (no behavior changes to endpoints)
- Tests + CI + supporting files:
  - tests/test_memory_basic.py added (dedupe, TTL/gc, fusion_score, recall/injection smoke)
  - docs/memory_store_summary.md and docs/README.md updated
  - .gitignore updated, .env.example added
  - Created GitHub Actions workflow, then removed it per your instruction; README updated with CI note

Current repo health checklist
- memory/store.py implemented and backend initialized on import.
- tools/server integration is minimal and additive (env-controlled).
- Unit tests created: run pytest to validate behavior locally.
- No new runtime dependencies required beyond existing project; sentence-transformers is optional (fallback embedder exists).
- Chroma backend is detected but not fully wired as primary by default — feature-flagged.

Recommended next steps (short)
1. Run tests locally:
   - pytest -q
2. Smoke-run the server and do a manual memory demo:
   - start server: uvicorn server:app --reload --port 8000
   - add 3 memories via memory.store.remember(...) in a small script or REPL, call recall() and inject_relevant_memory() to verify results
3. If you want Chroma as primary backend, confirm chromadb & OpenAI/OpenRouter keys and I can add a true Chroma backend implementation.

Notes about previous SEARCH/REPLACE mismatches
- You saw a failed match for edits to .github/workflows/ci.yml earlier; that was due to the file contents differing slightly between chat states. You later added the canonical files to the chat; I will only edit files you explicitly add.

If you want me to apply further edits now, tell me which of the files above to edit next:
- Implement a Chroma backend in memory/store.py
- Add more unit tests (decay reinforcement, re-ranking determinism)
- Wire snapshot/restore into a CLI script
- Add a small example script in examples/demo_memory.py that programmatically shows remember/recall/gc/snapshot/restore

Suggested shell commands (run from repo root)
```bash
pytest -q
```
```bash
uvicorn server:app --reload --port 8000
```
