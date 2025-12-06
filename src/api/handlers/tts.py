"""
TTS Handler - Text-to-Speech using Google Cloud TTS API

Provides TTS endpoint using Google's high-quality Journey/Aoede voices.
"""

import logging
import os
import base64
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Literal, Optional
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/audio", tags=["audio"])

# Google Cloud TTS voice mapping
# Aoede is a Journey voice - en-US-Journey-O (female, warm)
GOOGLE_VOICES = {
    "aoede": {"name": "en-US-Journey-O", "gender": "FEMALE"},
    "charon": {"name": "en-US-Journey-D", "gender": "MALE"},
    "fenrir": {"name": "en-US-Journey-F", "gender": "FEMALE"},
    "kore": {"name": "en-US-Journey-O", "gender": "FEMALE"},
    "puck": {"name": "en-US-Studio-O", "gender": "FEMALE"},
    # Fallbacks to standard voices
    "nova": {"name": "en-US-Neural2-C", "gender": "FEMALE"},
    "alloy": {"name": "en-US-Neural2-A", "gender": "MALE"},
    "echo": {"name": "en-US-Neural2-D", "gender": "MALE"},
    "onyx": {"name": "en-US-Neural2-J", "gender": "MALE"},
    "shimmer": {"name": "en-US-Neural2-F", "gender": "FEMALE"},
}


class TTSRequest(BaseModel):
    """TTS API request model."""
    model: str = Field(default="tts-1", description="TTS model (ignored, uses Google)")
    input: str = Field(..., description="Text to convert to speech", max_length=5000)
    voice: str = Field(default="aoede", description="Voice to use (aoede, kore, charon, fenrir, puck)")
    response_format: Literal["mp3", "wav", "ogg"] = Field(default="mp3", description="Audio format")
    speed: float = Field(default=1.0, ge=0.25, le=4.0, description="Speech speed")


@router.post("/speech")
async def text_to_speech(request: TTSRequest):
    """
    Convert text to speech using Google Cloud TTS API.
    
    Requires GOOGLE_TTS_API_KEY environment variable.
    Returns audio in the requested format.
    """
    api_key = os.getenv("GOOGLE_TTS_API_KEY")
    
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail={"error": {"message": "TTS requires GOOGLE_TTS_API_KEY", "type": "configuration_error"}}
        )
    
    # Get voice config
    voice_key = request.voice.lower()
    voice_config = GOOGLE_VOICES.get(voice_key, GOOGLE_VOICES["aoede"])
    
    # Audio encoding mapping
    audio_encodings = {
        "mp3": "MP3",
        "wav": "LINEAR16",
        "ogg": "OGG_OPUS",
    }
    
    content_types = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "ogg": "audio/ogg",
    }
    
    # Build Google TTS request
    tts_request = {
        "input": {"text": request.input},
        "voice": {
            "languageCode": "en-US",
            "name": voice_config["name"],
            "ssmlGender": voice_config["gender"]
        },
        "audioConfig": {
            "audioEncoding": audio_encodings.get(request.response_format, "MP3"),
            "speakingRate": request.speed,
            "pitch": 0.0,
            "volumeGainDb": 0.0,
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}",
                headers={"Content-Type": "application/json"},
                json=tts_request
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Google TTS error: {error_detail}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail={"error": {"message": f"Google TTS failed: {error_detail}", "type": "api_error"}}
                )
            
            # Google returns base64 encoded audio
            result = response.json()
            audio_content = base64.b64decode(result["audioContent"])
            
            return Response(
                content=audio_content,
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
