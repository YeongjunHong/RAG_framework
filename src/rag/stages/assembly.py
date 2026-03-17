from pydantic import BaseModel

from src.rag.core.types import RagContext, RagRequest
from src.rag.core.interfaces import RagStage


class AssemblyConfig(BaseModel):
    include_metadata: bool = False


class AssemblyStage(RagStage[AssemblyConfig]):
    name = "assembly"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        # Grouping / formatting for later compression/packing
        parts = []
        for i, sc in enumerate(ctx.filtered):
            header = f"[{i}] source={sc.chunk.source_id} chunk={sc.chunk.chunk_id} score={sc.score:.4f}"
            body = sc.chunk.content
            parts.append(header + "\n" + body)

        ctx.packed_context = "\n\n".join(parts)
        return ctx
