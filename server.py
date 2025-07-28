from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from main import runnable, State
from typing import cast
from dotenv import load_dotenv

load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

app = FastAPI()

# Optional: Allow cross-origin access (for Flutter or web frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    state: State = {
        "memory_file": "memory.jsonb"
    }

    while True:
        try:
            user_input = await websocket.receive_text()
            state["user_input"] = user_input

            result = runnable.invoke(state)
            state.update(cast(State, result))
            await websocket.send_text(state.get("response", ""))

        except Exception as e:
            await websocket.send_text(f"[ERROR]: {str(e)}")
            break

    await websocket.close()

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)