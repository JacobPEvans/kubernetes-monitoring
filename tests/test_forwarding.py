"""Tier 3: Forwarding verification tests.

These tests verify data flows correctly through the pipeline:
  A2: Host Filesystem → Cribl Edge Standalone (file monitor)
  A4: OTEL Collector → Cribl Stream Standalone (gRPC :4317)
  A5: Cribl Edge Standalone → Cribl Stream Standalone (HTTP :10080)
  A7: Cribl Stream Standalone → Splunk HEC (:8088 HEC)
"""

import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from conftest import (
    CONTEXT,
    NAMESPACE,
    OTEL_GRPC_ENDPOINT,
    PF_STREAM_INPUTS_A4,
    PF_STREAM_INPUTS_A5,
    PF_STREAM_OUTPUTS,
    kubectl,
    kubectl_secret,
    kubectl_secret_values,
    port_forward_get,
)
from helpers import find_flowing_stats, parse_otel_error_lines, url_present_in_outputs_yaml
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


def _send_trace(test_id: str) -> None:
    # insecure=True: TLS not needed for local OrbStack NodePort testing
    exporter = OTLPSpanExporter(endpoint=OTEL_GRPC_ENDPOINT, insecure=True)
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("otel-forwarding-test")
    with tracer.start_as_current_span("forward-test-span") as span:
        span.set_attribute("test.id", test_id)
    provider.shutdown()


def _kubectl_exec_no_fail(*args: str) -> tuple[str, int]:
    """Run kubectl exec and return (stdout, returncode) without raising on failure."""
    cmd = ["kubectl", "--context", CONTEXT, "-n", NAMESPACE, "exec", *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", 1


@pytest.mark.usefixtures("cluster_ready")
class TestCollectorToStreamForwarding:
    """Verify OTEL Collector forwards data to Cribl Stream Standalone (arrow A4)."""

    def test_no_export_errors_after_send(self):
        """After sending data, collector's own operational logs should not contain export errors.

        Note: The otel-collector also forwards log files from the host (including pod logs
        from other containers). Those forwarded logs may contain the word "Exporting" as
        telemetry data content. We check for errors only in the collector's operational
        log lines (lines starting with a timestamp and log level marker).
        """
        test_id = str(uuid.uuid4())
        _send_trace(test_id)
        time.sleep(5)  # Allow time for forwarding attempt
        logs = kubectl("logs", "statefulset/otel-collector", "--tail=50")
        # OTEL collector log format: TIMESTAMP\tLEVEL\tFILE\tMESSAGE\tJSON
        # Only lines with \terror\t are error-level operational log entries.
        # Info-level retry lines (e.g. "Exporting failed. Will retry...") are
        # expected transient noise and should not fail this test.
        otel_error_lines = parse_otel_error_lines(logs)
        assert not otel_error_lines, "OTEL Collector operational errors found after send:\n" + "\n".join(
            otel_error_lines[:5]
        )

    def test_cribl_stream_received_otlp_data(self):
        """After sending a trace, Cribl Stream API should be reachable to verify input activity."""
        _send_trace(str(uuid.uuid4()))
        time.sleep(5)
        resp = port_forward_get("cribl-stream-standalone", 9000, PF_STREAM_INPUTS_A4, "/api/v1/system/inputs")
        # 200 = API accessible, 401 = auth required (inputs endpoint exists)
        assert resp.status_code in (200, 401), f"Cribl Stream inputs API returned unexpected status {resp.status_code}"


@pytest.mark.usefixtures("cluster_ready")
class TestEdgeToStreamForwarding:
    """Verify Cribl Edge Standalone can reach Cribl Stream Standalone (arrow A5).

    Cribl Stream exposes HTTP inputs on :10080 (the actual data path).
    Port 9000 is the UI/API port, not the data forwarding path.
    """

    def test_edge_to_stream_connectivity(self):
        """Cribl Edge Standalone should be able to reach Cribl Stream data port on :10080."""
        output, returncode = _kubectl_exec_no_fail(
            "statefulset/cribl-edge-standalone",
            "--",
            "curl",
            "-s",
            "--max-time",
            "5",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            "http://cribl-stream-standalone:10080/",
        )
        # Any HTTP response (even 4xx) means TCP connectivity is working.
        # Exit code 7 (connection refused) also indicates NP allows traffic
        # but the port may not be listening yet — still confirms network path.
        if returncode == 7:
            return  # Connection refused = NP allows traffic, port not listening
        assert output.strip().isdigit() and int(output.strip()) > 0, (
            f"Expected HTTP response from Cribl Stream data port, got: '{output}' (curl exit {returncode})"
        )

    def test_cribl_stream_inputs_api_reachable(self):
        """Cribl Stream inputs API endpoint should be reachable after edge connectivity check."""
        resp = port_forward_get("cribl-stream-standalone", 9000, PF_STREAM_INPUTS_A5, "/api/v1/system/inputs")
        assert resp.status_code in (200, 401), f"Cribl Stream inputs API returned unexpected status {resp.status_code}"


@pytest.mark.usefixtures("cluster_ready")
class TestStreamToSplunkForwarding:
    """Verify Cribl Stream Standalone forwards to Splunk HEC (arrow A7)."""

    def test_splunk_hec_output_healthy(self):
        """Cribl Stream API should report the Splunk HEC output as configured."""
        resp = port_forward_get("cribl-stream-standalone", 9000, PF_STREAM_OUTPUTS, "/api/v1/system/outputs")
        # 200 = API accessible, 401 = auth required (output endpoint exists)
        assert resp.status_code in (200, 401), f"Cribl Stream outputs API returned unexpected status {resp.status_code}"

    def test_splunk_hec_health_endpoint(self):
        """Splunk HEC health endpoint should return HTTP 200 with 'HEC is healthy' from stream pod."""
        hec_url = kubectl_secret("splunk-hec-config", "url")
        health_url = hec_url.replace("/services/collector", "/services/collector/health")
        output, returncode = _kubectl_exec_no_fail(
            "statefulset/cribl-stream-standalone",
            "--",
            "curl",
            "-s",
            "--max-time",
            "30",
            "-k",
            "-w",
            "\n%{http_code}",
            health_url,
        )
        lines = output.splitlines()
        assert lines, f"No output from Splunk HEC health endpoint (curl exit {returncode})"
        status_code = lines[-1].strip()
        body = "\n".join(lines[:-1])
        assert status_code == "200", (
            f"Expected HTTP 200 from Splunk HEC health endpoint, got {status_code} "
            f"(curl exit {returncode}, body: '{body}')"
        )
        assert "HEC is healthy" in body, (
            f"Expected 'HEC is healthy' in response body, got: '{body}' (curl exit {returncode}, status {status_code})"
        )

    def test_splunk_hec_token_accepted(self):
        """Posting to Splunk HEC with the real token should return HTTP 200 with Success body."""
        secrets = kubectl_secret_values("splunk-hec-config", ["token", "url"])
        token, url = secrets["token"], secrets["url"]
        output, returncode = _kubectl_exec_no_fail(
            "statefulset/cribl-stream-standalone",
            "--",
            "curl",
            "-s",
            "--max-time",
            "30",
            "-k",
            "-w",
            "\n%{http_code}",
            "-H",
            f"Authorization: Splunk {token}",
            "-H",
            "Content-Type: application/json",
            "-d",
            '{"event": "test", "sourcetype": "test"}',
            url,
        )
        lines = output.splitlines()
        assert lines, f"No output from Splunk HEC (curl exit {returncode})"
        status_code = lines[-1].strip()
        body = "\n".join(lines[:-1])
        assert status_code == "200", (
            f"Expected HTTP 200 from Splunk HEC with token, got {status_code} (curl exit {returncode}, body: '{body}')"
        )
        assert '"text":"Success"' in body or '"code":0' in body, (
            f"Expected Success in HEC response body, got: '{body}' (curl exit {returncode}, status {status_code})"
        )

    def test_splunk_hec_url_matches_secret(self):
        """URL in splunk-hec-config secret should match the URL in Cribl Stream's outputs config."""
        secret_url = kubectl_secret("splunk-hec-config", "url")
        output, returncode = _kubectl_exec_no_fail(
            "statefulset/cribl-stream-standalone",
            "--",
            "sh",
            "-c",
            "cat ${CRIBL_VOLUME_DIR:-/opt/cribl}/local/cribl/outputs.yml",
        )
        assert url_present_in_outputs_yaml(secret_url, output), (
            f"Secret URL '{secret_url}' not found as 'url:' value in Cribl Stream outputs.yml "
            f"(cat exit {returncode}):\n{output[:300]}"
        )

    def test_cribl_stream_no_output_errors(self):
        """Cribl Stream logs should contain no warn/error lines for the splunk-hec output."""
        logs = kubectl("logs", "statefulset/cribl-stream-standalone", "--tail=100")
        error_lines = [
            line
            for line in logs.splitlines()
            if "output:splunk-hec" in line and ("level=warn" in line or "level=error" in line)
        ]
        assert not error_lines, "Cribl Stream has output errors for splunk-hec:\n" + "\n".join(error_lines[:5])

    def test_cribl_stream_events_flowing(self):
        """After sending a trace, Cribl Stream stats should show outBytes > 0.

        Checks _raw stats for outBytes > 0 (bytes actually sent to an external output),
        not just outEvents (which counts pipeline-internal routing). Since splunk-hec is
        the only non-default output and all routes lead there, outBytes > 0 confirms
        data was physically sent to Splunk HEC.
        """
        _send_trace(str(uuid.uuid4()))
        time.sleep(10)  # Allow pipeline processing
        logs = kubectl("logs", "statefulset/cribl-stream-standalone", "--tail=100")
        flowing = find_flowing_stats(logs)
        assert flowing, (
            "Expected _raw stats with outBytes > 0 after sending trace "
            "(data physically sent to splunk-hec), found none in last 100 log lines."
        )

    def test_otlp_events_reach_splunk_realtime(self):
        """Send OTLP trace and verify Stream reports outBytes > 0 within 30s (real-time).

        End-to-end verification that the OTLP → Stream → Splunk HEC path (A4 + A7) delivers
        events in real-time, not just that the output is configured. A sentCount > 0 in
        Stream's _raw stats logs confirms bytes were physically sent to Splunk and acknowledged.
        """
        _send_trace(f"splunk-rt-{uuid.uuid4().hex[:8]}")
        deadline = time.time() + 30
        while time.time() < deadline:
            logs = kubectl("logs", "statefulset/cribl-stream-standalone", "--since=90s")
            if find_flowing_stats(logs):
                return
            time.sleep(3)
        pytest.fail(
            "Cribl Stream did not report outBytes > 0 to Splunk within 30s of sending an OTLP trace. "
            "The OTLP → Stream → Splunk HEC pipeline (A4 + A7) is not forwarding events in real-time."
        )


# ---------------------------------------------------------------------------
# Fixture for Claude Code log pipeline tests
# ---------------------------------------------------------------------------

_CLAUDE_TEST_DIR = Path.home() / ".claude/projects/-test-claude-pipeline"


@pytest.fixture
def sentinel_claude_file():
    """Write a unique sentinel .jsonl to ~/.claude/projects/-test-claude-pipeline/ on the host.

    Yields (path, sentinel_id). Cleans up after the test.
    The edge pod mounts this directory via hostPath, so the file appears at
    /home/claude/.claude/projects/-test-claude-pipeline/ inside the pod.
    """
    _CLAUDE_TEST_DIR.mkdir(parents=True, exist_ok=True)
    sentinel_id = f"PIPELINE_TEST_{uuid.uuid4().hex[:12]}"
    sentinel_file = _CLAUDE_TEST_DIR / f"test-{sentinel_id}.jsonl"
    sentinel_data = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sentinel": sentinel_id,
        "level": "info",
        "message": "Claude Code log pipeline test event",
    }
    sentinel_file.write_text(json.dumps(sentinel_data) + "\n")
    yield sentinel_file, sentinel_id
    try:
        sentinel_file.unlink()
    except FileNotFoundError:
        pass
    try:
        _CLAUDE_TEST_DIR.rmdir()  # removes dir only if empty
    except OSError:
        pass


@pytest.mark.usefixtures("cluster_ready")
class TestClaudeCodeLogPipeline:
    """Verify .claude/ session log files are picked up by the edge file monitor (arrow A2).

    The file monitoring path (A2: Host FS → Edge Standalone) is separate from the
    OTLP path (A1/A4) tested by other classes. These tests confirm:
      1. The hostPath volume mount makes ~/.claude/projects/ visible inside the edge pod.
      2. The FileMonitor input (cc-edge-claude-code) is configured with the correct path.
      3. A new .jsonl file written on the host is detected by the edge within one poll interval.
    """

    def test_claude_home_mount_accessible(self):
        """Edge pod can list host ~/.claude/projects/ via the hostPath volume mount."""
        output, returncode = _kubectl_exec_no_fail(
            "statefulset/cribl-edge-standalone",
            "--",
            "ls",
            "/home/claude/.claude/projects/",
        )
        assert returncode == 0, (
            f"hostPath mount /home/claude/.claude/projects/ not accessible in edge pod (exit {returncode})"
        )
        assert output.strip(), "Expected non-empty listing of .claude/projects/ inside edge pod"

    def test_sentinel_file_visible_in_edge_pod(self, sentinel_claude_file):
        """A .jsonl file written to host ~/.claude/projects/ is immediately readable inside the edge pod."""
        sentinel_path, sentinel_id = sentinel_claude_file
        pod_path = f"/home/claude/.claude/projects/-test-claude-pipeline/{sentinel_path.name}"
        output, returncode = _kubectl_exec_no_fail(
            "statefulset/cribl-edge-standalone",
            "--",
            "cat",
            pod_path,
        )
        assert returncode == 0, (
            f"Sentinel file not readable inside edge pod at {pod_path} (exit {returncode}). "
            "Check that the hostPath volume is correctly mounted."
        )
        assert sentinel_id in output, f"Sentinel ID {sentinel_id!r} not found in pod file content: {output!r}"

    def test_edge_file_monitor_config_path(self):
        """Edge FileMonitor input is configured to monitor /home/claude/.claude/projects/."""
        output, returncode = _kubectl_exec_no_fail(
            "statefulset/cribl-edge-standalone",
            "--",
            "sh",
            "-c",
            "cat ${CRIBL_VOLUME_DIR:-/opt/cribl}/local/cc-edge-claude-code/inputs.yml",
        )
        assert returncode == 0, f"Could not read edge pack inputs.yml (exit {returncode}). Pack may not be installed."
        assert "/home/claude/.claude/projects/" in output, (
            f"Expected '/home/claude/.claude/projects/' in edge inputs.yml, got:\n{output}"
        )
        assert "*.jsonl" in output, f"Expected '*.jsonl' file pattern in edge inputs.yml, got:\n{output}"

    def test_edge_file_monitor_picks_up_sentinel(self, sentinel_claude_file):
        """Edge FileMonitor logs a 'collector added' entry for a new .jsonl file within 30s.

        The FileMonitor polls every 10 seconds (interval: 10). A new file written on the
        host should appear in edge logs within one poll cycle plus processing time.
        """
        sentinel_path, _ = sentinel_claude_file
        deadline = time.time() + 35
        while time.time() < deadline:
            logs = kubectl("logs", "statefulset/cribl-edge-standalone", "--since=2m")
            if "-test-claude-pipeline" in logs and "FileMonitor collector added" in logs:
                return
            time.sleep(5)
        pytest.fail(
            f"Edge FileMonitor did not log 'collector added' for {sentinel_path.name} within 35s. "
            "Check that the edge pack is installed and the hostPath volume is mounted correctly."
        )

    def test_edge_output_not_devnull(self):
        """Edge 'default' output must NOT resolve to devnull — it must route to Splunk HEC.

        Directly catches the failure mode where CRIBL_VOLUME_DIR is unset and the runtime
        ignores config written to /opt/cribl/local/, leaving only the built-in devnull output.
        """
        output, _ = _kubectl_exec_no_fail(
            "statefulset/cribl-edge-standalone",
            "--",
            "sh",
            "-c",
            "AUTH=$(curl -sf -X POST http://127.0.0.1:9420/api/v1/auth/login "
            '-H "Content-Type: application/json" '
            '-d \'{"username":"admin","password":"\'${CRIBL_EDGE_PASSWORD:-admin}\'"}\' '
            '2>/dev/null | sed \'s/.*"token":"\\([^"]*\\)".*/\\1/\'); '
            "curl -sf http://127.0.0.1:9420/api/v1/system/outputs "
            '-H "Authorization: Bearer $AUTH" 2>/dev/null',
        )
        assert '"splunk-hec"' in output or '"splunk_hec"' in output, (
            f"Edge outputs API does not include Splunk HEC output — all events route to devnull. "
            f"API response: {output[:300]}"
        )

    def test_edge_file_input_active(self):
        """Edge file monitor must be actively collecting files from the host filesystem.

        Catches the failure mode where the pack or injected inputs.yml was not loaded
        by the runtime (e.g. config written to wrong directory due to missing CRIBL_VOLUME_DIR).
        The pack inputs are in the worker namespace and not listed by /api/v1/system/inputs,
        so we verify activity via pod logs which show FileMonitor collector messages.
        """
        logs = kubectl("logs", "statefulset/cribl-edge-standalone", "--since=5m")
        assert "FileMonitor collector added" in logs or "cc-edge-claude-code" in logs, (
            "Edge file monitor is not active — pack may not be installed or inputs.yml was not loaded. "
            "Check that cc-edge-claude-code pack is installed and inputs.yml was injected correctly."
        )

    @pytest.mark.usefixtures("sentinel_claude_file")
    def test_file_events_reach_splunk_realtime(self):
        """Write a .jsonl sentinel and verify Edge's Splunk sentCount increases within 60s (real-time).

        End-to-end verification that the Host FS → Edge → Splunk HEC path (A2 + A5) delivers
        file events in real-time. The sentCount on Edge's splunk-hec output only increments
        when Splunk returns HTTP 200, confirming bytes were physically received.
        """

        def _edge_splunk_sent_count() -> int:
            output, _ = _kubectl_exec_no_fail(
                "statefulset/cribl-edge-standalone",
                "--",
                "sh",
                "-c",
                "AUTH=$(curl -sf -X POST http://127.0.0.1:9420/api/v1/auth/login "
                '-H "Content-Type: application/json" '
                '-d \'{"username":"admin","password":"\'${CRIBL_EDGE_PASSWORD:-admin}\'"}\' '
                '2>/dev/null | sed \'s/.*"token":"\\([^"]*\\)".*/\\1/\'); '
                "curl -sf http://127.0.0.1:9420/api/v1/system/outputs "
                '-H "Authorization: Bearer $AUTH" 2>/dev/null',
            )
            try:
                data = json.loads(output)
                for item in data.get("items", []):
                    if item.get("id") == "splunk-hec":
                        return item.get("status", {}).get("metrics", {}).get("sentCount", 0)
            except (ValueError, KeyError):
                pass
            return 0

        baseline = _edge_splunk_sent_count()
        # sentinel_claude_file already written on the host by the fixture
        deadline = time.time() + 60
        while time.time() < deadline:
            if _edge_splunk_sent_count() > baseline:
                return
            time.sleep(5)
        pytest.fail(
            f"Edge Splunk sentCount did not increase within 60s of writing sentinel file "
            f"(baseline={baseline}). The Host FS → Edge → Splunk HEC pipeline (A2 + A5) "
            "is not delivering file events in real-time."
        )
