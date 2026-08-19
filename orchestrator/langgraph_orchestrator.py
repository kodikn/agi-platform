"""Level 9: Orchestrator - LangGraph-based workflow orchestration"""

from typing import Dict, List, Any, Optional, Callable, Coroutine
from enum import Enum
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class WorkflowNode:
    """Workflow node definition"""
    
    def __init__(
        self,
        name: str,
        handler: Callable,
        required_inputs: Optional[List[str]] = None,
        output_keys: Optional[List[str]] = None
    ):
        self.name = name
        self.handler = handler
        self.required_inputs = required_inputs or []
        self.output_keys = output_keys or ["result"]
        self.retries = 0
        self.timeout = None

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute node"""
        
        # Validate inputs
        for key in self.required_inputs:
            if key not in input_data:
                raise ValueError(f"Missing required input: {key}")
        
        # Execute handler
        result = await self.handler(input_data)
        
        # Format output
        output = {}
        if isinstance(result, dict):
            output = result
        else:
            output["result"] = result
        
        return output


class WorkflowEdge:
    """Workflow edge (transition)"""
    
    def __init__(
        self,
        source: str,
        target: str,
        condition: Optional[Callable[[Dict], bool]] = None
    ):
        self.source = source
        self.target = target
        self.condition = condition or (lambda x: True)

    def should_transition(self, state: Dict[str, Any]) -> bool:
        """Check if transition should occur"""
        return self.condition(state)


class WorkflowState:
    """Workflow execution state"""
    
    def __init__(self, workflow_name: str):
        self.workflow_name = workflow_name
        self.id = str(uuid.uuid4())
        self.status = ExecutionStatus.PENDING
        self.current_node: Optional[str] = None
        self.data: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.checkpoints: Dict[int, Dict[str, Any]] = {}
        self.checkpoint_count = 0

    def update_data(self, updates: Dict[str, Any]):
        """Update workflow data"""
        self.data.update(updates)
        self.updated_at = datetime.utcnow()

    def add_history_entry(self, node_name: str, output: Dict[str, Any]):
        """Add execution history"""
        self.history.append({
            "node": node_name,
            "output": output,
            "timestamp": datetime.utcnow().isoformat()
        })

    def create_checkpoint(self) -> int:
        """Create a checkpoint"""
        self.checkpoint_count += 1
        self.checkpoints[self.checkpoint_count] = {
            "data": self.data.copy(),
            "current_node": self.current_node,
            "timestamp": datetime.utcnow().isoformat()
        }
        return self.checkpoint_count

    def restore_checkpoint(self, checkpoint_id: int) -> bool:
        """Restore from checkpoint"""
        if checkpoint_id not in self.checkpoints:
            return False
        
        checkpoint = self.checkpoints[checkpoint_id]
        self.data = checkpoint["data"].copy()
        self.current_node = checkpoint["current_node"]
        logger.info(f"Restored checkpoint {checkpoint_id}")
        return True


class StateGraph:
    """State machine graph for workflow orchestration"""
    
    def __init__(self, name: str):
        self.name = name
        self.nodes: Dict[str, WorkflowNode] = {}
        self.edges: List[WorkflowEdge] = []
        self.entry_point: Optional[str] = None
        self.end_point: Optional[str] = None

    def add_node(self, node: WorkflowNode):
        """Add a node to graph"""
        self.nodes[node.name] = node
        logger.debug(f"Added node: {node.name}")

    def add_edge(self, edge: WorkflowEdge):
        """Add an edge to graph"""
        self.edges.append(edge)
        logger.debug(f"Added edge: {edge.source} -> {edge.target}")

    def set_entry_point(self, node_name: str):
        """Set entry point"""
        if node_name not in self.nodes:
            raise ValueError(f"Node not found: {node_name}")
        self.entry_point = node_name

    def set_end_point(self, node_name: str):
        """Set end point"""
        if node_name not in self.nodes:
            raise ValueError(f"Node not found: {node_name}")
        self.end_point = node_name

    def get_next_nodes(self, current_node: str, state: Dict[str, Any]) -> List[str]:
        """Get next nodes based on current state"""
        
        next_nodes = []
        for edge in self.edges:
            if edge.source == current_node and edge.should_transition(state):
                next_nodes.append(edge.target)
        
        return next_nodes


class Orchestrator:
    """Level 9: Orchestrator - LangGraph-based workflow orchestration"""
    
    def __init__(self):
        self.graphs: Dict[str, StateGraph] = {}
        self.executions: Dict[str, WorkflowState] = {}
        self.human_in_loop_callbacks: Dict[str, Callable] = {}

    def create_graph(self, name: str) -> StateGraph:
        """Create a new workflow graph"""
        graph = StateGraph(name)
        self.graphs[name] = graph
        logger.info(f"Created workflow graph: {name}")
        return graph

    def get_graph(self, name: str) -> Optional[StateGraph]:
        """Get workflow graph by name"""
        return self.graphs.get(name)

    async def execute_workflow(
        self,
        graph_name: str,
        input_data: Dict[str, Any],
        enable_checkpointing: bool = True
    ) -> WorkflowState:
        """Execute workflow"""
        
        graph = self.graphs.get(graph_name)
        if not graph:
            raise ValueError(f"Graph not found: {graph_name}")
        
        state = WorkflowState(graph_name)
        state.status = ExecutionStatus.RUNNING
        state.started_at = datetime.utcnow()
        state.data = input_data.copy()
        state.current_node = graph.entry_point
        
        self.executions[state.id] = state
        
        logger.info(f"Starting workflow execution: {state.id}")
        
        try:
            # Execute workflow
            while state.current_node and state.status == ExecutionStatus.RUNNING:
                
                # Create checkpoint if enabled
                if enable_checkpointing:
                    state.create_checkpoint()
                
                node = graph.nodes.get(state.current_node)
                if not node:
                    raise ValueError(f"Node not found: {state.current_node}")
                
                # Execute node
                try:
                    output = await node.execute(state.data)
                    state.update_data(output)
                    state.add_history_entry(state.current_node, output)
                    
                    logger.info(f"Executed node: {state.current_node}")
                    
                except Exception as e:
                    logger.error(f"Node execution failed: {str(e)}")
                    state.error = str(e)
                    state.status = ExecutionStatus.FAILED
                    return state
                
                # Check if end point reached
                if state.current_node == graph.end_point:
                    state.status = ExecutionStatus.COMPLETED
                    state.completed_at = datetime.utcnow()
                    logger.info(f"Workflow completed: {state.id}")
                    break
                
                # Get next node
                next_nodes = graph.get_next_nodes(state.current_node, state.data)
                
                if not next_nodes:
                    state.status = ExecutionStatus.COMPLETED
                    state.completed_at = datetime.utcnow()
                    logger.info(f"Workflow completed (no next nodes): {state.id}")
                    break
                
                # For now, take first next node
                state.current_node = next_nodes[0]
            
            return state
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            state.error = str(e)
            state.status = ExecutionStatus.FAILED
            return state

    async def get_execution(self, execution_id: str) -> Optional[WorkflowState]:
        """Get workflow execution by ID"""
        return self.executions.get(execution_id)

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel workflow execution"""
        
        state = self.executions.get(execution_id)
        if not state:
            return False
        
        if state.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
            return False
        
        state.status = ExecutionStatus.CANCELLED
        logger.info(f"Cancelled execution: {execution_id}")
        return True

    async def pause_execution(self, execution_id: str) -> bool:
        """Pause workflow execution"""
        
        state = self.executions.get(execution_id)
        if not state:
            return False
        
        state.status = ExecutionStatus.PAUSED
        logger.info(f"Paused execution: {execution_id}")
        return True

    async def resume_execution(self, execution_id: str) -> bool:
        """Resume workflow execution"""
        
        state = self.executions.get(execution_id)
        if not state or state.status != ExecutionStatus.PAUSED:
            return False
        
        state.status = ExecutionStatus.RUNNING
        logger.info(f"Resumed execution: {execution_id}")
        return True

    async def restore_from_checkpoint(
        self,
        execution_id: str,
        checkpoint_id: int
    ) -> bool:
        """Restore workflow from checkpoint"""
        
        state = self.executions.get(execution_id)
        if not state:
            return False
        
        return state.restore_checkpoint(checkpoint_id)
