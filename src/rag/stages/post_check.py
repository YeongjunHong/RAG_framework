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
        if getattr(ctx, "intent", "") == "chitchat":
            logger.info(f"[{self.name}] Chitchat 인텐트이므로 검증을 스킵합니다.")
            ctx.postcheck = {"is_valid": True, "reason": "Chitchat bypass"}
            return ctx
        
        with self.tracer.span("post_check", provider=self.config.provider):
            validation_result = await self.guardrails_plugin.forward(
                context=ctx.packed_context,
                generation=ctx.raw_generation
            )
            
            ctx.postcheck = validation_result

            if ctx.is_streaming:
                if not validation_result.get("is_valid"):
                    logger.warning(f"[PostCheck] 환각 감지됨 (Streaming Mode). 사유: {validation_result.get('reason')}")
                return ctx
            else:
                if not validation_result.get("is_valid"):
                    logger.error(f"[PostCheck] 검증 실패. 사유: {validation_result.get('reason')}")
                    
                    if validation_result.get("error_type") == "format_error":
                        ctx.errors.append({"type": "format_error", "reason": validation_result.get('reason')})
                    else:
                        # [핵심] 원본 텍스트를 파괴하지 않고, 후처리를 통해 경고 문구만 삽입
                        original_answer = ctx.raw_generation or ""
                        warning_msg = "\n\n[ 시스템 알림: 위 답변은 검증 과정에서 제공된 문서와 일부 불일치하는 내용이 감지되었습니다.]"
                        ctx.raw_generation = original_answer + warning_msg
                        
                return ctx
            
def to_response(state: dict) -> dict:
    request: RagRequest = state["request"]
    ctx: RagContext = state["ctx"]
    
    response = RagResponse(
        trace_id=request.trace_id,
        answer=ctx.raw_generation or "안전한 기본 응답: 답변을 생성하지 못했습니다.",
        citations=[], 
        diagnostics={
            "intent": getattr(ctx, "intent", "unknown"),
            "is_streaming": getattr(ctx, "is_streaming", True),
            "strict_validation": getattr(ctx, "strict_validation", False),
            "postcheck_result": ctx.postcheck,
            "errors": ctx.errors,
            "timings_ms": getattr(ctx, "timings_ms", {})
        }
    )
    return {"response": response}