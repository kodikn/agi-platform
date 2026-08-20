from pathlib import Path

MANIFEST = Path("k8s/api.yaml").read_text()


def test_k8s_contains_required_production_resources():
    for kind in [
        "Deployment",
        "Service",
        "Ingress",
        "ConfigMap",
        "Secret",
        "ServiceAccount",
        "Role",
        "RoleBinding",
        "HorizontalPodAutoscaler",
        "PodDisruptionBudget",
        "NetworkPolicy",
    ]:
        assert f"kind: {kind}" in MANIFEST


def test_deployment_security_context_and_probes():
    assert "runAsNonRoot: true" in MANIFEST
    assert "allowPrivilegeEscalation: false" in MANIFEST
    assert "readOnlyRootFilesystem: true" in MANIFEST
    assert 'drop: ["ALL"]' in MANIFEST
    assert "startupProbe:" in MANIFEST
    assert "readinessProbe:" in MANIFEST
    assert "livenessProbe:" in MANIFEST
    assert "terminationGracePeriodSeconds: 45" in MANIFEST
    assert "maxUnavailable: 0" in MANIFEST


def test_k8s_availability_and_network_controls():
    assert "minAvailable: 2" in MANIFEST
    assert "averageUtilization: 65" in MANIFEST
    assert "http_request_duration_seconds_p95" in MANIFEST
    assert "type: ClusterIP" in MANIFEST
    assert "agi-platform-databases-not-public" in MANIFEST
    for port in ["5432", "6379", "6333", "7687"]:
        assert f"port: {port}" in MANIFEST
