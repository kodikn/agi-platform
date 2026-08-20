import copy

from agi_platform.database import Base

from agi_platform.services import MemoryRequest, PlatformService, WorkflowRequest
from agi_platform.security import Identity, TenantContext


def test_automated_restore_drill_memory_workflow_and_tenant_isolation():
    service = PlatformService()
    tenant_a = TenantContext(
        "tenant-a",
        Identity("actor-a", "tenant-a", frozenset(), frozenset({"*"})),
        "rid-a",
    )
    tenant_b = TenantContext(
        "tenant-b",
        Identity("actor-b", "tenant-b", frozenset(), frozenset({"*"})),
        "rid-b",
    )
    service.store_memory(MemoryRequest(content="tenant-a critical memory"), tenant_a)
    service.store_memory(MemoryRequest(content="tenant-b critical memory"), tenant_b)
    workflow = service.workflow.plan(WorkflowRequest(task="recover me").task, None)

    backup = {
        "memory": list(service.memory.records.values()),
        "workflows": copy.deepcopy(service.workflow.state_store.list()),
    }

    service.memory.records.clear()
    Base.metadata.drop_all(service.workflow.state_store.database.engine)
    service.workflow.state_store.database.create_all()
    service.workflow.state_store.database.ensure_tenant(
        service.workflow.state_store.tenant_id
    )

    for item in backup["memory"]:
        ctx = tenant_a if item["tenant_id"] == "tenant-a" else tenant_b
        service.memory.store(
            item["content"], item["memory_type"], item["metadata"], ctx
        )
    for wf in backup["workflows"]:
        service.workflow.state_store.append(wf)

    assert service.search_memory.__self__.memory.search("critical", 10, tenant_a)[
        "results"
    ]
    assert all(
        item["tenant_id"] == "tenant-a"
        for item in service.memory.search("critical", 10, tenant_a)["results"]
    )
    assert service.workflow.recover(workflow["checkpoint"])["status"] == "recovered"
