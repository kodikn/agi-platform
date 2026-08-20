import pytest

from agi_platform.domain import (
    DomainConcurrencyError,
    DomainStateError,
    Event,
    EventType,
    ToolPermission,
    Task,
    TaskState,
    Workflow,
    WorkflowState,
)


def test_workflow_state_machine_allows_valid_transitions():
    workflow = Workflow(id="wf_1", tenant_id="tenant_a")
    workflow.transition_to(WorkflowState.PLANNED)
    workflow.transition_to(WorkflowState.RUNNING)
    workflow.transition_to(WorkflowState.COMPLETED)
    assert workflow.state == WorkflowState.COMPLETED
    assert workflow.version == 4


def test_workflow_state_machine_rejects_invalid_transitions():
    workflow = Workflow(id="wf_1", tenant_id="tenant_a")
    with pytest.raises(DomainStateError):
        workflow.transition_to(WorkflowState.COMPLETED)


def test_task_state_machine_rejects_terminal_mutation():
    task = Task(id="task_1", tenant_id="tenant_a", workflow_id="wf_1")
    task.transition_to(TaskState.READY)
    task.transition_to(TaskState.RUNNING)
    task.transition_to(TaskState.COMPLETED)
    with pytest.raises(DomainStateError):
        task.transition_to(TaskState.RUNNING)


def test_event_shape_is_tenant_aware_correlatable_and_immutable():
    event = Event(
        event_type=EventType.WORKFLOW_CREATED,
        tenant_id="tenant_a",
        correlation_id="corr_1",
        request_id="req_1",
        workflow_id="wf_1",
        actor_id="user_1",
        sequence=1,
        payload={"state": "CREATED"},
    )
    assert event.event_id.startswith("evt_")
    assert event.event_version == 1
    assert event.tenant_id == "tenant_a"
    with pytest.raises(Exception):
        event.tenant_id = "tenant_b"


def test_workflow_transition_returns_actor_attributed_audit_event():
    workflow = Workflow(id="wf_2", tenant_id="tenant_a")
    event = workflow.transition_to(
        WorkflowState.PLANNED,
        actor_id="user_1",
        expected_version=1,
        correlation_id="corr_2",
        request_id="req_2",
    )
    assert event.event_type == EventType.WORKFLOW_STATE_TRANSITIONED
    assert event.workflow_id == "wf_2"
    assert event.actor_id == "user_1"
    assert event.correlation_id == "corr_2"
    assert event.payload == {"from_state": "CREATED", "to_state": "PLANNED", "entity_version": 2}


def test_task_transition_uses_optimistic_concurrency():
    task = Task(id="task_2", tenant_id="tenant_a", workflow_id="wf_2")
    with pytest.raises(DomainConcurrencyError):
        task.transition_to(TaskState.READY, expected_version=99)


def test_tool_permission_is_tenant_scoped_domain_object():
    permission = ToolPermission(id="perm_1", tenant_id="tenant_a", tool_id="tool_1", capability="sandbox:execute", risk_level="HIGH")
    assert permission.tenant_id == "tenant_a"
    assert permission.action == "execute"
    assert permission.version == 1
