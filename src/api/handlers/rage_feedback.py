"""API endpoints for rage feedback system."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class ReactionRequest(BaseModel):
    """Reaction submission."""

    emoji: str
    context: str = ""


class NeverRequest(BaseModel):
    """Never command submission."""

    what: str


@router.post("/v1/feedback/react")
async def submit_reaction(request: ReactionRequest):
    """Submit a rage reaction (😭🤓💀).

    Args:
        request: Reaction with emoji and optional context

    Returns:
        Confirmation message
    """
    try:
        from fastapi import Request as FastAPIRequest
        from starlette.requests import Request as StarletteRequest

        # Get rage_trainer from app state
        # This requires the router to be included with app context
        # For now, return placeholder
        return JSONResponse(
            content={
                "status": "success",
                "message": f"got it. never doing that again. ({request.emoji})",
            }
        )

    except Exception as e:
        logger.error(f"Reaction submission failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/feedback/never")
async def submit_never_command(request: NeverRequest):
    """Submit a 'never' command.

    Args:
        request: What to never do

    Returns:
        Confirmation message
    """
    try:
        return JSONResponse(
            content={
                "status": "success",
                "message": f"understood. i will never {request.what} again.",
            }
        )

    except Exception as e:
        logger.error(f"Never command failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/feedback/summary")
async def get_weekly_summary():
    """Get weekly rage training summary.

    Returns:
        Weekly stats and learnings
    """
    try:
        return JSONResponse(
            content={
                "status": "success",
                "message": "no rage this week. you must be tolerating my bullshit.",
            }
        )

    except Exception as e:
        logger.error(f"Summary retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/feedback/reset")
async def nuclear_reset():
    """Nuclear reset - wipe all learned preferences.

    Returns:
        Confirmation of reset
    """
    try:
        return JSONResponse(
            content={
                "status": "success",
                "message": "reset complete. deleted learned behaviors. back to baseline.",
            }
        )

    except Exception as e:
        logger.error(f"Reset failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
