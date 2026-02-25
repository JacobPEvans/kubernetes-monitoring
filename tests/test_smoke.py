"""Tier 1: Pod health and service endpoint smoke tests.

These tests verify the cluster state without sending any telemetry data.
Fast and safe to run at any time.
"""
import subprocess
import time
import pytest
import requests
from conftest import CONTEXT, NAMESPACE, STATEFULSETS, kubectl_json


def _port_forward_health(statefulset: str, container_port: int, local_port: int, path: str = "/api/v1/health") -> requests.Response:
    """Port-forward to a StatefulSet and GET the given health path.

    Uses the same pattern as TestOtelCollectorHealth.test_health_endpoint_reachable
    to avoid exec into distroless or restricted containers.
    """
    proc = subprocess.Popen(
        ["kubectl", "--context", CONTEXT, "-n", NAMESPACE,
         "port-forward", f"statefulset/{statefulset}", f"{local_port}:{container_port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        start_time = time.time()
        last_error = None
        timeout_seconds = 15
        while time.time() - start_time < timeout_seconds:
            if proc.poll() is not None:
                pytest.fail(
                    f"kubectl port-forward process exited before health check for {statefulset}; "
                    "port may already be in use."
                )
            try:
                resp = requests.get(f"http://localhost:{local_port}{path}", timeout=2)
                return resp
            except requests.exceptions.ConnectionError as exc:
                last_error = exc
                time.sleep(0.5)
        pytest.fail(
            f"Timed out after {timeout_seconds}s waiting for {statefulset} "
            f"health endpoint via port-forward: {last_error}"
        )
    finally:
        proc.terminate()
        proc.wait()


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

    def test_cribl_stream_standalone_ui_service(self):
        """Cribl Stream Standalone dedicated NodePort service should expose UI on :30900."""
        data = kubectl_json("get", "service", "cribl-stream-standalone-ui")
        port_map = {p["name"]: p.get("nodePort") for p in data["spec"]["ports"]}
        assert 30900 in port_map.values(), (
            f"Expected NodePort 30900 for Cribl Stream UI, got: {port_map}"
        )

    def test_cribl_edge_standalone_ui_service(self):
        """Cribl Edge Standalone dedicated NodePort service should expose UI on :30910."""
        data = kubectl_json("get", "service", "cribl-edge-standalone-ui")
        port_map = {p["name"]: p.get("nodePort") for p in data["spec"]["ports"]}
        assert 30910 in port_map.values(), (
            f"Expected NodePort 30910 for Cribl Edge UI, got: {port_map}"
        )


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
            start_time = time.time()
            last_error = None
            timeout_seconds = 10
            while time.time() - start_time < timeout_seconds:
                if proc.poll() is not None:
                    pytest.fail(
                        "kubectl port-forward process exited before health check; "
                        "port-forward may have failed to start."
                    )
                try:
                    resp = requests.get("http://localhost:13133/", timeout=2)
                    assert resp.status_code == 200, (
                        f"Health endpoint returned {resp.status_code}"
                    )
                    break
                except requests.exceptions.ConnectionError as exc:
                    last_error = exc
                    time.sleep(0.5)
            else:
                pytest.fail(
                    f"Timed out after {timeout_seconds}s waiting for OTEL Collector "
                    f"health endpoint via port-forward: {last_error}"
                )
        finally:
            proc.terminate()
            proc.wait()


@pytest.mark.usefixtures("cluster_ready")
class TestCriblHealth:
    def test_cribl_stream_standalone_health(self):
        """Cribl Stream Standalone /api/v1/health should return 200 via port-forward.

        Cribl Stream API is on port 9000 (not 9420 which is only used by Cribl Edge).
        """
        resp = _port_forward_health("cribl-stream-standalone", 9000, 19420)
        assert resp.status_code == 200, (
            f"Cribl Stream health returned {resp.status_code}: {resp.text[:200]}"
        )

    def test_cribl_edge_standalone_health(self):
        """Cribl Edge Standalone /api/v1/health should return 200 via port-forward."""
        resp = _port_forward_health("cribl-edge-standalone", 9420, 19421)
        assert resp.status_code == 200, (
            f"Cribl Edge health returned {resp.status_code}: {resp.text[:200]}"
        )
