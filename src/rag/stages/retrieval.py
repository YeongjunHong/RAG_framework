from pydantic import BaseModel

from src.rag.core.types import RagRequest, RagContext
from src.rag.core.interfaces import RagStage, Tracer
from src.rag.services.registry import RetrieverRegistry


class RetrievalConfig(BaseModel):
    top_k: int = 40
    bm25_weight: float = 0.5
    vector_weight: float = 0.5


class RetrievalStage(RagStage[RetrievalConfig]):
    name = "retrieval"

    def __init__(self, config: RetrievalConfig, registry: RetrieverRegistry, tracer: Tracer):
        super().__init__(config)
        self.registry = registry
        self.tracer = tracer

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        plan = ctx.plan.get("retrieval", {})

        

        provider_name = plan.get("service", "default")
        provider = self.registry.get(provider_name)

        top_k = int(plan.get("top_k", self.config.top_k))
        bm25_w = float(plan.get("bm25_weight", self.config.bm25_weight))
        vec_w = float(plan.get("vector_weight", self.config.vector_weight))        

        queries = ctx.expanded_queries or [request.user_query]

        filters = plan.get("filters", {} ) # 플랜에서 필터 꺼내기 ; 동적 메타데이터 필터링을 위해 Interfaces 파일에 filters 인자 하나 더 추가

        with self.tracer.span("retrieve", top_k=self.config.top_k):
            ctx.retrieved = await provider.forward(
                queries=queries,
                top_k=top_k,
                bm25_weight=bm25_w,
                vector_weight=vec_w,
                filters=filters 
            )
        return ctx
