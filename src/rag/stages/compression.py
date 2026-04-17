import tiktoken
import re
from pydantic import BaseModel
from typing import List, Optional

from src.rag.core.types import RagRequest, RagContext, EvidenceGroup, SourceChunk
from src.rag.core.interfaces import RagStage
from src.common.logger import get_logger
from src.rag.services.registry import TextCompressorRegistry

logger = get_logger(__name__)

class CompressionConfig(BaseModel):
    max_tokens: int = 3000
    tokenizer_model: str = "gpt-4o-mini" 
    use_semantic_compression: bool = True

class CompressionStage(RagStage[CompressionConfig]):
    name = "compression"

    def __init__(self, config: CompressionConfig, registry: TextCompressorRegistry):
        super().__init__(config)
        self.registry = registry
        try:
            self.encoder = tiktoken.encoding_for_model(self.config.tokenizer_model)
        except KeyError:
            logger.warning("지원하지 않는 토크나이저 모델. 기본값(cl100k_base)으로 폴백합니다.")
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        return len(self.encoder.encode(text))

    def _clean_compressed_text(self, text: str) -> str:
        """SLM이 생성한 불필요한 대화형 접두사 및 노이즈 제거"""
        # [압축된 텍스트], Here is the compressed text:, instruction: ... output: 등의 패턴 제거
        cleaned = re.sub(r"(?i)^(Here is the compressed text:\s*|\[압축된 텍스트\]\s*|instruction:.*?output:\s*)", "", text, flags=re.DOTALL)
        return cleaned.strip()

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        groups = getattr(ctx, "evidence_groups", [])
        
        if not groups:
            logger.info(f"[{self.name}] 압축할 데이터가 없습니다.")
            return ctx

        # STEP 1: Semantic Compression
        if self.config.use_semantic_compression:
            try:
                compressor = self.registry.get("slm_compressor")
                all_chunks = [chunk for group in groups for chunk in group.chunks]
                texts_to_compress = [chunk.content for chunk in all_chunks]
                
                if texts_to_compress:
                    logger.info(f"[{self.name}] {len(texts_to_compress)}개의 청크에 대해 압축을 시작합니다.")
                    compressed_texts = await compressor.forward(texts_to_compress)
                    
                    for chunk, comp_text in zip(all_chunks, compressed_texts):
                        # [핵심] 압축 텍스트 정제 적용
                        clean_text = self._clean_compressed_text(comp_text)
                        chunk.content = clean_text
                        
            except Exception as e:
                logger.error(f"[{self.name}] 의미 기반 압축 중 에러 발생: {e}")

        # STEP 2: Budget-aware Truncation
        compressed_groups = []
        current_total_tokens = 0

        for group in groups:
            kept_chunks = []
            for chunk in group.chunks:
                chunk_text = f"{group.title}\n{chunk.content}" 
                chunk_tokens = self._count_tokens(chunk_text)

                if current_total_tokens + chunk_tokens <= self.config.max_tokens:
                    kept_chunks.append(chunk)
                    current_total_tokens += chunk_tokens
                else:
                    logger.info(f"[{self.name}] 토큰 한도 초과. 청크 드랍 시작.")
                    break 

            if kept_chunks:
                compressed_groups.append(EvidenceGroup(
                    group_id=group.group_id,
                    title=group.title,
                    chunks=kept_chunks
                ))

            if current_total_tokens >= self.config.max_tokens:
                break

        ctx.evidence_groups = compressed_groups
        return ctx