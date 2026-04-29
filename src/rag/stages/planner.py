# import re
# from pydantic import BaseModel
# from src.rag.core.types import RagRequest, RagContext
# from src.rag.core.interfaces import RagStage, Tracer
# from src.rag.services.registry import PlannerRegistry
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class PlannerConfig(BaseModel):
#     provider: str = "default"

# class PlannerStage(RagStage[PlannerConfig]):
#     name = "planner"

#     def __init__(self, config: PlannerConfig, registry: PlannerRegistry, tracer: Tracer):
#         super().__init__(config)
#         self.registry = registry
#         self.tracer = tracer

#     def _semantic_route(self, query: str) -> dict | None:
#         """가벼운 정규식/키워드 기반의 프론트도어 시맨틱 라우터 (L7 필터 역할)"""
#         # 특수문자만 제거하고 띄어쓰기는 살림 (정규식 오작동 방지)
#         clean_query = re.sub(r'[^\w\s]', '', query).strip()
        
#         chitchat_patterns = [
#             r"^(안녕|안녕하세요|반가워|누구야|hello|hi)\b", 
#             r"^(하이|하이요|하이하이)$",  # '하이'는 독립적으로 쓰일 때만 매칭 ('하이브리드' 방어)
#             r"^(너는 누구|너의 이름은)",
#             r"(어떤 일|뭐 할 수|뭐해|뭐하시|어때)$"
#         ]
        
#         for pattern in chitchat_patterns:
#             if re.search(pattern, clean_query):
#                 return {
#                     "intent": "chitchat", 
#                     "requires_db": False, 
#                     "complexity": "low",
#                     "strict_validation": False,
#                     "routed_by": "semantic_frontdoor"
#                 }
                
#         return None

#     def _apply_routing_flags(self, ctx: RagContext, plan: dict, request: RagRequest) -> None:
#         """분석된 plan 딕셔너리를 바탕으로 Context의 라우팅 플래그를 설정"""
#         intent = plan.get("intent", "search")
#         requires_db = plan.get("requires_db", True)
#         strict_validation = plan.get("strict_validation", False)
        
#         ctx.intent = intent
#         ctx.plan_id = intent
#         ctx.plan = plan

#         # 1. 아예 검색이 필요 없는 경우 (Chitchat 등)
#         if intent == "chitchat" or not requires_db:
#             ctx.skip_retrieval = True
#             ctx.skip_reranker = True
            
#         # 2. 단순 정보 검색 (Reranker의 무거운 교차 검증 연산 생략)
#         elif intent == "simple_search":
#             ctx.skip_retrieval = False
#             ctx.skip_reranker = True
            
#         # 3. 복잡한 수학 문제 풀이 등 (전체 파이프라인 가동)
#         else:
#             ctx.skip_retrieval = False
#             ctx.skip_reranker = False

#         # 4. 스트리밍 및 검증 모드 제어 로직
#         # 클라이언트가 스트리밍을 원하지 않거나, 작업 자체가 엄격한 검증(authoring 등)을 요구하는 경우
#         if not request.stream_response or strict_validation or intent == "authoring":
#             ctx.is_streaming = False
#             ctx.strict_validation = True
#             ctx.stream_queue = None  # Generator에서 프론트로 토큰을 쏘는 것을 원천 차단
#             logger.info("[PlannerStage] Strict/Authoring 모드: 스트리밍 비활성화 및 Post-Check 강화 설정 완료")
#         else:
#             ctx.is_streaming = True
#             ctx.strict_validation = False

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         with self.tracer.span("planner", provider=self.config.provider):
            
#             # 1. Front-door Semantic Router (Fast Path)
#             semantic_plan = self._semantic_route(request.user_query)
            
#             if semantic_plan:
#                 logger.info("[PlannerStage] Semantic Router 빠른 처리 완료 (sLM 스킵)")
#                 self._apply_routing_flags(ctx, semantic_plan, request)
#                 return ctx

#             # 2. Semantic Router에서 걸러지지 않은 복잡한 쿼리만 sLM 플러그인 호출 
#             logger.info("[PlannerStage] Semantic 매칭 실패. sLM 플러그인 딥 다이브 시작.")
#             planner_plugin = self.registry.get(self.config.provider)
            
#             # sLM은 "intent", "requires_db", "strict_validation" 등의 키를 가진 dict를 반환한다고 가정
#             plan_result = await planner_plugin.forward(request.user_query)
            
#             # 3. sLM 분석 결과를 컨텍스트 플래그에 적용
#             logger.info(f"[PlannerStage] sLM 의도 분석 완료: {plan_result.get('intent')}")
#             self._apply_routing_flags(ctx, plan_result, request)

#         return ctx


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