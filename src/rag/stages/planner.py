

import re
from pydantic import BaseModel
from src.rag.core.types import RagRequest, RagContext, QueryIntent
from src.rag.core.interfaces import RagStage, Tracer
from src.rag.services.registry import PlannerRegistry
from src.common.logger import get_logger

logger = get_logger(__name__)

class PlannerConfig(BaseModel):
    provider: str = "default"

class PlannerStage(RagStage[PlannerConfig]):
    name = "planner"

    def __init__(self, config: PlannerConfig, registry: PlannerRegistry, tracer: Tracer):
        super().__init__(config)
        self.registry = registry
        self.tracer = tracer

    def _semantic_route(self, query: str) -> dict | None:
        """가벼운 정규식/키워드 기반의 프론트도어 시맨틱 라우터 (L7 필터 역할)"""
        clean_query = re.sub(r'[^\w\s]', '', query).strip()
        
        # [MODIFIED] dynamic_skip.py에 있던 Rule-based 로직까지 통합
        chitchat_patterns = [
            r"^(안녕|안녕하세요|반가워|누구야|hello|hi|고마워|수고)\b", 
            r"^(하이|하이요|하이하이)$",
            r"^[a-zA-Zㄱ-ㅎㅏ-ㅣ가-힣]{1,2}$", # 극단적으로 짧은 단어 방어
            r"(어떤 일|뭐 할 수|뭐해|뭐하시|어때)$"
        ]
        
        for pattern in chitchat_patterns:
            if re.search(pattern, clean_query):
                return {
                    "intent": QueryIntent.CHITCHAT, 
                    "requires_db": False, 
                    "strict_validation": False,
                }
        return None

    def _apply_routing_flags(self, ctx: RagContext, plan: dict, request: RagRequest) -> None:
        # [MODIFIED] Enum 기반 안전한 할당
        intent = plan.get("intent", QueryIntent.UNKNOWN)
        if isinstance(intent, str):
            try:
                intent = QueryIntent(intent)
            except ValueError:
                intent = QueryIntent.UNKNOWN
                
        requires_db = plan.get("requires_db", True)
        strict_validation = plan.get("strict_validation", False)
        
        ctx.intent = intent
        ctx.plan = plan

        # Granular Routing Flags
        if intent == QueryIntent.CHITCHAT or not requires_db:
            ctx.skip_retrieval = True
            ctx.skip_reranker = True
        elif intent == QueryIntent.SIMPLE_SEARCH:
            ctx.skip_retrieval = False
            ctx.skip_reranker = True
        else: # COMPLEX_MATH_SOLVING 등
            ctx.skip_retrieval = False
            ctx.skip_reranker = False

        if not request.stream_response or strict_validation or intent == QueryIntent.AUTHORING:
            ctx.is_streaming = False
            ctx.strict_validation = True
            ctx.stream_queue = None
        else:
            ctx.is_streaming = True
            ctx.strict_validation = False

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        with self.tracer.span("planner", provider=self.config.provider):
            semantic_plan = self._semantic_route(request.user_query)
            if semantic_plan:
                logger.info("[PlannerStage] Rule-based 매칭 완료 (sLM 스킵)")
                self._apply_routing_flags(ctx, semantic_plan, request)
                return ctx

            logger.info("[PlannerStage] sLM 기반 의도 분석 시작")
            planner_plugin = self.registry.get(self.config.provider)
            plan_result = await planner_plugin.forward(request.user_query)
            
            self._apply_routing_flags(ctx, plan_result, request)
        return ctx