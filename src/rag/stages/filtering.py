# # from typing import Dict, List
# # from pydantic import BaseModel

# # from src.rag.core.types import RagRequest, RagContext, ScoredChunk
# # from src.rag.core.interfaces import RagStage


# # class FilteringConfig(BaseModel):
# #     min_score: float = 0.0
# #     max_per_source: int = 5


# # class FilteringStage(RagStage[FilteringConfig]):
# #     name = "filtering"

# #     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
# #         items = ctx.reranked or ctx.retrieved
# #         out: List[ScoredChunk] = []
# #         per_source: Dict[str, int] = {}

# #         for sc in items:
# #             if sc.score < self.config.min_score:
# #                 continue
# #             sid = sc.chunk.source_id
# #             per_source[sid] = per_source.get(sid, 0) + 1
# #             if per_source[sid] > self.config.max_per_source:
# #                 continue
# #             out.append(sc)

# #         ctx.filtered = out
# #         return ctx

# from pydantic import BaseModel

# from src.rag.core.types import RagRequest, RagContext, FilteredChunk
# from src.rag.core.interfaces import RagStage


# class FilteringConfig(BaseModel):
#     # CrossEncoder(Logit) 기준: 0.0은 확률 50%를 의미함.
#     # 더 엄격하게 필터링하려면 1.0, 2.0 등으로 올리고, 느슨하게 하려면 -1.0 등으로 낮춤.
#     min_score: float = 0.0  


# class FilteringStage(RagStage[FilteringConfig]):
#     name = "filtering"

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         # 리랭킹된 결과가 없으면 스킵
#         if not ctx.reranked:
#             return ctx

#         ctx.filtered = []
        
#         for doc in ctx.reranked:
#             reasons = []
#             kept = True
            
#             # 1. 점수 기반 하드 필터링
#             if doc.score < self.config.min_score:
#                 kept = False
#                 reasons.append(f"Score ({doc.score:.4f}) < Threshold ({self.config.min_score})")

#             # 2. 추가적인 휴리스틱/메타데이터 필터링 확장을 위한 자리
#             # (예: 특정 tenant의 데이터만 허용, 본문 길이가 너무 짧은 청크 제외 등)
#             content_length = len(doc.chunk.content.strip())
#             if content_length < 10:
#                 kept = False
#                 reasons.append(f"Content too short ({content_length} chars)")

#             # 최종 상태를 FilteredChunk로 래핑하여 저장
#             filtered_chunk = FilteredChunk(
#                 chunk=doc.chunk,
#                 score=doc.score,
#                 kept=kept,
#                 reasons=reasons
#             )
            
#             ctx.filtered.append(filtered_chunk)
            
#         return ctx

from pydantic import BaseModel
from src.rag.core.types import RagRequest, RagContext, FilteredChunk
from src.rag.core.interfaces import RagStage
from src.common.logger import get_logger

logger = get_logger(__name__)

class FilteringConfig(BaseModel):
    # CrossEncoder의 Raw Logit을 사용 중이라면 0.0을 커트라인으로 하면 위험함. 

    # min_score: float = -5.0 
    min_score: float = 0.70

class FilteringStage(RagStage[FilteringConfig]):
    name = "filtering"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        if getattr(ctx, "skip_reranker", False) or not ctx.reranked:
            logger.info(f"[{self.name}] 필터링 스킵 또는 리랭크된 데이터 없음.")
            return ctx

        filtered_results = []
        kept_count = 0

        for scored_chunk in ctx.reranked:
            # 점수가 min_score 이상이면 kept=True
            is_kept = scored_chunk.score >= self.config.min_score
            reasons = [] if is_kept else [f"Score({scored_chunk.score:.2f}) < Min({self.config.min_score})"]
            
            filtered_results.append(FilteredChunk(
                chunk=scored_chunk.chunk,
                kept=is_kept,
                reasons=reasons,
                score=scored_chunk.score
            ))
            if is_kept:
                kept_count += 1

        ctx.filtered = filtered_results
        logger.info(f"[{self.name}] 필터링 완료: {len(ctx.reranked)}건 중 {kept_count}건 유지 (Threshold: {self.config.min_score})")
        return ctx