from pydantic import BaseModel

from src.rag.core.types import RagRequest, RagContext
from src.rag.core.interfaces import RagStage


class PackingConfig(BaseModel):
    max_chars: int = 12000


class PackingStage(RagStage[PackingConfig]):
    name = "packing"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        # Placeholder: already packed in assembly; enforce bound again.
        txt = ctx.packed_context or ""
        ctx.packed_context = txt[: self.config.max_chars]
        return ctx
