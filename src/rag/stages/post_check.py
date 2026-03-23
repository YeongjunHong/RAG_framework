import re
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
    answer = ctx.raw_generation or ""
    
    # 1. 정규식(Regex)을 사용하여 LLM 답변에서 [REF-숫자] 패턴의 숫자만 모두 추출
    # 예: "어쩌구 저쩌구 [REF-94110]" -> 94110 추출
    extracted_ids = re.findall(r'\[REF-(\d+)\]', answer)
    used_chunk_ids = list(set(int(id_str) for id_str in extracted_ids))
    
    # 2. LLM이 실제로 참조했다고 밝힌 ID만 찾아내서 Citations 배열 조립
    citations = []
    # PromptMaker에서 ctx.reranked를 컨텍스트로 주었으므로 여기서도 동일하게 대조.
    for doc in ctx.reranked:
        if doc.chunk.chunk_id in used_chunk_ids:
            citations.append(
                Citation(
                    source_id=doc.chunk.source_id, 
                    chunk_id=doc.chunk.chunk_id
                )
            )

    return RagResponse(
        trace_id=request.trace_id, 
        answer=answer, 
        citations=citations, 
        diagnostics={"plan_id": ctx.plan_id, "timings_ms": ctx.timings_ms}
    )