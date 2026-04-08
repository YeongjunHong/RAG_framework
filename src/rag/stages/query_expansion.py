# from typing import List, Literal
# from pydantic import BaseModel

# from src.rag.core.types import RagRequest, RagContext, ExpandedQuery
# from src.rag.core.interfaces import RagStage
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class QueryExpansionConfig(BaseModel):
#     mode: Literal["none", "simple_rules"] = "simple_rules"
#     max_expansions: int = 3

# class QueryExpansionStage(RagStage[QueryExpansionConfig]):
#     name = "query_expansion"

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         q = request.user_query.strip()
        
#         # 1. 기본 쿼리: 원본 사용자 요청
#         expanded_queries = [
#             ExpandedQuery(content=q, intent="original", channels={"bm25", "vector"})
#         ]

#         if self.config.mode == "none":
#             ctx.expanded_queries = expanded_queries
#             return ctx

#         # 2. 범용적인 단순 규칙 (simple_rules)
#         # 이 부분은 나중에 더 수정 
#         if self.config.mode == "simple_rules":
#             if len(q) >= 2:
#                 # 예시: 범용적인 키워드 확장 (추후에 openrouter로 연동 가능)
#                 expanded_queries.append(
#                     ExpandedQuery(content=q + " 핵심 개념", intent="keyword", weight=0.8, channels={"bm25"})
#                 )
#                 expanded_queries.append(
#                     ExpandedQuery(content=q + " 설명", intent="semantic", weight=0.8, channels={"vector"})
#                 )
        
#         # 3. 만약 Planner나 다른 곳에서 넘어온 필터가 있다면 그대로 유지
#         # ctx.plan["retrieval"] = {"filters": {"chunk_version": "v1.0"}} 와 같이 세팅될 수 있음

#         ctx.expanded_queries = expanded_queries[: self.config.max_expansions]
#         return ctx

from typing import List, Literal
from pydantic import BaseModel

from src.rag.core.types import RagRequest, RagContext, ExpandedQuery
from src.rag.core.interfaces import RagStage, Tracer
from src.rag.services.registry import QueryExpanderRegistry
from src.common.logger import get_logger

logger = get_logger(__name__)

class QueryExpansionConfig(BaseModel):
    # 'dynamic' 모드를 기본으로 추가하여 LLM 기반 확장을 지원
    mode: Literal["none", "simple_rules", "dynamic"] = "dynamic"
    max_expansions: int = 4
    provider: str = "default"

class QueryExpansionStage(RagStage[QueryExpansionConfig]):
    name = "query_expansion"

    # Registry와 Tracer 주입 (DI)
    def __init__(self, config: QueryExpansionConfig, registry: QueryExpanderRegistry, tracer: Tracer):
        super().__init__(config)
        self.registry = registry
        self.tracer = tracer

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        q = request.user_query.strip()
        
        # 1. 기본 쿼리: 원본 사용자 요청 (BM25, Vector 둘 다 높은 가중치로 탐색)
        expanded_queries = [
            ExpandedQuery(content=q, intent="original", weight=1.0, channels={"bm25", "vector"})
        ]

        # 플래너에서 검색을 스킵하라고 했거나, mode가 none인 경우 원본만 반환
        if ctx.skip_retrieval or self.config.mode == "none":
            ctx.expanded_queries = expanded_queries
            return ctx

        # 2. 동적 라우팅 기반 LLM 확장 (dynamic mode)
        if self.config.mode == "dynamic":
            with self.tracer.span("query_expansion", provider=self.config.provider):
                intent = ctx.intent
                
                try:
                    if intent == "simple_search":
                        # 전략 C: 키워드 추출 (BM25 전용 타겟팅)
                        keyword_plugin = self.registry.get("keyword_extractor")
                        keywords = await keyword_plugin.forward(q)
                        if keywords:
                            expanded_queries.append(
                                ExpandedQuery(
                                    content=" ".join(keywords), 
                                    intent="keyword", 
                                    weight=0.9, 
                                    channels={"bm25"} # 키워드 검색은 BM25에만 태움
                                )
                            )
                            
                    elif intent in ["search", "authoring"]:
                        # 전략 A: 다중 쿼리 생성 (Vector Search 커버리지 확장)
                        mq_plugin = self.registry.get("multi_query")
                        generated_queries = await mq_plugin.forward(q)
                        
                        for gen_q in generated_queries:
                            expanded_queries.append(
                                ExpandedQuery(
                                    content=gen_q, 
                                    intent="semantic", 
                                    weight=0.7, # 파생 쿼리는 원본보다 약간 낮은 가중치
                                    channels={"vector"} # 의미적 확장은 Vector DB 타겟팅
                                )
                            )
                except Exception as e:
                    logger.error(f"[QueryExpansion] 동적 확장 실패, 원본 쿼리 유지: {e}")
                    # 에러 발생 시 파이프라인 중단 없이 Fallback

        # 3. 범용적인 단순 규칙 (Fallback 용도 혹은 테스트 용도)
        elif self.config.mode == "simple_rules":
            if len(q) >= 2:
                expanded_queries.append(
                    ExpandedQuery(content=q + " 핵심 개념", intent="keyword", weight=0.8, channels={"bm25"})
                )
                expanded_queries.append(
                    ExpandedQuery(content=q + " 설명", intent="semantic", weight=0.8, channels={"vector"})
                )

        # 최대 확장 개수 제한 적용
        ctx.expanded_queries = expanded_queries[: self.config.max_expansions]
        logger.info(f"[QueryExpansion] 최종 쿼리 세트: {[eq.content for eq in ctx.expanded_queries]}")
        
        return ctx