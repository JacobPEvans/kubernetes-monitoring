"""Tier 1: Pod health and service endpoint smoke tests.

These tests verify the cluster state without sending any telemetry data.
Fast and safe to run at any time.
"""

import pytest
import requests
from conftest import (
    MCP_NODEPORT_URL,
    PF_EDGE_HEALTH,
    PF_OTEL_HEALTH,
    PF_STREAM_HEALTH,
    STATEFULSETS,
    kubectl_json,
    port_forward_get,
)

EXPECTED_NETWORK_POLICIES = [
    "default-deny-all",
    "allow-dns-egress",
    "allow-otel-ingress",
    "allow-otel-egress",
    "allow-edge-managed-egress",
    "allow-edge-standalone-egress",
    "allow-edge-standalone-ui-ingress",
    "allow-stream-ingress",
    "allow-stream-egress",
    "allow-stream-ui-ingress",
    "allow-mcp-egress",
    "allow-mcp-ingress",
]


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
        assert 30900 in port_map.values(), f"Expected NodePort 30900 for Cribl Stream UI, got: {port_map}"

    def test_cribl_edge_standalone_ui_service(self):
        """Cribl Edge Standalone dedicated NodePort service should expose UI on :30910."""
        data = kubectl_json("get", "service", "cribl-edge-standalone-ui")
        port_map = {p["name"]: p.get("nodePort") for p in data["spec"]["ports"]}
        assert 30910 in port_map.values(), f"Expected NodePort 30910 for Cribl Edge UI, got: {port_map}"

    def test_cribl_mcp_server_service(self):
        """Cribl MCP Server NodePort service should expose MCP endpoint on :30030."""
        data = kubectl_json("get", "service", "cribl-mcp-server-nodeport")
        port_map = {p["name"]: p.get("nodePort") for p in data["spec"]["ports"]}
        assert 30030 in port_map.values(), f"Expected NodePort 30030 for Cribl MCP Server, got: {port_map}"


@pytest.mark.usefixtures("cluster_ready")
class TestOtelCollectorHealth:
    def test_health_endpoint_reachable(self):
        """OTEL Collector health endpoint should return 200 via port-forward.

        The otel-collector image is distroless (no shell or curl), so we use
        kubectl port-forward and requests from the test host instead.
        """
        resp = port_forward_get("otel-collector", 13133, PF_OTEL_HEALTH)
        assert resp.status_code == 200, f"OTEL Collector health endpoint returned {resp.status_code}"


@pytest.mark.usefixtures("cluster_ready")
class TestCriblHealth:
    def test_cribl_stream_standalone_health(self):
        """Cribl Stream Standalone /api/v1/health should return 200 via port-forward.

        Cribl Stream API is on port 9000 (not 9420 which is only used by Cribl Edge).
        """
        resp = port_forward_get("cribl-stream-standalone", 9000, PF_STREAM_HEALTH, path="/api/v1/health")
        assert resp.status_code == 200, f"Cribl Stream health returned {resp.status_code}: {resp.text[:200]}"

    def test_cribl_edge_standalone_health(self):
        """Cribl Edge Standalone /api/v1/health should return 200 via port-forward."""
        resp = port_forward_get("cribl-edge-standalone", 9420, PF_EDGE_HEALTH, path="/api/v1/health")
        assert resp.status_code == 200, f"Cribl Edge health returned {resp.status_code}: {resp.text[:200]}"


@pytest.mark.usefixtures("cluster_ready")
class TestMcpServerNodePort:
    """Verify the Cribl MCP server is reachable from macOS via NodePort :30030.

    These tests hit localhost:30030 directly — the same path Claude Code uses —
    NOT via kubectl port-forward. They guarantee that the NodePort routing works
    and the MCP SSE protocol is responding correctly end-to-end.
    """

    def _connect(self) -> requests.Response:
        """Open a streaming GET to the MCP NodePort. Fails the test on connection error."""
        try:
            return requests.get(MCP_NODEPORT_URL, stream=True, timeout=(5, 5))
        except requests.exceptions.ConnectionError as exc:
            pytest.fail(
                f"Cannot connect to MCP server at {MCP_NODEPORT_URL} via NodePort. "
                f"Is the cluster running? (make deploy-doppler)\n{exc}"
            )

    def test_mcp_returns_200(self):
        """MCP server NodePort :30030 should accept HTTP connections from macOS."""
        resp = self._connect()
        assert resp.status_code == 200, f"MCP server returned {resp.status_code} — expected 200"
        resp.close()

    def test_mcp_sse_content_type(self):
        """MCP endpoint should respond with SSE content-type (text/event-stream)."""
        resp = self._connect()
        content_type = resp.headers.get("content-type", "")
        resp.close()
        assert "text/event-stream" in content_type, (
            f"Expected SSE content-type (text/event-stream), got: '{content_type}'. "
            f"The MCP server may be misconfigured or not fully started."
        )

    def test_mcp_sse_announces_session_endpoint(self):
        """MCP server should immediately announce a session endpoint via the SSE stream.

        The MCP SSE transport works as follows:
          1. Claude Code opens GET /mcp → receives an SSE stream
          2. Server sends: data: /mcp/sessions/<id>   (session endpoint)
          3. Claude Code POSTs JSON-RPC messages to that session URL

        This test verifies step 2 — that the server announces the session endpoint
        within 5 seconds of the connection being established.
        """
        resp = self._connect()
        data_line = None
        try:
            for line in resp.iter_lines(decode_unicode=True):
                if line.startswith("data: "):
                    data_line = line[6:].strip()
                    break
        except requests.exceptions.ReadTimeout:
            pytest.fail(
                f"MCP server at {MCP_NODEPORT_URL} did not send a session endpoint "
                f"event within 5s. The server may be starting up or misconfigured."
            )
        finally:
            resp.close()

        assert data_line is not None, (
            "MCP server opened SSE stream but sent no data event. "
            "Expected a session endpoint announcement (e.g. /mcp/sessions/<id>)."
        )
        assert data_line.startswith("/"), (
            f"Expected session endpoint to be a relative path (e.g. /mcp/sessions/...), got: '{data_line}'"
        )


@pytest.mark.usefixtures("cluster_ready")
class TestNetworkPolicies:
    @pytest.mark.parametrize("name", EXPECTED_NETWORK_POLICIES)
    def test_network_policy_exists(self, name):
        """Each expected NetworkPolicy should exist in the monitoring namespace."""
        data = kubectl_json("get", "networkpolicy", name)
        assert data["metadata"]["name"] == name


@pytest.mark.usefixtures("cluster_ready")
class TestPodDisruptionBudgets:
    @pytest.mark.parametrize("name", STATEFULSETS)
    def test_pdb_exists(self, name):
        """Each StatefulSet should have a corresponding PodDisruptionBudget."""
        data = kubectl_json("get", "pdb", name)
        assert data["metadata"]["name"] == name
