# Kai — AI Assistant Agent

Kai is a LangGraph-powered AI assistant designed to serve as a personal agent in a collaborative GroupChat App. It uses local LLMs, RAG (Retrieval-Augmented Generation), memory logic, and a modular tool system to interact, reason, and assist with multi-step tasks.

---

## 🔧 Features

- **LangGraph Orchestration**: Declarative graph-based execution for conversation, memory, and tool routing.
- **Memory System**: Short-term + long-term memory using ChromaDB and JSONB files.
- **Multi-Model Routing**: Routes requests to:
  - `smollm2:1.7b` for light interactions
  - `gemma3n:e2b` for long or code-based prompts
  - `gpt-4o`, `gemini` if manually triggered
- **RAG**: Dynamically retrieves relevant context from ChromaDB to improve responses.
- **Toolchain System** (MCP): Includes callable tools like:
  - Google Search
  - Document sync
  - Future tools like Weather, Code Eval, File Reader, etc.
- **WebSocket server** for real-time interaction
- **Developer-focused setup** using environment variables, local models, and fallback logic

---

## 🧱 Project Structure

```
kai/
├── docs
│   └── # Drop RAG docs here then run "sync_docs_to_chroma.py"
├── models
│   ├── gemini_client.py
│   ├── ollama_client.py
│   └── openai_client.py
├── rag
│   ├── chroma_client.py
│   └── memory_view.py
├── tools
│   └── tools.py
├── main.py
├── server.py
├── sync_docs_to_chroma.py
├── memory.jsonb
├── README.md


```

---

## 🧪 How It Works

1. **Message received**
2. `main.py` runs the LangGraph:
   - Loads memory
   - Optionally summarizes long history into ChromaDB
   - Routes model depending on:
     - Prompt length
     - Explicit flags (e.g., "`gpt", "`gemini", "`kai")
   - Retrieves RAG context if needed
   - Calls appropriate model
   - Updates memory
3. **WebSocket returns** the response to the frontend

---

## 🧩 Supported Prompt Triggers

Use these prefixes in your prompt to manually select a model:
- \`kai → use `smollm2` or `gemma3n` (auto-pick based on length)
- \`gpt → use OpenAI's `gpt-4o`
- \`gemini → use Google's Gemini model

---

## 📥 Document Sync

Drop files into the `docs/` folder (auto-created) to add them to ChromaDB.

**Supported file types:**
- `.md`, `.txt`, `.pdf`, `.docx`, `.html`, `.json`, `.csv`, `.py`, `.js`

Run:
```bash
python sync_docs_to_chroma.py
```

---

## 🔐 Environment Setup

Create a `.env` file in the root:
```
OPENAI_API_KEY=your-openai-key
GOOGLE_API_KEY=your-google-key
# (Optional) If you use GEMINI_API_KEY elsewhere, set it equal to GOOGLE_API_KEY
GEMINI_API_KEY=your-google-key
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Start the server:
```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

---

## 🧠 Future Plans

- Fine-tuning Kai on user-specific documents
- Better summarization / compression nodes
- Add more tools: browser, calendar, file search
- Memory visualization and editing via frontend

---

## 🧑‍💻 Author

Made by Ethan Joseph Magaoay

> Kai is designed to help builders like you go further, faster. 🚀
# Kai — OpenAI‑Compatible Personal AI Gateway

Kai is your plug‑and‑play AI gateway: it **looks like the OpenAI API** to any third‑party front‑end, but behind the scenes it runs your whole Kai ecosystem — dynamic model routing (local + cloud), RAG with Chroma, tools, and layered memory.

---

## What’s in here
- **OpenAI‑compatible endpoints**: `POST /v1/chat/completions`, `GET /v1/models`, plus `GET /health`.
- **Dynamic router** (`kai-graph:default`): picks between local models and cloud models, optional backtick overrides, optional RAG, and a final **style pass** so Kai always “sounds like Kai”.
- **Local + Cloud models**
  - Local (Ollama): `smollm2:1.7b`, `phi4-mini:3.8b`, `deepseek-coder:1.3b`  
    Aliases: `deepseekcoder:2b → deepseek-coder:1.3b`
  - Cloud (OpenRouter): `openai/gpt-oss-120b`, `openai/gpt-5`
- **Streaming**: Server‑Sent Events (SSE) for OpenRouter; simulated chunk streaming for local and graph paths.
- **Memory layers (Chroma)**: `kai_docs`, `kai_facts`, `kai_persona`, `kai_transcripts`.
- **Docs sync**: `sync_docs_to_chroma.py` ingests `./docs` (chunking + de‑dupe) and prints the active embedding mode.

---

## Quick start

1) Install deps (Python 3.10+ recommended):
```bash
pip install -r requirements.txt
# If you use local embeddings:
pip install sentence-transformers chromadb PyPDF2 python-docx beautifulsoup4
```

2) Env vars (create a `.env` or export in your shell):
```bash
# Cloud LLMs via OpenRouter
OPEN_ROUTER_KEY=...                 # required for OSS‑120B / GPT‑5
OPENROUTER_APP_URL=kai.local        # optional attribution
OPENROUTER_APP_TITLE=Kai            # optional attribution

# Embeddings for Chroma (pick ONE mode)
KAI_EMBEDDINGS=local                # one of: local | ollama | cloud
# local sentence‑transformers
EMBED_MODEL_LOCAL=all-MiniLM-L6-v2  # default local embedder
# ollama embeddings
EMBED_MODEL_OLLAMA=nomic-embed-text # or mxbai-embed-large
OLLAMA_URL=http://localhost:11434
# cloud embeddings (OpenAI)
OPENAI_API_KEY=...                  # only if KAI_EMBEDDINGS=cloud
EMBED_MODEL=text-embedding-3-small

# Chroma storage (optional)
CHROMA_PATH=./chroma
```

3) Run the API with autoreload:
```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

4) Sanity check:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/v1/models
```

---

## OpenAI‑compatible surface

### Models
`GET /v1/models` returns something like:
```json
{
  "object": "list",
  "data": [
    {"id": "gpt-5", "object": "model"},
    {"id": "openrouter:oss-120b", "object": "model"},
    {"id": "kai-local:smollm2:1.7b", "object": "model"},
    {"id": "kai-local:phi4-mini:3.8b", "object": "model"},
    {"id": "kai-local:deepseek-coder:1.3b", "object": "model"},
    {"id": "kai-graph:default", "object": "model"}
  ]
}
```

### Chat completions
Basic non‑stream call:
```bash
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "openrouter:oss-120b",
    "messages": [{"role":"user","content":"Say hi from OSS-120B."}]
  }'
```
Streaming (SSE) with OpenRouter:
```bash
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-5",
    "stream": true,
    "messages": [{"role":"user","content":"Stream three fun facts."}]
  }'
```
Local models (via Ollama):
```bash
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "kai-local:phi4-mini:3.8b",
    "messages": [{"role":"user","content":"Write a tiny haiku."}]
  }'
```
Graph (dynamic router):
```bash
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "kai-graph:default",
    "messages": [{"role":"user","content":"Draft a 4-week launch plan with risks."}]
  }'
```

---

## Dynamic routing (kai‑graph)
- Reads the request, scores **complexity** and **intent**, and chooses a model:
  - **Local**: `smollm2` (tiny tasks + tone), `phi‑4‑mini` (reasoning‑lite), `deepseek‑coder` (code_small)
  - **Cloud**: `OSS‑120B` (bigger reasoning), `GPT‑5` (hardest/safest)
- **Backtick overrides** (at the start of the message):
  - `` `kai `` → smollm2:1.7b
  - `` `phi `` → phi4-mini:3.8b
  - `` `code `` → deepseek-coder:1.3b
  - `` `oss `` → openai/gpt-oss-120b
  - `` `gpt `` → openai/gpt-5
- Heuristic **RAG retrieval** for doc/spec/how/why prompts; stitches citations into the prompt.
- **Style pass** with smollm2 unless the user says “raw”.

---

## Memory & RAG
Kai uses **Chroma** with named collections:
- `kai_docs` — documents from `./docs` (chunked + de‑duped)
- `kai_facts` — stable facts, playbooks, APIs, verified procedures
- `kai_persona` — voice/style/preferences for Kai
- `kai_transcripts` — saved user/assistant turns per session

### Embedding modes
Pick one by setting `KAI_EMBEDDINGS`:
- `ollama` → uses Ollama’s `/api/embeddings`  
  `EMBED_MODEL_OLLAMA=nomic-embed-text` (or `mxbai-embed-large`), `OLLAMA_URL=http://localhost:11434`
- `local` (default) → sentence‑transformers  
  `EMBED_MODEL_LOCAL=all-MiniLM-L6-v2`
- `cloud` → OpenAI embeddings  
  `OPENAI_API_KEY=...`, `EMBED_MODEL=text-embedding-3-small`

> Tip: run `python sync_docs_to_chroma.py` — it prints `Embedding mode → ...` at start.

### Sync docs into RAG
Put files in `./docs` then:
```bash
python sync_docs_to_chroma.py
```
- Supports: `.md`, `.txt`, `.pdf`, `.docx`, `.html`, `.csv`
- Chunks to ~1200 chars with 150‑char overlap
- De‑dupes by a stable content hash per chunk

### Transcripts
Every request saves **user** and **assistant** turns into `kai_transcripts`.  
Headers accepted for session grouping: `X-Session-Id` or `X-Client-Id`.  
OpenAI body field `user` is also supported and preferred if present.

---

## Third‑party front‑ends
Any UI that supports a custom OpenAI endpoint will work.
- **Settings**:
  - Base URL: `https://<your-host>/v1`
  - API key: your Kai key (if you add auth)
  - Model: pick from `/v1/models`
- **Apollo (iOS)** works great for quick tests.

---

## Publish with Tailscale Funnel (optional)
Expose your local Kai securely without router configs:
```bash
tailscale funnel 8000
```
Use the provided `https://...ts.net/v1` as your Base URL in clients.  
(Cloudflare Tunnel works too if you prefer custom DNS + WAF.)

---

## Troubleshooting
- **404 on /v1/** → make sure you’re launching `uvicorn server:app --reload` (this repo uses `server.py`).
- **OpenRouter 401** → check `OPEN_ROUTER_KEY` and model slugs.
- **Ollama local models** → run `ollama serve` and `ollama pull smollm2:1.7b` (etc.).
- **DeepSeek “2B”** → Ollama doesn’t ship a 2B tag; we map `deepseekcoder:2b` → `deepseek-coder:1.3b` by default.
- **Embeddings cost** → set `KAI_EMBEDDINGS=ollama` or `local` to avoid API usage; `cloud` enables OpenAI embeddings.

---

## Project structure (high level)
```
kai/
├── docs/                         # drop files to ingest
├── models/
│   ├── ollama_client.py          # local LLMs
│   ├── openrouter_client.py      # cloud LLMs via OpenRouter
│   └── openai_client.py          # optional direct OpenAI client
├── rag/
│   ├── chroma_client.py          # Chroma, embeddings, named collections
│   ├── transcripts.py            # transcript saver
│   └── memory_view.py
├── tools/
│   └── tools.py                  # router + RAG helpers
├── server.py                     # OpenAI-compatible API
├── sync_docs_to_chroma.py        # docs ingestion (chunk + de-dup)
└── README.md
```

---

## License & Author
Made by Ethan Joseph Magaoay.  
Kai is for builders who want their own stack, their own memory, and any front‑end they like.