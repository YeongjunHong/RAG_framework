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

# from pydantic import BaseModel
# from src.rag.core.types import RagRequest, RagContext, FilteredChunk
# from src.rag.core.interfaces import RagStage
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class FilteringConfig(BaseModel):
#     # CrossEncoder의 Raw Logit을 사용 중이라면 0.0을 커트라인으로 하면 위험함. 

#     # min_score: float = -5.0 
#     min_score: float = 0.70 # eval_threshold의 결과 값

# class FilteringStage(RagStage[FilteringConfig]):
#     name = "filtering"

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         if getattr(ctx, "skip_reranker", False) or not ctx.reranked:
#             logger.info(f"[{self.name}] 필터링 스킵 또는 리랭크된 데이터 없음.")
#             return ctx

#         filtered_results = []
#         kept_count = 0

#         # 1. 1차 점수 기반 필터링 
#         for scored_chunk in ctx.reranked:
#             # 점수가 min_score 이상이면 kept=True
#             is_kept = scored_chunk.score >= self.config.min_score
#             reasons = [] if is_kept else [f"Score({scored_chunk.score:.4f}) < Min({self.config.min_score})"]
            
#             filtered_results.append(FilteredChunk(
#                 chunk=scored_chunk.chunk,
#                 kept=is_kept,
#                 reasons=reasons,
#                 score=scored_chunk.score
#             ))
#             if is_kept:
#                 kept_count += 1

#         # 모든 문서가 Threshold 미달로 탈락했다면, 가장 점수가 높은 1위 문서를 강제로 구출
#         if kept_count == 0 and filtered_results:
#             logger.warning(f"[{self.name}] 모든 문서가 Threshold({self.config.min_score}) 미달로 탈락. 가장 높은 점수의 문서(Top-1)를 강제 구출합니다.")
            
#             # ctx.reranked는 이미 내림차순 정렬되어 있으므로 0번 인덱스가 최고 점수
#             filtered_results[0].kept = True
#             filtered_results[0].reasons = ["Forced Rescue (Context Starvation Prevention)"]
#             kept_count = 1

#         ctx.filtered = filtered_results
#         logger.info(f"[{self.name}] 필터링 완료: {len(ctx.reranked)}건 중 {kept_count}건 유지 (Threshold: {self.config.min_score})")
#         return ctx

# import json
# from pathlib import Path
# from pydantic import BaseModel
# from typing import Dict

# from src.rag.core.types import RagRequest, RagContext, FilteredChunk
# from src.rag.core.interfaces import RagStage
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class FilteringConfig(BaseModel):
#     thresholds_file: str = "settings/dynamic_thresholds.json"
#     default_min_score: float = 0.50

# class FilteringStage(RagStage[FilteringConfig]):
#     name = "filtering"

#     def __init__(self, config: FilteringConfig):
#         super().__init__(config)
#         self.thresholds_map = self._load_threshold_artifact()

#     def _load_threshold_artifact(self) -> Dict[str, float]:
#         """평가 파이프라인에서 생성한 Threshold 아티팩트 로드"""
#         artifact_path = Path(self.config.thresholds_file)
#         if not artifact_path.exists():
#             logger.warning(f"Threshold 아티팩트를 찾을 수 없습니다: {artifact_path}. 기본값을 사용합니다.")
#             return {}
            
#         try:
#             with open(artifact_path, "r") as f:
#                 thresholds = json.load(f)
#             logger.info(f"동적 Threshold 맵 로드 완료: {thresholds}")
#             return thresholds
#         except Exception as e:
#             logger.error(f"Threshold 아티팩트 파싱 실패: {e}. 기본값을 사용합니다.")
#             return {}

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         if getattr(ctx, "skip_reranker", False) or not ctx.reranked:
#             logger.info(f"[{self.name}] 필터링 스킵 또는 리랭크된 데이터 없음.")
#             return ctx

#         current_intent = getattr(ctx, "intent", "default")
#         # 인텐트에 맞는 Threshold 추출 (없으면 default, 그것도 없으면 config 기본값)
#         active_threshold = self.thresholds_map.get(
#             current_intent, 
#             self.thresholds_map.get("default", self.config.default_min_score)
#         )
#         # [추가된 로깅] 최고 점수 확인
#         if ctx.reranked:
#             max_score = ctx.reranked[0].score
#             logger.info(f"[{self.name}] 현재 Reranker 최고 점수: {max_score:.4f} / 요구 Threshold: {active_threshold:.4f}")

#         filtered_results = []
#         kept_count = 0

#         for scored_chunk in ctx.reranked:
#             is_kept = scored_chunk.score >= active_threshold
#             reasons = [] if is_kept else [f"Score({scored_chunk.score:.4f}) < Min({active_threshold})"]
            
#             filtered_results.append(FilteredChunk(
#                 chunk=scored_chunk.chunk,
#                 kept=is_kept,
#                 reasons=reasons,
#                 score=scored_chunk.score
#             ))
#             if is_kept:
#                 kept_count += 1

#         if kept_count == 0 and filtered_results:
#             logger.warning(f"[{self.name}] 모든 문서가 탈락하여 Top-1 문서를 구출합니다.")
#             filtered_results[0].kept = True
#             filtered_results[0].reasons = ["Forced Rescue"]
#             kept_count = 1

#         ctx.filtered = filtered_results
#         logger.info(f"[{self.name}] 인텐트 '{current_intent}' 필터링 완료: {len(ctx.reranked)}건 중 {kept_count}건 유지 (Threshold: {active_threshold})")
#         return ctx

import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Dict, List

from src.rag.core.types import RagRequest, RagContext, FilteredChunk, ScoredChunk
from src.rag.core.interfaces import RagStage
from src.common.logger import get_logger

logger = get_logger(__name__)

class IntentFilterRule(BaseModel):
    relative_margin: float = 0.15  # 1등 점수 대비 허용 편차
    min_k: int = 1                 # 컨텍스트 기아 방지 최소 보장 개수
    max_k: int = 10                # 토큰 낭비 방지 최대 허용 개수

class FilteringConfig(BaseModel):
    thresholds_file: str = "settings/dynamic_thresholds.json"
    default_floor: float = 0.30
    
    # 인텐트별 하이브리드 룰 정의
    rules: Dict[str, IntentFilterRule] = Field(default_factory=lambda: {
        "simple_search": IntentFilterRule(relative_margin=0.05, min_k=1, max_k=3), # 핀포인트
        "search": IntentFilterRule(relative_margin=0.15, min_k=2, max_k=7),        # 일반 검색
        "authoring": IntentFilterRule(relative_margin=0.20, min_k=4, max_k=15),    # 넓은 문맥
        "default": IntentFilterRule(relative_margin=0.15, min_k=1, max_k=5)
    })

class FilteringStage(RagStage[FilteringConfig]):
    name = "filtering"

    def __init__(self, config: FilteringConfig):
        super().__init__(config)
        self.floor_map = self._load_threshold_artifact()

    def _load_threshold_artifact(self) -> Dict[str, float]:
        artifact_path = Path(self.config.thresholds_file)
        if not artifact_path.exists():
            return {}
        try:
            with open(artifact_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        if getattr(ctx, "skip_reranker", False) or not ctx.reranked:
            return ctx

        current_intent = getattr(ctx, "intent", "default")
        floor_score = self.floor_map.get(current_intent, self.floor_map.get("default", self.config.default_floor))
        rule = self.config.rules.get(current_intent, self.config.rules["default"])

        logger.info(f"[{self.name}] 하이브리드 필터링 적용 (Intent: {current_intent}, Floor: {floor_score:.2f}, MinK: {rule.min_k})")

        # 1. 절대 하한선 방어 (Floor Cutoff)
        survivors_step1: List[ScoredChunk] = [c for c in ctx.reranked if c.score >= floor_score]

        if not survivors_step1:
            logger.warning(f"[{self.name}] 모든 문서가 하한선({floor_score:.2f}) 미달. 빈 컨텍스트를 반환합니다.")
            ctx.filtered = []
            return ctx

        # 2. 상대적 품질 제어 (Relative Margin)
        max_score = survivors_step1[0].score
        relative_threshold = max_score - rule.relative_margin
        
        survivors_step2: List[ScoredChunk] = [c for c in survivors_step1 if c.score >= relative_threshold]

        # 3. 체급 보장 (Min/Max K)
        if len(survivors_step2) < rule.min_k:
            logger.info(f"[{self.name}] Min K({rule.min_k}) 보장을 위해 하한선 통과 문서 중 일부를 강제 편입합니다.")
            final_chunks = survivors_step1[:rule.min_k]
        else:
            final_chunks = survivors_step2[:rule.max_k]

        # FilteredChunk 객체로 래핑하여 컨텍스트에 저장
        ctx.filtered = [
            FilteredChunk(chunk=c.chunk, kept=True, reasons=["Hybrid Filter Pass"], score=c.score)
            for c in final_chunks
        ]
        
        logger.info(f"[{self.name}] 필터링 완료: {len(ctx.filtered)}개 문서 유지 (최고 점수: {max_score:.4f})")
        return ctx