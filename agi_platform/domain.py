from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class DomainStateError(ValueError):
    """Raised when a domain object is asked to perform an invalid state transition."""


class LifecycleState(StrEnum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class WorkflowState(StrEnum):
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskState(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_TOOL = "WAITING_TOOL"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RETRYING = "RETRYING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


WORKFLOW_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.CREATED: {WorkflowState.PLANNED, WorkflowState.CANCELLED},
    WorkflowState.PLANNED: {WorkflowState.RUNNING, WorkflowState.PAUSED, WorkflowState.CANCELLED},
    WorkflowState.RUNNING: {WorkflowState.WAITING, WorkflowState.PAUSED, WorkflowState.FAILED, WorkflowState.COMPLETED, WorkflowState.CANCELLED},
    WorkflowState.WAITING: {WorkflowState.RUNNING, WorkflowState.PAUSED, WorkflowState.FAILED, WorkflowState.CANCELLED},
    WorkflowState.PAUSED: {WorkflowState.RUNNING, WorkflowState.CANCELLED},
    WorkflowState.FAILED: {WorkflowState.RECOVERING, WorkflowState.CANCELLED},
    WorkflowState.RECOVERING: {WorkflowState.RUNNING, WorkflowState.FAILED, WorkflowState.CANCELLED},
    WorkflowState.COMPLETED: set(),
    WorkflowState.CANCELLED: set(),
}

TASK_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.PENDING: {TaskState.READY, TaskState.CANCELLED},
    TaskState.READY: {TaskState.RUNNING, TaskState.WAITING_APPROVAL, TaskState.CANCELLED},
    TaskState.RUNNING: {TaskState.WAITING_TOOL, TaskState.WAITING_APPROVAL, TaskState.RETRYING, TaskState.FAILED, TaskState.COMPLETED, TaskState.CANCELLED},
    TaskState.WAITING_TOOL: {TaskState.RUNNING, TaskState.RETRYING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.WAITING_APPROVAL: {TaskState.RUNNING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.RETRYING: {TaskState.RUNNING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.FAILED: {TaskState.RETRYING, TaskState.CANCELLED},
    TaskState.COMPLETED: set(),
    TaskState.CANCELLED: set(),
}


class EventType(StrEnum):
    WORKFLOW_CREATED = "WorkflowCreated"
    WORKFLOW_STARTED = "WorkflowStarted"
    WORKFLOW_PAUSED = "WorkflowPaused"
    WORKFLOW_RESUMED = "WorkflowResumed"
    WORKFLOW_COMPLETED = "WorkflowCompleted"
    WORKFLOW_FAILED = "WorkflowFailed"
    TASK_CREATED = "TaskCreated"
    TASK_STARTED = "TaskStarted"
    TASK_RETRIED = "TaskRetried"
    TASK_COMPLETED = "TaskCompleted"
    TASK_FAILED = "TaskFailed"
    AGENT_STARTED = "AgentStarted"
    AGENT_COMPLETED = "AgentCompleted"
    AGENT_FAILED = "AgentFailed"
    TOOL_CALL_REQUESTED = "ToolCallRequested"
    TOOL_CALL_STARTED = "ToolCallStarted"
    TOOL_CALL_COMPLETED = "ToolCallCompleted"
    TOOL_CALL_FAILED = "ToolCallFailed"
    MEMORY_CREATED = "MemoryCreated"
    MEMORY_UPDATED = "MemoryUpdated"
    MEMORY_REJECTED = "MemoryRejected"
    MEMORY_ROLLED_BACK = "MemoryRolledBack"
    EVIDENCE_CREATED = "EvidenceCreated"
    CLAIM_CREATED = "ClaimCreated"
    DECISION_CREATED = "DecisionCreated"
    APPROVAL_REQUESTED = "ApprovalRequested"
    APPROVAL_GRANTED = "ApprovalGranted"
    APPROVAL_REJECTED = "ApprovalRejected"
    SANDBOX_STARTED = "SandboxStarted"
    SANDBOX_COMPLETED = "SandboxCompleted"
    SANDBOX_FAILED = "SandboxFailed"
    IMPROVEMENT_PROPOSED = "ImprovementProposed"
    IMPROVEMENT_APPROVED = "ImprovementApproved"
    IMPROVEMENT_REJECTED = "ImprovementRejected"
    IMPROVEMENT_DEPLOYED = "ImprovementDeployed"


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass
class VersionedEntity:
    id: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    version: int = 1

    def touch(self) -> None:
        self.updated_at = utc_now()
        self.version += 1


@dataclass
class TenantScopedEntity(VersionedEntity):
    tenant_id: str = "default"
    owner_id: str | None = None
    lifecycle_state: LifecycleState = LifecycleState.CREATED


@dataclass
class User(TenantScopedEntity):
    email: str = ""


@dataclass
class Tenant(VersionedEntity):
    name: str = "default"
    lifecycle_state: LifecycleState = LifecycleState.CREATED


@dataclass
class AgentRole(TenantScopedEntity):
    name: str = "agent"
    permissions: tuple[str, ...] = ()


@dataclass
class AgentCapability(TenantScopedEntity):
    name: str = ""
    risk_level: str = "LOW"


@dataclass
class Agent(TenantScopedEntity):
    role_id: str = ""
    capabilities: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    allowed_resources: tuple[str, ...] = ()
    risk_level: str = "LOW"
    budget: dict[str, float] = field(default_factory=dict)
    timeout_seconds: int = 60
    max_iterations: int = 10
    max_tool_calls: int = 20


@dataclass
class Tool(TenantScopedEntity):
    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    required_capabilities: tuple[str, ...] = ()
    timeout_seconds: int = 30
    network_access: str = "none"
    filesystem_access: str = "none"


@dataclass
class Workflow(TenantScopedEntity):
    state: WorkflowState = WorkflowState.CREATED
    idempotency_key: str | None = None

    def transition_to(self, target: WorkflowState) -> None:
        if target not in WORKFLOW_TRANSITIONS[self.state]:
            raise DomainStateError(f"workflow cannot transition from {self.state} to {target}")
        self.state = target
        self.touch()


@dataclass
class Task(TenantScopedEntity):
    workflow_id: str = ""
    state: TaskState = TaskState.PENDING
    idempotency_key: str | None = None

    def transition_to(self, target: TaskState) -> None:
        if target not in TASK_TRANSITIONS[self.state]:
            raise DomainStateError(f"task cannot transition from {self.state} to {target}")
        self.state = target
        self.touch()


@dataclass(frozen=True)
class Event:
    event_type: EventType
    tenant_id: str
    event_id: str = field(default_factory=lambda: new_id("evt"))
    event_version: int = 1
    occurred_at: datetime = field(default_factory=utc_now)
    correlation_id: str | None = None
    request_id: str | None = None
    workflow_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    actor_id: str | None = None
    sequence: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowRun(TenantScopedEntity):
    workflow_id: str = ""
    current_state: WorkflowState = WorkflowState.CREATED
    checkpoint_id: str | None = None
    event_sequence: int = 0
    idempotency_key: str | None = None


@dataclass
class TaskRun(TenantScopedEntity):
    task_id: str = ""
    current_state: TaskState = TaskState.PENDING
    attempt: int = 0


@dataclass
class Checkpoint(TenantScopedEntity):
    workflow_run_id: str = ""
    event_sequence: int = 0
    state: dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence(TenantScopedEntity):
    source: str = ""
    source_type: str = "unknown"
    content_hash: str = ""
    trust_score: float = 0.0


@dataclass
class Claim(TenantScopedEntity):
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 0.0
    text: str = ""


@dataclass
class Decision(TenantScopedEntity):
    status: str = "proposed"
    risk_level: str = "LOW"
    evidence_ids: tuple[str, ...] = ()


@dataclass
class Approval(TenantScopedEntity):
    decision_id: str = ""
    approver_id: str = ""
    scope: str = ""
    expires_at: datetime | None = None


@dataclass
class Memory(TenantScopedEntity):
    memory_type: str = "semantic"
    content_hash: str = ""
    source: str = ""
    source_type: str = "unknown"
    confidence: float = 0.0
    evidence_ids: tuple[str, ...] = ()
    supersedes: str | None = None


@dataclass
class MemoryVersion(TenantScopedEntity):
    memory_id: str = ""
    version_number: int = 1
    content_hash: str = ""


@dataclass
class Entity(TenantScopedEntity):
    labels: tuple[str, ...] = ()
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class Relationship(TenantScopedEntity):
    source_entity_id: str = ""
    target_entity_id: str = ""
    relationship_type: str = "RELATED_TO"
    confidence: float = 0.0
    evidence_ids: tuple[str, ...] = ()


@dataclass
class Artifact(TenantScopedEntity):
    artifact_type: str = "unknown"
    content_hash: str = ""
    size_bytes: int = 0
    source_workflow_id: str | None = None


@dataclass
class Execution(TenantScopedEntity):
    tool_id: str = ""
    workflow_id: str | None = None
    task_id: str | None = None
    status: str = "created"


@dataclass
class Policy(TenantScopedEntity):
    name: str = ""
    rules: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditEvent(Event):
    pass


@dataclass
class ImprovementProposal(TenantScopedEntity):
    title: str = ""
    risk_level: str = "MEDIUM"
    status: str = "proposed"
    reversible: bool = True
