"""
TTS Handler - Text-to-Speech using OpenAI API

Provides OpenAI-compatible TTS endpoint that proxies to OpenAI's TTS API.
"""

import logging
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/audio", tags=["audio"])


class TTSRequest(BaseModel):
    """OpenAI TTS API request model."""
    model: str = Field(default="tts-1", description="TTS model to use")
    input: str = Field(..., description="Text to convert to speech", max_length=4096)
    voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = Field(
        default="nova", description="Voice to use"
    )
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = Field(
        default="mp3", description="Audio format"
    )
    speed: float = Field(default=1.0, ge=0.25, le=4.0, description="Speech speed")


@router.post("/speech")
async def text_to_speech(request: TTSRequest):
    """
    Convert text to speech using OpenAI's TTS API.
    
    Returns audio stream in the requested format.
    """
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    if not openai_api_key:
        raise HTTPException(
            status_code=500,
            detail={"error": {"message": "OpenAI API key not configured", "type": "configuration_error"}}
        )
    
    # Content type mapping
    content_types = {
        "mp3": "audio/mpeg",
        "opus": "audio/opus",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "wav": "audio/wav",
        "pcm": "audio/pcm",
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": request.model,
                    "input": request.input,
                    "voice": request.voice,
                    "response_format": request.response_format,
                    "speed": request.speed,
                }
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"OpenAI TTS error: {error_detail}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail={"error": {"message": f"OpenAI TTS failed: {error_detail}", "type": "api_error"}}
                )
            
            # Stream the audio response
            return StreamingResponse(
                iter([response.content]),
                media_type=content_types.get(request.response_format, "audio/mpeg"),
                headers={
                    "Content-Disposition": f"attachment; filename=speech.{request.response_format}"
                }
            )
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={"error": {"message": "TTS request timed out", "type": "timeout_error"}}
        )
    except httpx.RequestError as e:
        logger.error(f"TTS request error: {e}")
        raise HTTPException(
            status_code=502,
            detail={"error": {"message": f"Failed to connect to TTS service: {str(e)}", "type": "connection_error"}}
        )
