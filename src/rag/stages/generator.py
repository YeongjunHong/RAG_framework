from pydantic import BaseModel

from src.rag.core.types import RagContext, RagRequest
from src.rag.core.interfaces import RagStage, RagGenerator, Tracer
from src.common.logger import get_logger

logger = get_logger(__name__)

class GeneratorConfig(BaseModel):
    model: str | None = None

class GeneratorStage(RagStage[GeneratorConfig]):
    name = "generator_llm"

    def __init__(self, config: GeneratorConfig, llm: RagGenerator, tracer: Tracer):
        super().__init__(config)
        self.llm = llm
        self.tracer = tracer

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        target_model = self.config.model or "default"
        logger.info(f"[{self.name}] 실행 시작 (모델: {target_model})")
        
        with self.tracer.span("generate", model=target_model):
            # -------------------------------------------------------------
            # [핵심] Early Exit (조기 종료 패턴) - 환각 원천 차단 및 비용 절감
            # -------------------------------------------------------------
            if getattr(ctx, "intent", "") != "chitchat" and not getattr(ctx, "packed_context", "").strip():
                logger.warning(f"[{self.name}] 컨텍스트가 비어있어 LLM 호출을 생략하고 Fallback 메시지를 반환합니다.")
                ctx.raw_generation = "제공된 문서에서 관련 정보를 찾을 수 없습니다."
                
                # 스트리밍 클라이언트가 무한 대기하지 않도록 즉시 메시지와 종료 시그널(None) 전송
                if getattr(ctx, 'stream_queue', None):
                    await ctx.stream_queue.put(ctx.raw_generation)
                    await ctx.stream_queue.put(None)
                
                return ctx

            # -------------------------------------------------------------
            # 정상 LLM 호출 로직
            # -------------------------------------------------------------
            logger.info(f"[{self.name}] LLM 생성 시작 (스트리밍: {getattr(ctx, 'is_streaming', False)})")
            
            # 큐를 LLM으로 전달하여 스트리밍 파이프 연결
            # forward()가 await되는 동안 백그라운드에서 ctx.stream_queue로 토큰이 푸시됨
            # Consumer(API 라우터 또는 RabbitMQ 워커)는 이 시점에 큐에서 토큰을 빼가야 함
            ctx.raw_generation = await self.llm.forward(
                prompt=ctx.prompt, 
                model=self.config.model,
                stream_queue=getattr(ctx, 'stream_queue', None)
            )
            
        logger.info(f"[{self.name}] 실행 완료")
        return ctx