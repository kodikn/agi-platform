"""API routes - Orchestrator workflows"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()


class WorkflowExecutionRequest(BaseModel):
    """Workflow execution request"""
    workflow_name: str
    input: Dict[str, Any]
    enable_checkpointing: bool = True


class WorkflowExecution(BaseModel):
    """Workflow execution response"""
    id: str
    workflow_name: str
    status: str
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    error: Optional[str]


class CheckpointInfo(BaseModel):
    """Checkpoint information"""
    checkpoint_id: int
    node_name: str
    timestamp: datetime


# In-memory storage for demo
executions_db: Dict[str, Dict[str, Any]] = {}
workflows_db: Dict[str, Dict[str, Any]] = {}


@router.post("/execute", response_model=WorkflowExecution)
async def execute_workflow(request: WorkflowExecutionRequest):
    """Execute a workflow"""
    
    if request.workflow_name not in workflows_db:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    execution_id = str(uuid.uuid4())
    
    execution = {
        "id": execution_id,
        "workflow_name": request.workflow_name,
        "status": "running",
        "input": request.input,
        "output": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "error": None,
        "checkpoints": [],
        "enable_checkpointing": request.enable_checkpointing
    }
    
    executions_db[execution_id] = execution
    
    logger.info(f"Started workflow execution: {execution_id}")
    
    return execution


@router.get("/execution/{execution_id}", response_model=WorkflowExecution)
async def get_execution(execution_id: str):
    """Get workflow execution status"""
    
    execution = executions_db.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return execution


@router.get("/executions", response_model=List[WorkflowExecution])
async def list_executions(
    workflow_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List workflow executions"""
    
    results = list(executions_db.values())
    
    if workflow_name:
        results = [e for e in results if e["workflow_name"] == workflow_name]
    
    if status:
        results = [e for e in results if e["status"] == status]
    
    # Sort by creation time descending
    results = sorted(results, key=lambda x: x["created_at"], reverse=True)
    
    return results[offset:offset + limit]


@router.post("/execution/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    """Cancel workflow execution"""
    
    execution = executions_db.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if execution["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed execution")
    
    execution["status"] = "cancelled"
    execution["updated_at"] = datetime.utcnow()
    
    logger.info(f"Cancelled execution: {execution_id}")
    
    return {"status": "cancelled", "execution_id": execution_id}


@router.post("/execution/{execution_id}/pause")
async def pause_execution(execution_id: str):
    """Pause workflow execution"""
    
    execution = executions_db.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if execution["status"] != "running":
        raise HTTPException(status_code=400, detail="Can only pause running executions")
    
    execution["status"] = "paused"
    execution["updated_at"] = datetime.utcnow()
    
    logger.info(f"Paused execution: {execution_id}")
    
    return {"status": "paused", "execution_id": execution_id}


@router.post("/execution/{execution_id}/resume")
async def resume_execution(execution_id: str):
    """Resume workflow execution"""
    
    execution = executions_db.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if execution["status"] != "paused":
        raise HTTPException(status_code=400, detail="Can only resume paused executions")
    
    execution["status"] = "running"
    execution["updated_at"] = datetime.utcnow()
    
    logger.info(f"Resumed execution: {execution_id}")
    
    return {"status": "running", "execution_id": execution_id}


@router.get("/execution/{execution_id}/checkpoints", response_model=List[CheckpointInfo])
async def get_checkpoints(execution_id: str):
    """Get execution checkpoints"""
    
    execution = executions_db.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    checkpoints = []
    for cp in execution.get("checkpoints", []):
        checkpoints.append(CheckpointInfo(
            checkpoint_id=cp["id"],
            node_name=cp.get("node_name", "unknown"),
            timestamp=cp.get("timestamp", datetime.utcnow())
        ))
    
    return checkpoints


@router.post("/execution/{execution_id}/restore/{checkpoint_id}")
async def restore_from_checkpoint(execution_id: str, checkpoint_id: int):
    """Restore execution from checkpoint"""
    
    execution = executions_db.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    checkpoint = next(
        (cp for cp in execution.get("checkpoints", []) if cp["id"] == checkpoint_id),
        None
    )
    
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    
    execution["status"] = "running"
    execution["updated_at"] = datetime.utcnow()
    
    logger.info(f"Restored execution {execution_id} from checkpoint {checkpoint_id}")
    
    return {"status": "restored", "execution_id": execution_id, "checkpoint_id": checkpoint_id}


@router.get("/workflows", response_model=List[Dict[str, Any]])
async def list_workflows():
    """List all available workflows"""
    
    return list(workflows_db.values())


@router.post("/workflows")
async def create_workflow(workflow: Dict[str, Any]):
    """Create a new workflow"""
    
    workflow_id = str(uuid.uuid4())
    
    workflow["id"] = workflow_id
    workflow["created_at"] = datetime.utcnow()
    
    workflows_db[workflow_id] = workflow
    
    logger.info(f"Created workflow: {workflow_id}")
    
    return workflow
