from sqlalchemy import create_engine

from agi_platform.database import Database
from agi_platform.orchestration import WorkflowEngine, WorkflowStateStore


def workflow_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'workflow.sqlite3'}", future=True)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    return WorkflowStateStore(Database(engine), tenant_id="tenant-a")


def test_workflow_recovers_after_restart(tmp_path):
    store = workflow_store(tmp_path)
    engine = WorkflowEngine(store)
    planned = engine.plan("durable work", ["architect"])
    restarted = WorkflowEngine(WorkflowStateStore(store.database, tenant_id="tenant-a"))
    recovered = restarted.recover(planned["checkpoint"])
    assert recovered["status"] == "recovered"
    assert restarted.execute(planned["checkpoint"])["status"] == "completed"


def test_duplicate_task_and_two_workers_do_not_share_lease(tmp_path):
    store = workflow_store(tmp_path)
    checkpoint = WorkflowEngine(store).plan("lease work", ["architect"])["checkpoint"]
    first = store.lease_next_task(checkpoint, "worker-1")
    second = store.lease_next_task(checkpoint, "worker-2")
    assert first is not None
    assert second is None
    assert store.mark_task_succeeded(first, "worker-2") is False
    assert store.mark_task_succeeded(first, "worker-1") is True


def test_worker_timeout_recovery(tmp_path):
    store = workflow_store(tmp_path)
    checkpoint = WorkflowEngine(store).plan("timeout work", ["architect"])["checkpoint"]
    task_id = store.lease_next_task(checkpoint, "worker-1", lease_seconds=-1)
    assert task_id is not None
    assert store.recover_expired_leases() == 1
    assert store.lease_next_task(checkpoint, "worker-2") == task_id


def test_db_disconnect_failure_is_explicit(tmp_path):
    store = workflow_store(tmp_path)
    store.database.engine.dispose()
    assert isinstance(store.database.healthy(), bool)
