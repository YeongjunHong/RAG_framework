import os
from contextlib import contextmanager

from src.rag.core.interfaces import Tracer
from src.common.logger import get_logger

logger = get_logger(__name__)

class NoopTracer(Tracer):
    @contextmanager
    def span(self, name: str, **attrs):
        yield


class OTelTracer(Tracer):
    """OpenTelemetry tracer with local-only defaults."""
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
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
                if not endpoint:
                    raise RuntimeError("TRACE_EXPORTER=otlp but OTEL_EXPORTER_OTLP_ENDPOINT is not set")
                span_exporter = OTLPSpanExporter(endpoint=endpoint)
            else:
                trace_file = open("demo_traces.jsonl", "a", encoding="utf-8")
                span_exporter = ConsoleSpanExporter(out=trace_file)

            provider.add_span_processor(BatchSpanProcessor(span_exporter))
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(service_name)
        except Exception:
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
    if os.getenv("TRACE_ENABLED", "1") != "1":
        return NoopTracer()
    
    exporter = os.getenv("TRACE_EXPORTER", "langfuse").lower()
    
    if exporter == "langfuse":
        # [핵심] 최신 Langfuse(v4+)는 LangGraph의 CallbackHandler를 통해
        # 그래프 전체의 노드 흐름과 내부 LLM 호출을 자동으로 캡쳐
        # 따라서 수동 span 생성을 담당하던 기존 Tracer 로직은 충돌을 막기 위해 Noop으로 우회
        logger.debug("[Tracing] Langfuse 모드: 수동 트레이서를 비활성화하고 LangGraph 네이티브 콜백에 위임합니다.")
        return NoopTracer()
        
    return OTelTracer()