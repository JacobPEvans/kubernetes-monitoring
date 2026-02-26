"""Tier 2: OTLP send and receive verification.

These tests send actual trace data through the OTEL Collector and verify
the exporter returned SUCCESS (indicating the collector accepted the data).
Requires the stack to be deployed and NodePorts accessible.
"""

import uuid

import pytest
from conftest import OTEL_GRPC_ENDPOINT, OTEL_HTTP_ENDPOINT
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GrpcExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HttpExporter,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExportResult


def _create_test_span() -> object:
    """Create a finished test span for export verification."""
    provider = TracerProvider()
    tracer = provider.get_tracer("otel-pipeline-test")
    with tracer.start_as_current_span("test-span") as span:
        span.set_attribute("test.id", str(uuid.uuid4()))
        span.set_attribute("test.source", "pytest-pipeline-test")
    provider.shutdown()
    return span


@pytest.mark.usefixtures("cluster_ready")
class TestOtlpGrpcIngestion:
    def test_send_trace_grpc(self):
        """Send a trace via gRPC NodePort and verify the collector accepted it."""
        span = _create_test_span()
        # insecure=True: TLS not needed for local OrbStack NodePort testing
        exporter = GrpcExporter(endpoint=OTEL_GRPC_ENDPOINT, insecure=True)
        result = exporter.export([span])
        exporter.shutdown()
        assert result == SpanExportResult.SUCCESS, f"OTLP gRPC export to {OTEL_GRPC_ENDPOINT} failed: {result}"


@pytest.mark.usefixtures("cluster_ready")
class TestOtlpHttpIngestion:
    def test_send_trace_http(self):
        """Send a trace via HTTP NodePort and verify the collector accepted it."""
        span = _create_test_span()
        exporter = HttpExporter(endpoint=f"{OTEL_HTTP_ENDPOINT}/v1/traces")
        result = exporter.export([span])
        exporter.shutdown()
        assert result == SpanExportResult.SUCCESS, f"OTLP HTTP export to {OTEL_HTTP_ENDPOINT} failed: {result}"
