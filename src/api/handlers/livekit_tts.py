"""
LiveKit TTS Handler - Streaming Text-to-Speech

Uses LiveKit's TTS service with ElevenLabs/Deepgram voices.
Streams audio chunks for lower latency than batch processing.
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
    voice: str = Field(default="aoede", description="Voice ID")
    response_format: Literal["mp3", "wav", "opus"] = Field(default="mp3")
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


# LiveKit voice mappings (using ElevenLabs or Deepgram)
LIVEKIT_VOICES = {
    "aoede": "EXAVITQu4vr4xnSDxMaL",  # Rachel (ElevenLabs)
    "nova": "21m00Tcm4TlvDq8ikWAM",   # Rachel (ElevenLabs)
    "alloy": "pNInz6obpgDQGcFmaJgB",  # Adam (ElevenLabs)
    "echo": "VR6AewLTigWG4xSOukaG",   # Arnold (ElevenLabs)
    "shimmer": "AZnzlk1XvdvUeBnXmlld",  # Domi (ElevenLabs)
}


async def stream_tts_audio(text: str, voice_id: str, speed: float) -> AsyncIterator[bytes]:
    """
    Stream TTS audio from LiveKit/ElevenLabs API.
    """
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail={"error": {"message": "LiveKit TTS requires LIVEKIT_API_KEY", "type": "configuration_error"}}
        )
    
    # Use ElevenLabs API directly for now (LiveKit uses it under the hood)
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    if not elevenlabs_key:
        raise HTTPException(
            status_code=503,
            detail={"error": {"message": "TTS requires ELEVENLABS_API_KEY", "type": "configuration_error"}}
        )
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    
    headers = {
        "xi-api-key": elevenlabs_key,
        "Content-Type": "application/json",
    }
    
    data = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, headers=headers, json=data) as response:
            if response.status_code != 200:
                error = await response.aread()
                logger.error(f"ElevenLabs TTS error: {error}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail={"error": {"message": "TTS streaming failed", "type": "api_error"}}
                )
            
            async for chunk in response.aiter_bytes(chunk_size=4096):
                if chunk:
                    yield chunk


@router.post("/speech/stream")
async def stream_text_to_speech(request: LiveKitTTSRequest):
    """
    Stream TTS audio using LiveKit/ElevenLabs.
    Returns streaming MP3 audio for lower latency.
    """
    voice_id = LIVEKIT_VOICES.get(request.voice.lower(), LIVEKIT_VOICES["aoede"])
    
    return StreamingResponse(
        stream_tts_audio(request.input, voice_id, request.speed),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f"attachment; filename=speech.mp3",
            "Cache-Control": "no-cache",
        }
    )


@router.post("/speech")
async def batch_text_to_speech(request: LiveKitTTSRequest):
    """
    Batch TTS (for compatibility) - collects all chunks and returns.
    For streaming, use /speech/stream endpoint.
    """
    voice_id = LIVEKIT_VOICES.get(request.voice.lower(), LIVEKIT_VOICES["aoede"])
    
    chunks = []
    async for chunk in stream_tts_audio(request.input, voice_id, request.speed):
        chunks.append(chunk)
    
    audio_data = b"".join(chunks)
    
    return StreamingResponse(
        iter([audio_data]),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f"attachment; filename=speech.mp3"}
    )
