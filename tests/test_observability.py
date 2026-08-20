import json
import logging

from fastapi.testclient import TestClient

from api.main import app
from agi_platform.telemetry import JsonLogFormatter

client = TestClient(app)


def test_live_and_ready_are_different_contracts():
    live = client.get("/live")
    ready = client.get("/ready")
    assert live.status_code == 200
    assert live.json()["status"] == "alive"
    assert "levels" in ready.json()


def test_request_and_trace_ids_are_returned_and_metrics_recorded():
    response = client.get("/health", headers={"X-Request-ID": "rid-observe"})
    assert response.headers["X-Request-ID"] == "rid-observe"
    assert response.headers["Trace-ID"]
    metrics = client.get("/metrics").text
    assert "http_requests_total" in metrics
    assert "http_request_latency_ms" in metrics


def test_json_log_formatter_redacts_sensitive_fields():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "event", (), None)
    record.request_id = "rid"
    record.trace_id = "tid"
    record.api_key = "agi_secret"
    record.password = "super-secret"
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["request_id"] == "rid"
    assert payload["trace_id"] == "tid"
    assert payload["api_key"] == "[REDACTED]"
    assert payload["password"] == "[REDACTED]"
