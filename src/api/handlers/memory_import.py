"""API handler for memory import operations."""

import json
import logging
from typing import Any

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from src.storage.memory_vault import MemoryVault
from src.tools.chatgpt_importer import ChatGPTImporter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/memory/import/chatgpt")
async def import_chatgpt_conversations(
    file: UploadFile = File(...),
):
    """Import ChatGPT conversations.json file.
    
    Args:
        file: Uploaded JSON file containing ChatGPT conversations
        
    Returns:
        JSON response with import statistics
    """
    try:
        # Read uploaded file
        content = await file.read()
        data = json.loads(content)
        
        # Get user_id from session (defaulting to "default" for now)
        # In production, this should come from authentication
        user_id = "default"
        
        # Initialize vault and importer
        vault = MemoryVault(user_id=user_id)
        
        # Get LLM connector from app state
        from src.core.providers.ollama_provider import OllamaProvider
        llm_config = {
            "model_id": "granite-local",
            "model_name": "granite4:micro-h",
            "provider": "ollama",
            "capabilities": [],
            "context_window": 4096,
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
        }
        llm = OllamaProvider(llm_config, "http://localhost:11434")
        
        # Run import
        importer = ChatGPTImporter(vault, llm)
        stats = await importer.process_conversations(data)
        
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])
        
        return JSONResponse(content={
            "status": "success",
            "message": f"Imported {stats['conversations']} conversations · Kai now remembers your chaos",
            "stats": stats
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in upload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
