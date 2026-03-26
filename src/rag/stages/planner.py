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

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         # 1. 레지스트리에서 설정된 플래너(sLM 등) 객체 획득
#         planner_plugin = self.registry.get(self.config.provider)
        
#         # 2. 트레이싱 스팬을 열고 플래너 실행
#         with self.tracer.span("planner", provider=self.config.provider):
#             plan_result = await planner_plugin.forward(request.user_query)
            
#             # 3. 분석 결과를 파이프라인 컨텍스트에 저장
#             ctx.plan = plan_result
#             ctx.plan_id = plan_result.get("intent", "search")
            
#             logger.info(f"[PlannerStage] 의도 분석 완료: {ctx.plan_id}")

#         return ctx


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
#         # 특수문자 제거 및 공백 정제 (검색 정확도 향상)
#         clean_query = re.sub(r'[^\w\s]', '', query).strip()
        
#         # 1. 인사말 및 잡담 패턴 (가장 빈번하고 LLM 토큰 낭비가 심한 쿼리)
#         chitchat_patterns = [
#             r"^(안녕|안녕하세요|반가워|누구야|너는|하이|hello|hi)",
#             r"(어떤 일|뭐 할 수|뭐해|뭐하시)"
#         ]
        
#         for pattern in chitchat_patterns:
#             if re.search(pattern, clean_query):
#                 return {
#                     "intent": "chitchat", 
#                     "requires_db": False, 
#                     "complexity": "low",
#                     "routed_by": "semantic_frontdoor"  # 추후 로깅/디버깅을 위한 태그
#                 }
                
#         # 매칭 실패 시 None 반환 -> 무거운 sLM으로 폴백(Fallback)
#         return None 

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         with self.tracer.span("planner", provider=self.config.provider):
            
#             # 1. Front-door Semantic Router (Fast Path)
#             semantic_plan = self._semantic_route(request.user_query)
            
#             if semantic_plan:
#                 logger.info(f"[PlannerStage] Semantic Router 빠른 처리 완료 (sLM 스킵): {semantic_plan}")
#                 ctx.plan = semantic_plan
#                 ctx.plan_id = semantic_plan.get("intent", "search")
#                 return ctx

#             # 2. Semantic Router에서 걸러지지 않은 복잡한 쿼리만 sLM 플러그인 호출 
#             logger.info("[PlannerStage] Semantic 매칭 실패. sLM 플러그인 딥 다이브 시작.")
#             planner_plugin = self.registry.get(self.config.provider)
            
#             plan_result = await planner_plugin.forward(request.user_query)
            
#             # 3. sLM 분석 결과를 컨텍스트에 저장
#             ctx.plan = plan_result
#             ctx.plan_id = plan_result.get("intent", "search")
            
#             logger.info(f"[PlannerStage] sLM 의도 분석 완료: {ctx.plan_id}")

#         return ctx

import re
from pydantic import BaseModel
from src.rag.core.types import RagRequest, RagContext
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
        
        chitchat_patterns = [
            r"^(안녕|안녕하세요|반가워|누구야|너는|하이|hello|hi)",
            r"(어떤 일|뭐 할 수|뭐해|뭐하시)"
        ]
        
        for pattern in chitchat_patterns:
            if re.search(pattern, clean_query):
                return {
                    "intent": "chitchat", 
                    "requires_db": False, 
                    "complexity": "low",
                    "routed_by": "semantic_frontdoor"
                }
        # for demo 방법 2
        # simple_fact_patterns = [
        #     r"(전화번호|운영시간|운영 시간|고객센터|주소|위치|홈페이지)"
        # ]
        # for pattern in simple_fact_patterns:
        #     if re.search(pattern, clean_query):
        #         return {
        #             "intent": "simple_search", # 이 의도가 리랭커를 스킵하게 만듦
        #             "requires_db": True, 
        #             "complexity": "low",
        #             "routed_by": "semantic_frontdoor"
        #         }
                
        return None 

    def _apply_routing_flags(self, ctx: RagContext, plan: dict) -> None:
        """분석된 plan 딕셔너리를 바탕으로 Context의 라우팅 플래그를 설정"""
        intent = plan.get("intent", "search")
        requires_db = plan.get("requires_db", True)
        
        ctx.intent = intent
        ctx.plan_id = intent
        ctx.plan = plan

        # 1. 아예 검색이 필요 없는 경우 (Chitchat 등)
        if intent == "chitchat" or not requires_db:
            ctx.skip_retrieval = True
            ctx.skip_reranker = True
            
        # 2. 단순 정보 검색 (Reranker의 무거운 교차 검증 연산 생략)
        elif intent == "simple_search":
            ctx.skip_retrieval = False
            ctx.skip_reranker = True
            
        # 3. 복잡한 수학 문제 풀이 등 (전체 파이프라인 가동)
        else:
            ctx.skip_retrieval = False
            ctx.skip_reranker = False

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        with self.tracer.span("planner", provider=self.config.provider):
            
            # 1. Front-door Semantic Router (Fast Path)
            semantic_plan = self._semantic_route(request.user_query)
            
            if semantic_plan:
                logger.info(f"[PlannerStage] Semantic Router 빠른 처리 완료 (sLM 스킵)")
                self._apply_routing_flags(ctx, semantic_plan)
                return ctx

            # 2. Semantic Router에서 걸러지지 않은 복잡한 쿼리만 sLM 플러그인 호출 
            logger.info("[PlannerStage] Semantic 매칭 실패. sLM 플러그인 딥 다이브 시작.")
            planner_plugin = self.registry.get(self.config.provider)
            
            # sLM은 "intent", "requires_db" 등의 키를 가진 dict를 반환한다고 가정
            plan_result = await planner_plugin.forward(request.user_query)
            
            # 3. sLM 분석 결과를 컨텍스트 플래그에 적용
            logger.info(f"[PlannerStage] sLM 의도 분석 완료: {plan_result.get('intent')}")
            self._apply_routing_flags(ctx, plan_result)

        return ctx