import re
from typing import Any
from pydantic import BaseModel

from src.rag.core.types import RagContext, RagRequest
from src.rag.core.interfaces import RagStage, Tracer
from src.common.logger import get_logger

logger = get_logger(__name__)

class DynamicSkipConfig(BaseModel):
    use_rule_based_fast_skip: bool = True
    default_intent: str = "complex_math_solving"

class DynamicSkipStage(RagStage[DynamicSkipConfig]):
    name = "dynamic_skip"

    # slm_planner는 src/rag/plugins/slm_planner.py의 인스턴스를 DI 받음
    def __init__(self, config: DynamicSkipConfig, slm_planner: Any, tracer: Tracer):
        super().__init__(config)
        self.slm_planner = slm_planner
        self.tracer = tracer

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        with self.tracer.span("dynamic_skip"):
            prompt = ctx.prompt.strip()

            # 1. Rule-based Fast Skip (비용 0, 레이턴시 0)
            if self.config.use_rule_based_fast_skip:
                chitchat_patterns = [r"^(안녕|반가워|고마워|수고)", r"^[a-zA-Zㄱ-ㅎㅏ-ㅣ가-힣]{1,2}$"]
                if any(re.match(p, prompt) for p in chitchat_patterns):
                    logger.info(f"[{self.name}] Rule-based: 단순 대화 의도 감지.")
                    ctx.intent = "chitchat"
                    ctx.skip_retrieval = True
                    ctx.skip_reranker = True
                    return ctx

            # 2. SLM Planner를 통한 동적 의도 분류 (Llama-3-8b 등)
            try:
                # analyze_intent는 SLM 플러그인에 구현되어 있다고 가정하는 메서드
                intent = await self.slm_planner.analyze_intent(prompt)
                logger.info(f"[{self.name}] SLM Planner 의도 분류 결과: {intent}")
            except Exception as e:
                logger.warning(f"[{self.name}] SLM Planner 호출 실패. 기본값({self.config.default_intent})으로 폴백. 에러: {e}")
                intent = self.config.default_intent

            # Context에 의도 기록
            ctx.intent = intent

            # 3. Intent에 따른 Granular Routing 플래그 설정
            if intent == "chitchat":
                ctx.skip_retrieval = True
                ctx.skip_reranker = True
                
            elif intent == "simple_search":
                # 단순 개념 검색: 검색은 하되, 무거운 리랭커나 교차 검증은 생략
                ctx.skip_retrieval = False
                ctx.skip_reranker = True 
                
            elif intent == "complex_math_solving":
                # 복잡한 풀이: pgvector, BM25, Reranker 등 전체 파이프라인 가동
                ctx.skip_retrieval = False
                ctx.skip_reranker = False
                
            else:
                # 예기치 않은 분류값일 경우 보수적으로 전체 파이프라인 가동
                ctx.skip_retrieval = False
                ctx.skip_reranker = False

        return ctx