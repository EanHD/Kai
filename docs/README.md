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
uvicorn server:app --reload --port 8000
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
