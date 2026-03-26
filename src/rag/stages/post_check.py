from pydantic import BaseModel

from src.rag.core.types import RagRequest, RagResponse, RagContext, Citation
from src.rag.core.interfaces import RagStage


class PostCheckConfig(BaseModel):
    enable_guardrails: bool = False
    # Additional local checks can be added here (PII, banned terms, etc.)


class PostCheckStage(RagStage[PostCheckConfig]):
    name = "post_check"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        # Placeholder: attach simple diagnostics; real guardrails integration is in adapters/guard/
        ctx.postcheck["guardrails_applied"] = self.config.enable_guardrails
        return ctx


def to_response(request: RagRequest, ctx: RagContext) -> RagResponse:
    # Minimal citation: include top filtered chunks ids
    citations = []
    for sc in (ctx.filtered[:5] if ctx.filtered else []):
        citations.append(Citation(source_id=sc.chunk.source_id, chunk_id=sc.chunk.chunk_id))

    answer = ctx.raw_generation or ""
    return RagResponse(trace_id=request.trace_id, answer=answer, citations=citations, diagnostics={"plan_id": ctx.plan_id, "timings_ms": ctx.timings_ms})
