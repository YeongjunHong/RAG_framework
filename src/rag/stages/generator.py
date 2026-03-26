from pydantic import BaseModel

from src.rag.core.types import RagContext, RagRequest
from src.rag.core.interfaces import RagStage, RagGenerator, Tracer


class GeneratorConfig(BaseModel):
    model: str | None = None


class GeneratorStage(RagStage[GeneratorConfig]):
    name = "generator_llm"

    def __init__(self, config: GeneratorConfig, llm: RagGenerator, tracer: Tracer):
        super().__init__(config)
        self.llm = llm
        self.tracer = tracer

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        with self.tracer.span("generate", model=self.config.model or "default"):
            # 큐를 LLM으로 전달하여 스트리밍 파이프 연결
            ctx.raw_generation = await self.llm.forward(
                prompt=ctx.prompt, 
                model=self.config.model,
                stream_queue=ctx.stream_queue
                )
        return ctx

