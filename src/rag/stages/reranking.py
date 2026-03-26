from pydantic import BaseModel

from src.rag.core.types import RagRequest, RagContext
from src.rag.core.interfaces import RagStage, Tracer
from src.rag.services.registry import RerankerRegistry


class RerankingConfig(BaseModel):
    top_k: int = 20


class RerankingStage(RagStage[RerankingConfig]):
    name = "reranking"

    def __init__(self, config: RerankingConfig, registry: RerankerRegistry, tracer: Tracer):
        super().__init__(config)
        self.registry = registry
        self.tracer = tracer

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        plan = ctx.plan.get("retrieval", {})

        provider_name = plan.get("service", "default")
        provider = self.registry.get(provider_name)

        top_k = int(plan.get("top_k", self.config.top_k))
    
        with self.tracer.span("rerank", top_k=self.config.top_k):
            ctx.reranked = await provider.forward(
                query=request.user_query,
                candidates=ctx.retrieved,
                top_k=top_k,
            )
        return ctx
