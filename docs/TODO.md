# Kai — Quick TODO / Launch checklist

This short checklist contains minimal steps and items to confirm so Kai can be launched on a headless Linux box.

Prerequisites
- Python 3.11 installed (system apt or pyenv)
- Docker (optional) if you plan to use the Docker path

Basic quickstart (venv)
1. git clone <repo>
2. cp .env.example .env  # fill any secrets (OPEN_ROUTER_KEY optional for local-only)
3. python3 -m venv .venv && source .venv/bin/activate
4. pip install -r requirements.txt
5. Start server:
   - dev: bash scripts/run_dev.sh
   - prod: bash scripts/run_prod.sh

Smoke test
- From the same host run: bash scripts/smoke.sh
- Or: curl http://localhost:8000/health

Docker quickstart
1. cp .env.example .env
2. docker compose up --build -d
3. curl http://localhost:8000/health

Important checks (if memory/Chroma not required)
- MEMORY_BACKEND=sqlite (default) does not need chromadb installed; chromadb is optional.
- If using sentence-transformers embeddings locally, ensure model download is possible (large; optional). The memory.store has a deterministic fallback.

CI / repo push note
- If your GitHub token lacks the `workflow` scope, avoid pushing changes that create/update files under `.github/workflows/`. Use the GitHub UI to create workflows instead.

Helpful commands
- Run tests: pytest -q
- Run server locally: bash scripts/run_dev.sh
- Build and run in Docker: docker compose up --build

If you want I can:
- Add a small "demo_memory.py" to /examples that programmatically demonstrates remember/recall/gc/snapshot/restore.
- Wire a lightweight CLI for snapshots and exports.
