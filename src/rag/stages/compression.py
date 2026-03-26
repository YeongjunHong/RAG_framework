# from pydantic import BaseModel

# from src.rag.core.types import RagRequest, RagContext
# from src.rag.core.interfaces import RagStage


# class CompressionConfig(BaseModel):
#     mode: str = "none"  # placeholder for LLM-based compression
#     max_chars: int = 12000


# class CompressionStage(RagStage[CompressionConfig]):
#     name = "compression"

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         # Framework-free baseline: truncate.
#         txt = ctx.packed_context or ""
#         if len(txt) > self.config.max_chars:
#             ctx.packed_context = txt[: self.config.max_chars]
#         return ctx

from pydantic import BaseModel
from src.rag.core.types import RagRequest, RagContext
from src.rag.core.interfaces import RagStage
from src.common.logger import get_logger

logger = get_logger(__name__)

class CompressionConfig(BaseModel):
    max_chars: int = 12000

class CompressionStage(RagStage[CompressionConfig]):
    name = "compression"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        if not ctx.packed_context:
            return ctx

        blocks = ctx.packed_context.split("||CHUNK_SPLIT||")
        valid_blocks = []
        current_len = 0
        
        # 글자를 무식하게 자르지 않고, 예산 초과 시 청크 단위로 Drop
        for block in blocks:
            block_len = len(block)
            if current_len + block_len > self.config.max_chars:
                logger.warning(f"컨텍스트 한계 도달 ({current_len}/{self.config.max_chars}). 하위 랭크 청크 삭제됨.")
                break
            valid_blocks.append(block)
            current_len += block_len
            
        ctx.packed_context = "||CHUNK_SPLIT||".join(valid_blocks)
        return ctx