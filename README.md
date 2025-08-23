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
- **Docs sync**: `sync_docs_to_chroma.py` ingests `./docs` (chunking + de‑dupe)
- **Toolchain System** (MCP): Includes callable tools like:
  - Google Search
  - Document sync
  - Future tools like Weather, Code Eval, File Reader, etc.
- **WebSocket server** for real-time interaction
- **Developer-focused setup** using environment variables, local models, and fallback logic

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
python rag/sync_docs.py
```

---

## 🔐 Environment Setup

Create a `.env` file in the root:
```
OPENAI_API_KEY=your-openai-key
GEMINI_API_KEY=your-google-key
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Start the server:
```bash
uvicorn app:app --reload --port 60001
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

## Memory injection toggles
Env vars controlling memory context injection:

- ENABLE_MEMORY_INJECT=true|false (default true)
- MEMORY_TOKENS=800 (approx token/word budget)

Example:
```
ENABLE_MEMORY_INJECT=true
MEMORY_TOKENS=800
```
