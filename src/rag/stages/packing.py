# from pydantic import BaseModel

# from src.rag.core.types import RagRequest, RagContext
# from src.rag.core.interfaces import RagStage


# class PackingConfig(BaseModel):
#     max_chars: int = 12000


# class PackingStage(RagStage[PackingConfig]):
#     name = "packing"

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         # Placeholder: already packed in assembly; enforce bound again.
#         txt = ctx.packed_context or ""
#         ctx.packed_context = txt[: self.config.max_chars]
#         return ctx

from pydantic import BaseModel
from src.rag.core.types import RagRequest, RagContext
from src.rag.core.interfaces import RagStage

class PackingConfig(BaseModel):
    pass

class PackingStage(RagStage[PackingConfig]):
    name = "packing"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        if not ctx.packed_context:
            ctx.packed_context = "제공된 문서 내용이 없습니다."
            return ctx
            
        blocks = ctx.packed_context.split("||CHUNK_SPLIT||")
        # 최종적으로 LLM에 주입될 수 있도록 깔끔한 개행문자로 병합
        ctx.packed_context = "\n\n".join(blocks)
        return ctx