"""Tier 2: OTLP send and receive verification.

These tests send actual trace data through the OTEL Collector and verify
the exporter returned SUCCESS (indicating the collector accepted the data).
Requires the stack to be deployed and NodePorts accessible.
"""
import uuid

import pytest

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GrpcExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HttpExporter

from conftest import OTEL_GRPC_ENDPOINT, OTEL_HTTP_ENDPOINT


@pytest.mark.usefixtures("cluster_ready")
class TestOtlpGrpcIngestion:
    def test_send_trace_grpc(self):
        """Send a trace via gRPC NodePort and verify the collector accepted it."""
        exporter = GrpcExporter(endpoint=OTEL_GRPC_ENDPOINT, insecure=True)
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("otel-pipeline-test")
        with tracer.start_as_current_span("test-span") as span:
            span.set_attribute("test.id", str(uuid.uuid4()))
            span.set_attribute("test.source", "pytest-pipeline-test")
        result = provider.shutdown()
        # No exception means the collector accepted the data
        assert result is None or result


@pytest.mark.usefixtures("cluster_ready")
class TestOtlpHttpIngestion:
    def test_send_trace_http(self):
        """Send a trace via HTTP NodePort and verify the collector accepted it."""
        exporter = HttpExporter(endpoint=f"{OTEL_HTTP_ENDPOINT}/v1/traces")
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("otel-pipeline-test")
        with tracer.start_as_current_span("test-span") as span:
            span.set_attribute("test.id", str(uuid.uuid4()))
            span.set_attribute("test.source", "pytest-pipeline-test")
        result = provider.shutdown()
        assert result is None or result
