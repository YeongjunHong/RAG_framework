# from pydantic import BaseModel

# from src.rag.core.types import RagContext, RagRequest
# from src.rag.core.interfaces import RagStage


# class AssemblyConfig(BaseModel):
#     include_metadata: bool = False


# class AssemblyStage(RagStage[AssemblyConfig]):
#     name = "assembly"

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         # Grouping / formatting for later compression/packing
#         parts = []
#         for i, sc in enumerate(ctx.filtered):
#             header = f"[{i}] source={sc.chunk.source_id} chunk={sc.chunk.chunk_id} score={sc.score:.4f}"
#             body = sc.chunk.content
#             parts.append(header + "\n" + body)

#         ctx.packed_context = "\n\n".join(parts)
#         return ctx

from pydantic import BaseModel
from src.rag.core.types import RagContext, RagRequest
from src.rag.core.interfaces import RagStage

class AssemblyConfig(BaseModel):
    include_metadata: bool = False

class AssemblyStage(RagStage[AssemblyConfig]):
    name = "assembly"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        blocks = []
        # 필터링을 통과한 데이터(kept=True)만 조립
        for fc in ctx.filtered:
            if fc.kept:
                chunk_id = fc.chunk.chunk_id
                content = fc.chunk.content
                # Prompt Maker가 하던 포맷팅 역할을 Assembly로 이관
                blocks.append(f"문서 식별자: [REF-{chunk_id}]\n내용: {content}")
        
        # 블록 단위 조작을 위해 특수 구분자로 묶어서 Compression으로 전달
        ctx.packed_context = "||CHUNK_SPLIT||".join(blocks)
        return ctx