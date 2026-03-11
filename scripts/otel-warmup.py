"""Send a warmup trace to prime the OTEL collector gRPC connection."""

import os

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

host = os.environ.get("K8S_NODEPORT_HOST", "host.internal")
exporter = OTLPSpanExporter(endpoint=f"{host}:30317", insecure=True)
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
tracer = provider.get_tracer("warmup")
with tracer.start_as_current_span("pipeline-warmup"):
    pass
provider.shutdown()
