"""
LiveKit STT Handler - Speech-to-Text using Deepgram

Replaces browser SpeechRecognition with reliable Deepgram API via LiveKit.
"""

import logging
import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/audio", tags=["audio"])


class TranscriptionResponse(BaseModel):
    """OpenAI-compatible transcription response."""
    text: str


@router.post("/transcriptions", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    model: str = Form(default="whisper-1"),
    language: Optional[str] = Form(default="en"),
    prompt: Optional[str] = Form(default=None),
    response_format: str = Form(default="json"),
    temperature: float = Form(default=0.0)
):
    """
    Transcribe audio using Deepgram via LiveKit.
    OpenAI Whisper API compatible.
    """
    deepgram_key = os.getenv("DEEPGRAM_API_KEY")
    
    if not deepgram_key:
        raise HTTPException(
            status_code=503,
            detail={"error": {"message": "STT requires DEEPGRAM_API_KEY", "type": "configuration_error"}}
        )
    
    # Read audio file
    audio_data = await file.read()
    
    # Deepgram API endpoint
    url = "https://api.deepgram.com/v1/listen"
    
    # Query parameters for Deepgram
    params = {
        "model": "nova-2",  # Latest Deepgram model
        "language": language,
        "smart_format": "true",
        "punctuate": "true",
        "diarize": "false",
    }
    
    headers = {
        "Authorization": f"Token {deepgram_key}",
        "Content-Type": file.content_type or "audio/webm",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                content=audio_data
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Deepgram STT error: {error_detail}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail={"error": {"message": f"STT failed: {error_detail}", "type": "api_error"}}
                )
            
            result = response.json()
            
            # Extract transcript from Deepgram response
            try:
                transcript = result["results"]["channels"][0]["alternatives"][0]["transcript"]
            except (KeyError, IndexError) as e:
                logger.error(f"Failed to parse Deepgram response: {e}")
                raise HTTPException(
                    status_code=500,
                    detail={"error": {"message": "Failed to parse transcription", "type": "parse_error"}}
                )
            
            return TranscriptionResponse(text=transcript)
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={"error": {"message": "STT request timed out", "type": "timeout_error"}}
        )
    except httpx.RequestError as e:
        logger.error(f"STT request error: {e}")
        raise HTTPException(
            status_code=502,
            detail={"error": {"message": f"Failed to connect to STT service: {str(e)}", "type": "connection_error"}}
        )
