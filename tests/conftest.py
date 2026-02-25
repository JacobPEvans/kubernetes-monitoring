"""Shared test fixtures and utilities for OTEL pipeline tests."""
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
STATEFULSETS = [
    "otel-collector",
    "cribl-edge-managed",
    "cribl-edge-standalone",
    "cribl-stream-standalone",
]


def kubectl(*args: str) -> str:
    """Run kubectl with orbstack context and monitoring namespace."""
    cmd = ["kubectl", "--context", CONTEXT, "-n", NAMESPACE, *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            f"kubectl {' '.join(args)} failed:\nstderr: {result.stderr}\nstdout: {result.stdout}"
        )
    return result.stdout.strip()


def kubectl_json(*args: str) -> Any:
    """Run kubectl and parse JSON output."""
    output = kubectl(*args, "-o", "json")
    return json.loads(output)


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
        ["kubectl", "--context", CONTEXT, "-n", NAMESPACE,
         "port-forward", f"statefulset/{statefulset}", f"{local_port}:{container_port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        start_time = time.time()
        last_error = None
        while time.time() - start_time < timeout_seconds:
            if proc.poll() is not None:
                pytest.fail(
                    f"kubectl port-forward process exited before request for {statefulset}; "
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
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("OrbStack cluster not reachable")
