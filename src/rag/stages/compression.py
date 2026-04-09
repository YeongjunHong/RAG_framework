# # from pydantic import BaseModel

# # from src.rag.core.types import RagRequest, RagContext
# # from src.rag.core.interfaces import RagStage


# # class CompressionConfig(BaseModel):
# #     mode: str = "none"  # placeholder for LLM-based compression
# #     max_chars: int = 12000


# # class CompressionStage(RagStage[CompressionConfig]):
# #     name = "compression"

# #     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
# #         # Framework-free baseline: truncate.
# #         txt = ctx.packed_context or ""
# #         if len(txt) > self.config.max_chars:
# #             ctx.packed_context = txt[: self.config.max_chars]
# #         return ctx

# from pydantic import BaseModel
# from src.rag.core.types import RagRequest, RagContext
# from src.rag.core.interfaces import RagStage
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class CompressionConfig(BaseModel):
#     max_chars: int = 12000

# class CompressionStage(RagStage[CompressionConfig]):
#     name = "compression"

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         if not ctx.packed_context:
#             return ctx

#         blocks = ctx.packed_context.split("||CHUNK_SPLIT||")
#         valid_blocks = []
#         current_len = 0
        
#         # 글자를 무식하게 자르지 않고, 예산 초과 시 청크 단위로 Drop
#         for block in blocks:
#             block_len = len(block)
#             if current_len + block_len > self.config.max_chars:
#                 logger.warning(f"컨텍스트 한계 도달 ({current_len}/{self.config.max_chars}). 하위 랭크 청크 삭제됨.")
#                 break
#             valid_blocks.append(block)
#             current_len += block_len
            
#         ctx.packed_context = "||CHUNK_SPLIT||".join(valid_blocks)
#         return ctx

# import tiktoken
# from pydantic import BaseModel
# from typing import List

# from src.rag.core.types import RagRequest, RagContext, EvidenceGroup, SourceChunk
# from src.rag.core.interfaces import RagStage
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class CompressionConfig(BaseModel):
#     #  최대 허용 토큰 수
#     max_tokens: int = 3000
#     # 토큰 계산에 사용할 인코더 (OpenRouter/Gemini를 쓴다면 o200k_base나 cl100k_base 등 호환되는 것 사용)
#     tokenizer_model: str = "gpt-4o-mini" 

# class CompressionStage(RagStage[CompressionConfig]):
#     name = "compression"

#     def __init__(self, config: CompressionConfig):
#         super().__init__(config)
#         # tiktoken 인코더 초기화 (I/O 블로킹 방지를 위해 초기화 시 1회만 로드)
#         try:
#             self.encoder = tiktoken.encoding_for_model(self.config.tokenizer_model)
#         except KeyError:
#             logger.warning(f"지원하지 않는 토크나이저 모델. 기본값(cl100k_base)으로 폴백합니다.")
#             self.encoder = tiktoken.get_encoding("cl100k_base")

#     def _count_tokens(self, text: str) -> int:
#         """텍스트의 정확한 토큰 수를 계산"""
#         return len(self.encoder.encode(text))

#     def _compress_groups(self, groups: List[EvidenceGroup], max_tokens: int) -> List[EvidenceGroup]:
#         """
#         토큰 예산(max_tokens)을 초과하지 않도록 청크를 잘라냄.
#         이 예시에서는 단순화를 위해 뒤에서부터 잘라내는(Truncate) 방식을 사용하지만,
#         실무에서는 청크의 원본 검색 Score를 보존하여 Score가 낮은 것부터 Drop하는 Greedy 알고리즘이 더 효과적임.
#         """
#         compressed_groups = []
#         current_total_tokens = 0

#         for group in groups:
#             kept_chunks = []
#             for chunk in group.chunks:
#                 # 메타데이터나 구조화를 위해 추가될 오버헤드를 고려하여 여유 있게 계산
#                 chunk_text = f"{group.title}\n{chunk.content}" 
#                 chunk_tokens = self._count_tokens(chunk_text)

#                 if current_total_tokens + chunk_tokens <= max_tokens:
#                     kept_chunks.append(chunk)
#                     current_total_tokens += chunk_tokens
#                 else:
#                     logger.info(f"[{self.name}] 토큰 한도 초과. 청크 ID {chunk.chunk_id} (출처: {group.title}) 부터 드랍합니다.")
#                     # 예산이 초과되면 해당 그룹의 남은 청크는 모두 무시하고 다음 그룹/종료 처리
#                     break 

#             if kept_chunks:
#                 # 살아남은 청크들로만 새로운 EvidenceGroup 객체 생성
#                 compressed_groups.append(EvidenceGroup(
#                     group_id=group.group_id,
#                     title=group.title,
#                     chunks=kept_chunks
#                 ))

#             if current_total_tokens >= max_tokens:
#                 break

#         return compressed_groups

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         # AssemblyStage에서 넘어온 구조화된 데이터 확인
#         groups = getattr(ctx, "evidence_groups", [])
        
#         if not groups:
#             logger.info(f"[{self.name}] 압축할 데이터가 없습니다.")
#             return ctx

#         # 토큰 예산에 맞춰 객체 단위 압축 수행
#         compressed_groups = self._compress_groups(groups, self.config.max_tokens)
        
#         # 압축된 결과를 다시 Context에 덮어씌움
#         ctx.evidence_groups = compressed_groups
        
#         logger.info(f"[{self.name}] 컨텍스트 압축 완료. (유지된 문서 그룹: {len(compressed_groups)}개)")
        
#         return ctx

import tiktoken
from pydantic import BaseModel
from typing import List, Optional

from src.rag.core.types import RagRequest, RagContext, EvidenceGroup, SourceChunk
from src.rag.core.interfaces import RagStage
from src.common.logger import get_logger

# 올바른 인터페이스(레지스트리) 임포트
from src.rag.services.registry import TextCompressorRegistry

logger = get_logger(__name__)

class CompressionConfig(BaseModel):
    # 최대 허용 토큰 수
    max_tokens: int = 3000
    # 토큰 계산에 사용할 인코더
    tokenizer_model: str = "gpt-4o-mini" 
    # SLM 기반 의미적 압축 사용 여부
    use_semantic_compression: bool = True

class CompressionStage(RagStage[CompressionConfig]):
    name = "compression"

    def __init__(self, config: CompressionConfig, registry: TextCompressorRegistry):
        super().__init__(config)
        self.registry = registry
        try:
            self.encoder = tiktoken.encoding_for_model(self.config.tokenizer_model)
        except KeyError:
            logger.warning(f"지원하지 않는 토크나이저 모델. 기본값(cl100k_base)으로 폴백합니다.")
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        """텍스트의 정확한 토큰 수를 계산"""
        return len(self.encoder.encode(text))

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        groups = getattr(ctx, "evidence_groups", [])
        
        if not groups:
            logger.info(f"[{self.name}] 압축할 데이터가 없습니다.")
            return ctx

        # -------------------------------------------------------------
        # STEP 1: Semantic Compression (의미 기반 텍스트 밀도 압축)
        # -------------------------------------------------------------
        if self.config.use_semantic_compression:
            try:
                compressor = self.registry.get("slm_compressor")
                
                # 모든 청크의 텍스트를 평탄화(Flatten)하여 수집
                all_chunks = [chunk for group in groups for chunk in group.chunks]
                texts_to_compress = [chunk.content for chunk in all_chunks]
                
                if texts_to_compress:
                    logger.info(f"[{self.name}] {len(texts_to_compress)}개의 청크에 대해 SLM 의미 기반 압축을 시작합니다.")
                    # 비동기 병렬로 모든 텍스트 압축
                    compressed_texts = await compressor.forward(texts_to_compress)
                    
                    # 압축된 텍스트를 다시 원본 청크 객체에 매핑
                    for chunk, comp_text in zip(all_chunks, compressed_texts):
                        orig_len = len(chunk.content)
                        comp_len = len(comp_text)
                        logger.debug(f"[{self.name}] 청크 ID {chunk.chunk_id} 압축: {orig_len}자 -> {comp_len}자")
                        chunk.content = comp_text
                        
            except Exception as e:
                logger.error(f"[{self.name}] 의미 기반 압축 중 에러 발생 (기존 텍스트를 유지하고 다음 단계로 넘어갑니다): {e}")

        # -------------------------------------------------------------
        # STEP 2: Budget-aware Truncation (안전장치 - 물리적 삭감)
        # -------------------------------------------------------------
        compressed_groups = []
        current_total_tokens = 0

        for group in groups:
            kept_chunks = []
            for chunk in group.chunks:
                # 메타데이터나 구조화를 위해 추가될 오버헤드를 고려하여 여유 있게 계산
                chunk_text = f"{group.title}\n{chunk.content}" 
                chunk_tokens = self._count_tokens(chunk_text)

                if current_total_tokens + chunk_tokens <= self.config.max_tokens:
                    kept_chunks.append(chunk)
                    current_total_tokens += chunk_tokens
                else:
                    logger.info(f"[{self.name}] 토큰 한도 초과. 청크 ID {chunk.chunk_id} (출처: {group.title}) 부터 드랍합니다.")
                    break 

            if kept_chunks:
                # 살아남은 청크들로만 새로운 EvidenceGroup 객체 생성
                compressed_groups.append(EvidenceGroup(
                    group_id=group.group_id,
                    title=group.title,
                    chunks=kept_chunks
                ))

            if current_total_tokens >= self.config.max_tokens:
                break

        ctx.evidence_groups = compressed_groups
        logger.info(f"[{self.name}] 컨텍스트 최종 압축 및 예산 할당 완료. (유지된 그룹: {len(compressed_groups)}개, 총 토큰: {current_total_tokens})")
        
        return ctx