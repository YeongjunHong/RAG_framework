# import re
# from pydantic import BaseModel

# from src.rag.core.types import RagRequest, RagResponse, RagContext, Citation
# from src.rag.core.interfaces import RagStage


# class PostCheckConfig(BaseModel):
#     enable_guardrails: bool = False
#     # Additional local checks can be added here (PII, banned terms, etc.)


# class PostCheckStage(RagStage[PostCheckConfig]):
#     name = "post_check"

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         # Placeholder: attach simple diagnostics; real guardrails integration is in adapters/guard/
#         ctx.postcheck["guardrails_applied"] = self.config.enable_guardrails
#         return ctx


# def to_response(request: RagRequest, ctx: RagContext) -> RagResponse:
#     answer = ctx.raw_generation or ""
    
#     # 1. 정규식(Regex)을 사용하여 LLM 답변에서 [REF-숫자] 패턴의 숫자만 모두 추출
#     # 예: "어쩌구 저쩌구 [REF-94110]" -> 94110 추출
#     extracted_ids = re.findall(r'\[REF-(\d+)\]', answer)
#     used_chunk_ids = list(set(int(id_str) for id_str in extracted_ids))
    
#     # 2. LLM이 실제로 참조했다고 밝힌 ID만 찾아내서 Citations 배열 조립
#     citations = []
#     # PromptMaker에서 ctx.reranked를 컨텍스트로 주었으므로 여기서도 동일하게 대조.
#     for doc in ctx.reranked:
#         if doc.chunk.chunk_id in used_chunk_ids:
#             citations.append(
#                 Citation(
#                     source_id=doc.chunk.source_id, 
#                     chunk_id=doc.chunk.chunk_id
#                 )
#             )

#     return RagResponse(
#         trace_id=request.trace_id, 
#         answer=answer, 
#         citations=citations, 
#         diagnostics={"plan_id": ctx.plan_id, "timings_ms": ctx.timings_ms}
#     )


# src/rag/stages/post_check.py

from pydantic import BaseModel
from src.rag.core.types import RagRequest, RagContext, RagResponse
from src.rag.core.interfaces import RagStage, Tracer
from src.common.logger import get_logger

logger = get_logger(__name__)

class PostCheckConfig(BaseModel):
    provider: str = "default"

class PostCheckStage(RagStage[PostCheckConfig]):
    name = "post_check"

    def __init__(self, config: PostCheckConfig, guardrails_plugin, tracer: Tracer):
        super().__init__(config)
        self.guardrails_plugin = guardrails_plugin
        self.tracer = tracer

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        # [추가된 방어 로직]
        if getattr(ctx, "intent", "") == "chitchat":
            logger.info(f"[{self.name}] Chitchat 인텐트이므로 Guardrails 검증을 스킵합니다.")
            ctx.postcheck = {"is_valid": True, "reason": "Chitchat bypass"}
            return ctx
        
        with self.tracer.span("post_check", provider=self.config.provider):
            
            # 검증 실행 (공통)
            validation_result = await self.guardrails_plugin.forward(
                context=ctx.packed_context,
                generation=ctx.raw_generation
            )
            
            ctx.postcheck = validation_result

            # A 모드: 챗봇 (스트리밍 ON)
            if ctx.is_streaming:
                if not validation_result.get("is_valid"):
                    # 이미 클라이언트에게 텍스트가 흘러갔으므로 에러 로깅만 수행 (Observability)
                    logger.warning(f"[PostCheck] 환각 감지됨 (Streaming Mode). 피드백 DB에 기록합니다. 사유: {validation_result.get('reason')}")
                return ctx

            # B 모드: 교육 콘텐츠 제작 (스트리밍 OFF / 강력한 방어)
            else:
                if not validation_result.get("is_valid"):
                    logger.error(f"[PostCheck] 검증 실패 (Strict Mode). 사유: {validation_result.get('reason')}")
                    
                    # 에러 유형이 Format 에러라면 Retry를 위한 플래그를 세팅할 수 있음
                    if validation_result.get("error_type") == "format_error":
                        ctx.errors.append({"type": "format_error", "reason": validation_result.get('reason')})
                        # LangGraph의 conditional edge에서 이 값을 보고 Generator로 루프백 시킴
                        
                    # 에러 유형이 환각(Hallucination)이라면 즉시 안전한 Fallback 메시지로 덮어씌움 (Fail-fast)
                    else:
                        ctx.raw_generation = "제공된 문서에서 정확하고 신뢰할 수 있는 정보를 찾을 수 없어 답변 생성을 중단했습니다."
                        
                return ctx
            
def to_response(state: dict) -> dict:
    """
    LangGraph 파이프라인의 최종 상태를 클라이언트 반환용 RagResponse 객체로 패키징
    """
    request: RagRequest = state["request"]
    ctx: RagContext = state["ctx"]
    
    # Context에 쌓인 데이터를 기반으로 최종 응답 조립
    response = RagResponse(
        trace_id=request.trace_id,
        answer=ctx.raw_generation or "안전한 기본 응답: 답변을 생성하지 못했습니다.",
        citations=[], # 추후 Citation 기능 고도화 시 ctx.evidence_groups 등에서 매핑
        diagnostics={
            "intent": getattr(ctx, "intent", "unknown"),
            "is_streaming": getattr(ctx, "is_streaming", True),
            "strict_validation": getattr(ctx, "strict_validation", False),
            "postcheck_result": ctx.postcheck,
            "errors": ctx.errors,
            "timings_ms": ctx.timings_ms
        }
    )
    
    # LangGraph State 업데이트
    return {"response": response}