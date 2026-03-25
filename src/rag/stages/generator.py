# from pydantic import BaseModel

# from src.rag.core.types import RagContext, RagRequest
# from src.rag.core.interfaces import RagStage, RagGenerator, Tracer


# class GeneratorConfig(BaseModel):
#     model: str | None = None


# class GeneratorStage(RagStage[GeneratorConfig]):
#     name = "generator_llm"

#     def __init__(self, config: GeneratorConfig, llm: RagGenerator, tracer: Tracer):
#         super().__init__(config)
#         self.llm = llm
#         self.tracer = tracer

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         with self.tracer.span("generate", model=self.config.model or "default"):
#             # 큐를 LLM으로 전달하여 스트리밍 파이프 연결
#             ctx.raw_generation = await self.llm.forward(
#                 prompt=ctx.prompt, 
#                 model=self.config.model,
#                 stream_queue=ctx.stream_queue
#                 )
#         return ctx


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