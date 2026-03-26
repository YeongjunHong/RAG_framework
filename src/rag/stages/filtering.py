from typing import Dict, List
from pydantic import BaseModel

from src.rag.core.types import RagRequest, RagContext, ScoredChunk
from src.rag.core.interfaces import RagStage


class FilteringConfig(BaseModel):
    min_score: float = 0.0
    max_per_source: int = 5


class FilteringStage(RagStage[FilteringConfig]):
    name = "filtering"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        items = ctx.reranked or ctx.retrieved
        out: List[ScoredChunk] = []
        per_source: Dict[str, int] = {}

        for sc in items:
            if sc.score < self.config.min_score:
                continue
            sid = sc.chunk.source_id
            per_source[sid] = per_source.get(sid, 0) + 1
            if per_source[sid] > self.config.max_per_source:
                continue
            out.append(sc)

        ctx.filtered = out
        return ctx
