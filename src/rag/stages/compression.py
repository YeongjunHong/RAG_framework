from pydantic import BaseModel

from src.rag.core.types import RagRequest, RagContext
from src.rag.core.interfaces import RagStage


class CompressionConfig(BaseModel):
    mode: str = "none"  # placeholder for LLM-based compression
    max_chars: int = 12000


class CompressionStage(RagStage[CompressionConfig]):
    name = "compression"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        # Framework-free baseline: truncate.
        txt = ctx.packed_context or ""
        if len(txt) > self.config.max_chars:
            ctx.packed_context = txt[: self.config.max_chars]
        return ctx
