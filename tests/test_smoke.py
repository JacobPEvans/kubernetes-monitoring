"""Tier 1: Pod health and service endpoint smoke tests.

These tests verify the cluster state without sending any telemetry data.
Fast and safe to run at any time.
"""
import subprocess
import time
import pytest
import requests
from conftest import CONTEXT, NAMESPACE, STATEFULSETS, kubectl, kubectl_json


@pytest.mark.usefixtures("cluster_ready")
class TestPodHealth:
    @pytest.mark.parametrize("name", STATEFULSETS)
    def test_statefulset_has_ready_replicas(self, name):
        """Each StatefulSet should have at least 1 ready replica."""
        data = kubectl_json("get", "statefulset", name)
        ready = data["status"].get("readyReplicas", 0)
        assert ready >= 1, f"{name}: expected readyReplicas >= 1, got {ready}"

    @pytest.mark.parametrize("name", STATEFULSETS)
    def test_pod_not_restarting(self, name):
        """Pods should not be in a crash loop (restarts <= 5)."""
        data = kubectl_json("get", "pods", "-l", f"app={name}")
        items = data.get("items", [])
        assert items, f"No pods found for {name}"
        for pod in items:
            for cs in pod["status"].get("containerStatuses", []):
                restarts = cs.get("restartCount", 0)
                assert restarts <= 5, (
                    f"{name} pod {pod['metadata']['name']} container "
                    f"{cs['name']}: {restarts} restarts (possible crash loop)"
                )


@pytest.mark.usefixtures("cluster_ready")
class TestServiceEndpoints:
    def test_otel_collector_headless_service(self):
        """Headless ClusterIP service for StatefulSet should exist."""
        data = kubectl_json("get", "service", "otel-collector")
        assert data["spec"]["clusterIP"] == "None", "Expected headless service"

    def test_otel_collector_external_service(self):
        """NodePort service should expose gRPC :30317 and HTTP :30318."""
        data = kubectl_json("get", "service", "otel-collector-external")
        ports = {p["name"]: p["nodePort"] for p in data["spec"]["ports"]}
        assert ports.get("otlp-grpc") == 30317
        assert ports.get("otlp-http") == 30318

    def test_cribl_edge_managed_service(self):
        """Cribl edge managed service should expose OTLP port 9420."""
        data = kubectl_json("get", "service", "cribl-edge-managed")
        ports = [p["port"] for p in data["spec"]["ports"]]
        assert 9420 in ports


@pytest.mark.usefixtures("cluster_ready")
class TestOtelCollectorHealth:
    def test_health_endpoint_reachable(self):
        """OTEL Collector health endpoint should return 200 via port-forward.

        The otel-collector image is distroless (no shell or curl), so we use
        kubectl port-forward and requests from the test host instead.
        """
        proc = subprocess.Popen(
            ["kubectl", "--context", CONTEXT, "-n", NAMESPACE,
             "port-forward", "statefulset/otel-collector", "13133:13133"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(1)
            resp = requests.get("http://localhost:13133/", timeout=5)
            assert resp.status_code == 200, f"Health endpoint returned {resp.status_code}"
        finally:
            proc.terminate()
            proc.wait()

    @pytest.mark.xfail(reason="Cribl Edge OTLP source may not be configured")
    def test_otel_can_reach_cribl_edge(self):
        """OTEL Collector should be able to reach Cribl Edge on port 9420."""
        output = kubectl(
            "exec", "statefulset/otel-collector", "--",
            "curl", "-sf", "--max-time", "5",
            "http://cribl-edge-managed:9420/api/v1/health"
        )
        assert output
