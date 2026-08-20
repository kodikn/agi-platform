import pytest

from agi_platform.domain import (
    DomainStateError,
    Event,
    EventType,
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
