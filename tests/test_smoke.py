"""Tier 1: Pod health and service endpoint smoke tests.

These tests verify the cluster state without sending any telemetry data.
Fast and safe to run at any time.
"""

import json

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
    "allow-heartbeat-egress",
    "allow-heartbeat-splunk-egress",
    "allow-heartbeat-edge-egress",
    "allow-heartbeat-otel-egress",
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


MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

MCP_INITIALIZE_PAYLOAD = {
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "1.0"},
    },
    "id": 1,
}


@pytest.mark.usefixtures("cluster_ready")
class TestMcpServerNodePort:
    """Verify the Cribl MCP server is reachable from macOS via NodePort :30030.

    These tests hit localhost:30030 directly — the same path Claude Code uses —
    NOT via kubectl port-forward. They guarantee that the NodePort routing works
    and the MCP Streamable HTTP protocol (2025-03-26) is responding correctly.

    The server uses POST-based Streamable HTTP transport (not the older GET/SSE
    transport). Each request is a POST to /mcp with Content-Type: application/json
    and Accept: application/json, text/event-stream.
    """

    def _post(self, payload: dict) -> requests.Response:
        """POST a JSON-RPC message to the MCP NodePort. Fails the test on connection error."""
        try:
            return requests.post(
                MCP_NODEPORT_URL,
                json=payload,
                headers=MCP_HEADERS,
                stream=True,
                timeout=(5, 5),
            )
        except requests.exceptions.ConnectionError as exc:
            pytest.fail(
                f"Cannot connect to MCP server at {MCP_NODEPORT_URL} via NodePort. "
                f"Is the cluster running? (make deploy-doppler)\n{exc}"
            )

    def _read_sse_data(self, resp: requests.Response) -> dict:
        """Read the first SSE data event from a streaming response and parse as JSON."""
        try:
            for line in resp.iter_lines(decode_unicode=True):
                if line.startswith("data: "):
                    return json.loads(line[6:].strip())
        except requests.exceptions.ReadTimeout:
            pytest.fail(f"MCP server at {MCP_NODEPORT_URL} did not respond within 5s.")
        finally:
            resp.close()
        pytest.fail("MCP server returned no SSE data event.")

    def test_mcp_initialize_returns_200(self):
        """MCP server should accept initialize requests with 200 OK."""
        resp = self._post(MCP_INITIALIZE_PAYLOAD)
        assert resp.status_code == 200, f"MCP server returned {resp.status_code} — expected 200"
        resp.close()

    def test_mcp_response_content_type(self):
        """MCP endpoint should respond with SSE content-type (text/event-stream)."""
        resp = self._post(MCP_INITIALIZE_PAYLOAD)
        content_type = resp.headers.get("content-type", "")
        resp.close()
        assert "text/event-stream" in content_type, (
            f"Expected SSE content-type (text/event-stream), got: '{content_type}'. "
            f"The MCP server may be misconfigured or not fully started."
        )

    def test_mcp_initialize_protocol_version(self):
        """MCP server should negotiate the 2025-03-26 protocol version.

        The MCP Streamable HTTP transport (2025-03-26) works as follows:
          1. Client POSTs initialize to /mcp with Accept: application/json, text/event-stream
          2. Server returns 200 with SSE stream
          3. SSE stream contains a message event with the initialize result

        This test verifies the server correctly handles the handshake and returns
        a valid protocol version and server info.
        """
        resp = self._post(MCP_INITIALIZE_PAYLOAD)
        data = self._read_sse_data(resp)

        assert "result" in data, f"Expected 'result' in MCP initialize response, got: {data}"
        result = data["result"]
        assert result.get("protocolVersion") == "2025-03-26", (
            f"Expected protocolVersion '2025-03-26', got: '{result.get('protocolVersion')}'"
        )
        assert "serverInfo" in result, f"Expected 'serverInfo' in result, got: {result}"


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
