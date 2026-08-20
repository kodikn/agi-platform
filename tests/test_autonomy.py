from agi_platform.autonomy import ArchitectureAutonomyController
from agi_platform.governance.core import ArchitectureGovernance


class DummyLLM:
    def models(self):
        return {"providers": {"local": {"configured": True}}}


class DummyService:
    llm = DummyLLM()

    def health(self):
        return {"status": "ok"}

    def levels(self):
        return [{} for _ in range(12)]

    def external_memory_health(self):
        return {"status": "disabled"}


def test_self_test_passes_with_configured_local_model():
    report = ArchitectureAutonomyController().self_test(DummyService())
    assert report["status"] == "passed"
    assert any(check["name"] == "model_provider" for check in report["checks"])


def test_self_improvement_proposals_require_human_approval():
    controller = ArchitectureAutonomyController()
    governance = ArchitectureGovernance()
    report = {"checks": [{"name": "model_provider", "status": "needs-configuration", "detail": {}}]}
    result = controller.propose_improvements(report, governance)
    assert result["auto_apply"] is False
    assert result["approval_required"] is True
    assert result["proposals"][0]["status"] == "needs-review"


def test_self_improvement_proposals_do_not_duplicate_pending_reviews():
    controller = ArchitectureAutonomyController()
    governance = ArchitectureGovernance()
    report = {"checks": [{"name": "model_provider", "status": "needs-configuration", "detail": {}}]}
    first = controller.propose_improvements(report, governance)
    second = controller.propose_improvements(report, governance)
    assert first["proposals"][0]["decision_id"] == second["proposals"][0]["decision_id"]
    assert len(governance.decisions) == 1
