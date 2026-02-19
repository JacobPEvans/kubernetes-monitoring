"""Shared test fixtures and utilities for OTEL pipeline tests."""
import json
import os
import subprocess
from typing import Any
import pytest

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
