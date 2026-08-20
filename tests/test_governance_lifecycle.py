import time

import pytest

from agi_platform.evolution.core import SelfImprovementEngine


def prepared_engine():
    engine = SelfImprovementEngine()
    proposal = engine.create_proposal(
        "tenant-a", "agent-a", "safe change", {"actions": ["deploy"]}, risk="high"
    )
    engine.record_benchmark(proposal["id"], {"success_rate": 0.99, "failure_rate": 0.0})
    engine.assess_risk(proposal["id"], ["production change"], high_risk=True)
    return engine, proposal


def test_unauthorized_deployment_and_approval_bypass_denied():
    engine, proposal = prepared_engine()
    with pytest.raises(PermissionError):
        engine.deploy(proposal["id"], "tenant-a", "agent-a", canary_passed=True)


def test_expired_and_wrong_tenant_approval_denied():
    engine, proposal = prepared_engine()
    with pytest.raises(PermissionError):
        engine.approve(proposal["id"], "tenant-b", "approver", int(time.time()) + 60)
    engine.approve(proposal["id"], "tenant-a", "approver", int(time.time()) - 1)
    with pytest.raises(PermissionError):
        engine.deploy(proposal["id"], "tenant-a", "agent-a", canary_passed=True)


def test_failed_canary_rolls_back_and_audit_is_recorded():
    engine, proposal = prepared_engine()
    engine.approve(proposal["id"], "tenant-a", "approver", int(time.time()) + 60)
    result = engine.deploy(proposal["id"], "tenant-a", "agent-a", canary_passed=False)
    assert result["reason"] == "failed canary"
    assert proposal["id"] in engine.rollbacks
    assert any(
        event["action"] == "deployment.rollback" and event["result"] == "allowed"
        for event in engine.audit_events
    )
