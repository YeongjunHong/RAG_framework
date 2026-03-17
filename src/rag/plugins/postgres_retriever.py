from typing import List, Sequence, Dict, Any
import asyncpg

from src.rag.core.types import SourceChunk, ScoredChunk
from src.rag.core.interfaces import RagRetriever
from src.common.logger import get_logger

logger = get_logger(__name__)

class PostgresHybridRetriever(RagRetriever):
    def __init__(self, dsn: str):
        self.dsn = dsn

    async def forward(
        self,
        *,
        queries: Sequence[Any], # ExpandedQuery 객체가 들어올 수도 있음
        top_k: int,
        bm25_weight: float,
        vector_weight: float,
        filters: Dict[str, Any] = None, #  메타데이터 필터를 받기 위해 추가됨!
    ) -> List[ScoredChunk]:
        
        if not queries:
            return []
            
        # ExpandedQuery 객체인지, 일반 문자열인지 확인 후 처리
        q = queries[0].content if hasattr(queries[0], 'content') else str(queries[0])
        
        async with asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=5) as pool:
            async with pool.acquire() as conn:
                
                # 기본 파라미터 ($1: 검색어, $2: 검색 개수)
                args = [q, top_k]
                extra_where = ""
                
                #  동적 WHERE 절 생성 (filters 딕셔너리가 주어졌을 때)
                if filters:
                    for key, value in filters.items():
                        # 파라미터 번호를 동적으로 할당 ($3, $4 ...)
                        args.append(value)
                        extra_where += f" AND {key} = ${len(args)}"

                #  동적으로 조립된 최종 SQL
                bm25_sql = f"""
                SELECT 
                    id AS chunk_id, 
                    0 AS source_id, 
                    content, 
                    chunk_index,
                    ts_rank_cd(chunk_tsv, websearch_to_tsquery('simple', $1)) AS score
                FROM 
                    source_chunk
                WHERE 
                    chunk_tsv @@ websearch_to_tsquery('simple', $1)
                    {extra_where}
                ORDER BY 
                    score DESC
                LIMIT $2;
                """
                
                # args 리스트를 언패킹(*args)하여 쿼리 실행
                try:
                    rows = await conn.fetch(bm25_sql, *args)
                except Exception as e:
                    logger.error(f"동적 SQL 실행 실패: {e}")
                    return []

        out: List[ScoredChunk] = []
        for r in rows:
            ch = SourceChunk(
                chunk_id=int(r["chunk_id"]),
                source_id=int(r["source_id"]),
                source_name="postgres_bm25",
                content=str(r["content"]),
                metadata={"chunk_index": int(r["chunk_index"])},
            )
            final_score = float(r["score"]) * bm25_weight
            out.append(ScoredChunk(chunk=ch, score=final_score))
            
        return out