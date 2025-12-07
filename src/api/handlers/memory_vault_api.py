"""API handler for memory vault operations."""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from src.storage.memory_vault import MemoryVault, MEMORY_TYPES

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/v1/memory/list")
async def list_memories(
    type: Optional[str] = Query(None, description="Filter by memory type"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    limit: int = Query(100, ge=1, le=1000, description="Max number of memories to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """List all memories with optional filtering.
    
    Args:
        type: Memory type filter (episodic, semantic, preference, etc.)
        tags: Filter by tags (AND logic - must have all tags)
        limit: Maximum number of results
        offset: Pagination offset
        
    Returns:
        JSON response with memories array and pagination info
    """
    try:
        # Get user_id from session (defaulting to "default" for now)
        user_id = "default"
        
        vault = MemoryVault(user_id=user_id)
        
        # Get all memories of requested type(s)
        all_memories = []
        
        types_to_fetch = [type] if type else list(MEMORY_TYPES.keys())
        
        for memory_type in types_to_fetch:
            try:
                memories = vault.get_all(memory_type)
                all_memories.extend(memories)
            except ValueError:
                # Invalid type, skip
                continue
        
        # Filter by tags if provided
        if tags:
            all_memories = [
                m for m in all_memories 
                if all(tag in m.tags for tag in tags)
            ]
        
        # Sort by created_at (newest first)
        all_memories.sort(key=lambda x: x.created_at, reverse=True)
        
        # Pagination
        total = len(all_memories)
        paginated = all_memories[offset:offset + limit]
        
        # Convert to dict for JSON response
        memories_dict = [m.to_dict() for m in paginated]
        
        return JSONResponse(content={
            "status": "success",
            "memories": memories_dict,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to list memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/memory/search")
async def search_memories(
    query: str = Query(..., description="Search query"),
    type: Optional[str] = Query(None, description="Filter by memory type"),
    limit: int = Query(20, ge=1, le=100, description="Max number of results")
):
    """Search memories by query string.
    
    Args:
        query: Search query (searches summary and payload)
        type: Optional memory type filter
        limit: Maximum number of results
        
    Returns:
        JSON response with matching memories
    """
    try:
        user_id = "default"
        vault = MemoryVault(user_id=user_id)
        
        # Get all memories
        all_memories = []
        types_to_search = [type] if type else list(MEMORY_TYPES.keys())
        
        for memory_type in types_to_search:
            try:
                memories = vault.get_all(memory_type)
                all_memories.extend(memories)
            except ValueError:
                continue
        
        # Simple text search in summary and payload
        query_lower = query.lower()
        matches = []
        
        for memory in all_memories:
            score = 0
            
            # Search in summary
            if memory.summary and query_lower in memory.summary.lower():
                score += 10
            
            # Search in tags
            for tag in memory.tags:
                if query_lower in tag.lower():
                    score += 5
            
            # Search in payload (convert to string)
            payload_str = str(memory.payload).lower()
            if query_lower in payload_str:
                score += 3
            
            if score > 0:
                matches.append((score, memory))
        
        # Sort by score (descending)
        matches.sort(key=lambda x: x[0], reverse=True)
        
        # Take top N
        top_matches = [m[1].to_dict() for m in matches[:limit]]
        
        return JSONResponse(content={
            "status": "success",
            "query": query,
            "results": top_matches,
            "total": len(top_matches)
        })
        
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/memory/stats")
async def get_memory_stats():
    """Get statistics about stored memories.
    
    Returns:
        JSON response with memory counts by type
    """
    try:
        user_id = "default"
        vault = MemoryVault(user_id=user_id)
        
        stats = {}
        total = 0
        
        for memory_type in MEMORY_TYPES.keys():
            try:
                memories = vault.get_all(memory_type)
                count = len(list(memories))
                stats[memory_type] = count
                total += count
            except ValueError:
                stats[memory_type] = 0
        
        return JSONResponse(content={
            "status": "success",
            "total": total,
            "by_type": stats
        })
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/v1/memory/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a specific memory by ID.
    
    Args:
        memory_id: UUID of the memory to delete
        
    Returns:
        JSON response with success status
    """
    try:
        user_id = "default"
        vault = MemoryVault(user_id=user_id)
        
        # Search all types for the memory
        found = False
        for memory_type in MEMORY_TYPES.keys():
            try:
                memories = list(vault.get_all(memory_type))
                target = next((m for m in memories if m.id == memory_id), None)
                
                if target:
                    vault.delete(memory_id, memory_type)
                    found = True
                    break
            except (ValueError, FileNotFoundError):
                continue
        
        if not found:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return JSONResponse(content={
            "status": "success",
            "message": f"Memory {memory_id} deleted"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/memory/add")
async def add_memory(
    type: str,
    payload: Dict[str, Any],
    summary: Optional[str] = None,
    tags: Optional[List[str]] = None,
    confidence: Optional[float] = None,
    ttl_days: Optional[int] = None
):
    """Manually add a memory to the vault.
    
    Args:
        type: Memory type (episodic, semantic, preference, etc.)
        payload: Memory data (dict)
        summary: Optional summary text
        tags: Optional tags
        confidence: Optional confidence score (0-1)
        ttl_days: Optional time-to-live in days
        
    Returns:
        JSON response with created memory record
    """
    try:
        user_id = "default"
        vault = MemoryVault(user_id=user_id)
        
        record = vault.add(
            mtype=type,
            payload=payload,
            summary=summary,
            tags=tags or [],
            confidence=confidence,
            ttl_days=ttl_days
        )
        
        return JSONResponse(content={
            "status": "success",
            "memory": record.to_dict()
        })
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
