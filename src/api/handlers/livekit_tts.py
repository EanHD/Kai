"""
LiveKit TTS Handler - Streaming Text-to-Speech

Uses LiveKit's TTS service with Cartesia voices (Felicia, etc).
"""

import logging
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal, AsyncIterator
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/audio", tags=["audio"])


class LiveKitTTSRequest(BaseModel):
    """LiveKit TTS request model (OpenAI-compatible)."""
    model: str = Field(default="tts-1", description="Model identifier")
    input: str = Field(..., description="Text to convert to speech", max_length=5000)
    voice: str = Field(default="felicia", description="Voice ID")
    response_format: Literal["mp3", "wav", "opus"] = Field(default="mp3")
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


# Cartesia voice IDs via LiveKit
CARTESIA_VOICES = {
    "felicia": "f9836c6e-a0bd-460e-9d3c-f7299fa60f94",  # Felicia - expressive, warm
    "aoede": "79a125e8-cd45-4c13-8a67-188112f4dd22",    # British Lady
    "nova": "a0e99841-438c-4a64-b679-ae501e7d6091",     # Friendly Woman
    "clover": "b7d50908-b17c-442d-ad8d-810c63997ed9",   # Pleasant Female
}


async def stream_tts_audio(text: str, voice_id: str, speed: float) -> AsyncIterator[bytes]:
    """
    Stream TTS audio from LiveKit/Cartesia.
    """
    livekit_url = os.getenv("LIVEKIT_URL", "wss://your-livekit-server.com")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    if not api_key or not api_secret:
        raise HTTPException(
            status_code=503,
            detail={"error": {"message": "TTS requires LIVEKIT_API_KEY and LIVEKIT_API_SECRET", "type": "configuration_error"}}
        )
    
    # Use Cartesia TTS via their direct API (LiveKit uses this)
    cartesia_key = os.getenv("CARTESIA_API_KEY")
    if not cartesia_key:
        raise HTTPException(
            status_code=503,
            detail={"error": {"message": "TTS requires CARTESIA_API_KEY", "type": "configuration_error"}}
        )
    
    url = "https://api.cartesia.ai/tts/bytes"
    
    headers = {
        "X-API-Key": cartesia_key,
        "Cartesia-Version": "2024-06-10",
        "Content-Type": "application/json",
    }
    
    data = {
        "model_id": "sonic-english",
        "transcript": text,
        "voice": {
            "mode": "id",
            "id": voice_id
        },
        "output_format": {
            "container": "raw",
            "encoding": "pcm_s16le",
            "sample_rate": 44100
        },
        "language": "en"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, headers=headers, json=data) as response:
            if response.status_code != 200:
                error = await response.aread()
                logger.error(f"Cartesia TTS error: {error}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail={"error": {"message": "TTS streaming failed", "type": "api_error"}}
                )
            
            async for chunk in response.aiter_bytes(chunk_size=4096):
                if chunk:
                    yield chunk


@router.post("/speech")
async def batch_text_to_speech(request: LiveKitTTSRequest):
    """
    Batch TTS using LiveKit/Cartesia.
    """
    voice_id = CARTESIA_VOICES.get(request.voice.lower(), CARTESIA_VOICES["felicia"])
    
    chunks = []
    async for chunk in stream_tts_audio(request.input, voice_id, request.speed):
        chunks.append(chunk)
    
    audio_data = b"".join(chunks)
    
    return StreamingResponse(
        iter([audio_data]),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f"attachment; filename=speech.mp3"}
    )
