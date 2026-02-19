"""Tier 3: Collector-to-Cribl Edge forwarding verification.

These tests verify that after sending data, the OTEL Collector does not
log export errors when forwarding to Cribl Edge managed.
"""
import time
import uuid

import pytest

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from conftest import OTEL_GRPC_ENDPOINT, kubectl


def _send_trace(test_id: str) -> None:
    exporter = OTLPSpanExporter(endpoint=OTEL_GRPC_ENDPOINT, insecure=True)
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("otel-forwarding-test")
    with tracer.start_as_current_span("forward-test-span") as span:
        span.set_attribute("test.id", test_id)
    provider.shutdown()


@pytest.mark.usefixtures("cluster_ready")
class TestCollectorToEdgeForwarding:
    def test_no_export_errors_after_send(self):
        """After sending data, collector logs should not contain export errors."""
        test_id = str(uuid.uuid4())
        _send_trace(test_id)
        time.sleep(5)  # Allow time for forwarding attempt
        logs = kubectl("logs", "statefulset/otel-collector", "--tail=100")
        error_indicators = ["Exporting failed", "export error", "connection refused"]
        for indicator in error_indicators:
            assert indicator not in logs, (
                f"Export error found in collector logs after send: '{indicator}'"
            )

    @pytest.mark.xfail(reason="Cribl Edge OTLP source may not be configured in cloud")
    def test_cribl_edge_health_after_send(self):
        """Cribl Edge should be healthy after receiving forwarded data."""
        test_id = str(uuid.uuid4())
        _send_trace(test_id)
        time.sleep(3)
        output = kubectl(
            "exec", "statefulset/cribl-edge-managed", "--",
            "curl", "-sf", "http://localhost:9420/api/v1/health"
        )
        assert output
