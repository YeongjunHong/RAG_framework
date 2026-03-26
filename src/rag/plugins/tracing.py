import os
from contextlib import contextmanager

from src.rag.core.interfaces import Tracer


class NoopTracer(Tracer):
    @contextmanager
    def span(self, name: str, **attrs):
        yield


class OTelTracer(Tracer):
    """OpenTelemetry tracer with local-only defaults.

    - Default exporter: console (no network)
    - Optional OTLP exporter: enabled only if TRACE_EXPORTER=otlp and endpoint set
    """

    def __init__(self, service_name: str = "rag-pipeline"):
        self._enabled = os.getenv("TRACE_ENABLED", "1") == "1"
        self._tracer = None
        if not self._enabled:
            return

        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

            exporter = os.getenv("TRACE_EXPORTER", "console").lower()
            resource = Resource.create({"service.name": service_name})
            provider = TracerProvider(resource=resource)

            if exporter == "otlp":
                # Network export is opt-in only.
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

                endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
                if not endpoint:
                    raise RuntimeError("TRACE_EXPORTER=otlp but OTEL_EXPORTER_OTLP_ENDPOINT is not set")
                span_exporter = OTLPSpanExporter(endpoint=endpoint)
            else:
                span_exporter = ConsoleSpanExporter()

            provider.add_span_processor(BatchSpanProcessor(span_exporter))
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(service_name)
        except Exception:
            # If OTel deps missing or misconfigured, fall back to noop.
            self._enabled = False
            self._tracer = None

    @contextmanager
    def span(self, name: str, **attrs):
        if not self._enabled or self._tracer is None:
            yield
            return
        with self._tracer.start_as_current_span(name) as span:
            for k, v in attrs.items():
                try:
                    span.set_attribute(k, v)
                except Exception:
                    pass
            yield


def build_tracer() -> Tracer:
    # Optional LangSmith integration is intentionally excluded by default because it requires outbound comms.
    # If user explicitly enables it, they can add wiring here.
    if os.getenv("TRACE_ENABLED", "1") != "1":
        return NoopTracer()
    return OTelTracer()
