"""API routes - Memory management"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uuid

from memory.layer import MemoryType

logger = logging.getLogger(__name__)

router = APIRouter()


class MemoryStoreRequest(BaseModel):
    """Store memory request"""
    content: Dict[str, Any]
    memory_type: str  # short_term, long_term, episodic, semantic
    confidence: float = 1.0
    tags: Optional[List[str]] = None


class MemoryRetrievalRequest(BaseModel):
    """Memory retrieval request"""
    query: str
    memory_types: Optional[List[str]] = None
    limit: int = 10
    min_confidence: float = 0.5


class MemoryEntry(BaseModel):
    """Memory entry response"""
    id: str
    content: Dict[str, Any]
    memory_type: str
    confidence: float
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    access_count: int


# In-memory storage for demo
memory_db: Dict[str, Dict[str, Any]] = {}


@router.post("/store", response_model=Dict[str, str])
async def store_memory(request: MemoryStoreRequest):
    """Store a memory entry"""
    
    try:
        memory_type = MemoryType(request.memory_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid memory type: {request.memory_type}"
        )
    
    memory_id = str(uuid.uuid4())
    
    entry = {
        "id": memory_id,
        "content": request.content,
        "memory_type": request.memory_type,
        "confidence": request.confidence,
        "tags": request.tags or [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "access_count": 0
    }
    
    memory_db[memory_id] = entry
    
    logger.info(f"Stored memory {memory_id} of type {request.memory_type}")
    
    return {"memory_id": memory_id, "status": "stored"}


@router.post("/retrieve", response_model=List[MemoryEntry])
async def retrieve_memory(request: MemoryRetrievalRequest):
    """Retrieve memories based on query"""
    
    results = []
    
    for memory_id, entry in memory_db.items():
        # Simple matching logic
        if any(term in str(entry["content"]).lower() for term in request.query.lower().split()):
            if entry["confidence"] >= request.min_confidence:
                if not request.memory_types or entry["memory_type"] in request.memory_types:
                    results.append(entry)
    
    # Sort by confidence and access count
    results = sorted(
        results,
        key=lambda x: (x["confidence"], x["access_count"]),
        reverse=True
    )
    
    # Update access count
    for entry in results[:request.limit]:
        entry["access_count"] += 1
        entry["updated_at"] = datetime.utcnow()
    
    logger.info(f"Retrieved {len(results)} memories for query: {request.query}")
    
    return results[:request.limit]


@router.get("/{memory_id}", response_model=MemoryEntry)
async def get_memory(memory_id: str):
    """Get specific memory entry"""
    
    entry = memory_db.get(memory_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    # Update access
    entry["access_count"] += 1
    entry["updated_at"] = datetime.utcnow()
    
    return entry


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete memory entry"""
    
    if memory_id not in memory_db:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    del memory_db[memory_id]
    
    logger.info(f"Deleted memory {memory_id}")
    
    return {"status": "deleted", "memory_id": memory_id}


@router.get("/type/{memory_type}", response_model=List[MemoryEntry])
async def list_by_type(
    memory_type: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List memories by type"""
    
    try:
        MemoryType(memory_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory type")
    
    results = [
        entry for entry in memory_db.values()
        if entry["memory_type"] == memory_type
    ]
    
    return results[offset:offset + limit]


@router.get("/stats/overview", response_model=Dict[str, Any])
async def memory_stats():
    """Get memory statistics"""
    
    stats = {
        "total_memories": len(memory_db),
        "by_type": {},
        "average_confidence": 0.0,
        "total_access_count": 0
    }
    
    for entry in memory_db.values():
        memory_type = entry["memory_type"]
        if memory_type not in stats["by_type"]:
            stats["by_type"][memory_type] = 0
        stats["by_type"][memory_type] += 1
        stats["total_access_count"] += entry["access_count"]
    
    if memory_db:
        avg_confidence = sum(e["confidence"] for e in memory_db.values()) / len(memory_db)
        stats["average_confidence"] = round(avg_confidence, 2)
    
    return stats
