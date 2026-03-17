from typing import List, Literal
from pydantic import BaseModel

from src.rag.core.types import RagRequest, RagContext, ExpandedQuery
from src.rag.core.interfaces import RagStage
from src.common.logger import get_logger

logger = get_logger(__name__)

class QueryExpansionConfig(BaseModel):
    mode: Literal["none", "simple_rules"] = "simple_rules"
    max_expansions: int = 3

class QueryExpansionStage(RagStage[QueryExpansionConfig]):
    name = "query_expansion"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        q = request.user_query.strip()
        
        # 1. 기본 쿼리: 원본 사용자 요청
        expanded_queries = [
            ExpandedQuery(content=q, intent="original", channels={"bm25", "vector"})
        ]

        if self.config.mode == "none":
            ctx.expanded_queries = expanded_queries
            return ctx

        # 2. 범용적인 단순 규칙 (simple_rules)
        # 이 부분은 나중에 더 수정 
        if self.config.mode == "simple_rules":
            if len(q) >= 2:
                # 예시: 범용적인 키워드 확장 (추후에 openrouter로 연동 가능)
                expanded_queries.append(
                    ExpandedQuery(content=q + " 핵심 개념", intent="keyword", weight=0.8, channels={"bm25"})
                )
                expanded_queries.append(
                    ExpandedQuery(content=q + " 설명", intent="semantic", weight=0.8, channels={"vector"})
                )
        
        # 3. 만약 Planner나 다른 곳에서 넘어온 필터가 있다면 그대로 유지
        # ctx.plan["retrieval"] = {"filters": {"chunk_version": "v1.0"}} 와 같이 세팅될 수 있음

        ctx.expanded_queries = expanded_queries[: self.config.max_expansions]
        return ctx