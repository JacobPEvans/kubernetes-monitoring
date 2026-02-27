"""Shared test fixtures and utilities for OTEL pipeline tests."""

import base64
import json
import os
import subprocess
import time
from typing import Any

import pytest
import requests

CONTEXT = os.environ.get("KUBE_CONTEXT", "orbstack")
NAMESPACE = os.environ.get("KUBE_NAMESPACE", "monitoring")
OTEL_GRPC_ENDPOINT = "localhost:30317"
OTEL_HTTP_ENDPOINT = "http://localhost:30318"

# Local port-forward ports — each test uses a unique port to avoid collisions.
PF_OTEL_HEALTH = 13133
PF_STREAM_HEALTH = 19420
PF_EDGE_HEALTH = 19421
PF_STREAM_INPUTS_A4 = 19422
PF_STREAM_INPUTS_A5 = 19423
PF_STREAM_OUTPUTS = 19424

# MCP server NodePort — accessed directly from macOS (not via port-forward).
MCP_NODEPORT_URL = "http://localhost:30030/mcp"

STATEFULSETS = [
    "otel-collector",
    "cribl-edge-managed",
    "cribl-edge-standalone",
    "cribl-stream-standalone",
    "cribl-mcp-server",
]


def kubectl(*args: str) -> str:
    """Run kubectl with orbstack context and monitoring namespace."""
    cmd = ["kubectl", "--context", CONTEXT, "-n", NAMESPACE, *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"kubectl {' '.join(args)} failed:\nstderr: {result.stderr}\nstdout: {result.stdout}")
    return result.stdout.strip()


def kubectl_json(*args: str) -> Any:
    """Run kubectl and parse JSON output."""
    output = kubectl(*args, "-o", "json")
    return json.loads(output)


def kubectl_secret(name: str, key: str) -> str:
    """Read a k8s secret value (base64 decoded)."""
    data = kubectl_json("get", "secret", name)
    encoded = data.get("data", {}).get(key)
    if not encoded:
        raise RuntimeError(f"Secret {name}[{key}] not found or empty")
    return base64.b64decode(encoded).decode()


def kubectl_secret_values(name: str, keys: list[str]) -> dict[str, str]:
    """Read multiple k8s secret values in a single kubectl call (base64 decoded)."""
    data = kubectl_json("get", "secret", name)
    secret_data = data.get("data", {})
    result = {}
    for key in keys:
        encoded = secret_data.get(key)
        if not encoded:
            raise RuntimeError(f"Secret {name}[{key}] not found or empty")
        result[key] = base64.b64decode(encoded).decode()
    return result


def port_forward_get(
    statefulset: str,
    container_port: int,
    local_port: int,
    path: str = "/",
    timeout_seconds: int = 15,
) -> requests.Response:
    """Port-forward to a StatefulSet and perform a GET request.

    Avoids kubectl exec into distroless or restricted containers by using
    a local port-forward and requests from the test host instead.
    """
    proc = subprocess.Popen(
        [
            "kubectl",
            "--context",
            CONTEXT,
            "-n",
            NAMESPACE,
            "port-forward",
            f"statefulset/{statefulset}",
            f"{local_port}:{container_port}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        start_time = time.time()
        last_error = None
        while time.time() - start_time < timeout_seconds:
            if proc.poll() is not None:
                pytest.fail(
                    f"kubectl port-forward process exited before request for {statefulset}; port may already be in use."
                )
            try:
                resp = requests.get(f"http://localhost:{local_port}{path}", timeout=2)
                return resp
            except requests.exceptions.ConnectionError as exc:
                last_error = exc
                time.sleep(0.5)
        pytest.fail(
            f"Timed out after {timeout_seconds}s waiting for {statefulset} "
            f"via port-forward on :{local_port}: {last_error}"
        )
    finally:
        proc.terminate()
        proc.wait()


@pytest.fixture(scope="session")
def cluster_ready():
    """Skip all tests if the cluster is unreachable."""
    try:
        subprocess.run(
            ["kubectl", "--context", CONTEXT, "cluster-info"],
            capture_output=True,
            timeout=10,
            check=True,
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        pytest.skip("OrbStack cluster not reachable")
