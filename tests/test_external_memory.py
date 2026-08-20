from agi_platform.external_memory import ExternalMemoryAsset, ExternalMemorySettings, TencentDBMemoryConnector


def test_disabled_connector_is_safe_and_read_only():
    connector = TencentDBMemoryConnector(ExternalMemorySettings(enabled=False))
    assert connector.health()["status"] == "disabled"
    assert connector.search_assets("agent memory") == []
    assert connector.get_asset("asset-1") is None


def test_external_asset_converts_to_memory_result_with_provenance():
    asset = ExternalMemoryAsset(
        id="asset-1",
        asset_type="wiki",
        title="Runbook",
        content="Use guarded deployments",
        score=0.91,
        visibility="team",
        version="v2",
        metadata={"owner": "platform"},
    )
    result = asset.to_memory_result()
    assert result["id"] == "asset-1"
    assert result["source"] == "tencentdb_agent_memory"
    assert result["memory_type"] == "wiki"
    assert result["metadata"]["owner"] == "platform"


def test_external_asset_payload_handles_bad_score_and_deterministic_id():
    payload = {"title": "Bad score", "summary": "content", "score": "not-a-number", "metadata": ["bad"]}
    first = TencentDBMemoryConnector._asset_from_payload(payload)
    second = TencentDBMemoryConnector._asset_from_payload(payload)
    assert first.id == second.id
    assert first.score == 0.0
    assert first.metadata == {}


def test_get_asset_url_encodes_asset_id(monkeypatch):
    seen = {}

    def fake_request(self, method, path, payload=None):
        seen["path"] = path
        return {"id": "asset/1"}

    monkeypatch.setattr(TencentDBMemoryConnector, "_request", fake_request)
    connector = TencentDBMemoryConnector(ExternalMemorySettings(enabled=True, base_url="http://memory.local"))
    assert connector.get_asset("asset/1") == {"id": "asset/1"}
    assert seen["path"] == "/assets/asset%2F1"
