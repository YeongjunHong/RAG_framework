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