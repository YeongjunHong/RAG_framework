from typing import List, Sequence, Dict, Any
import asyncpg
import json
#추가 
from langchain_huggingface import HuggingFaceEmbeddings

from src.rag.core.types import SourceChunk, ScoredChunk
from src.rag.core.interfaces import RagRetriever
from src.common.logger import get_logger

logger = get_logger(__name__)

class PostgresHybridRetriever(RagRetriever):
    def __init__(self, dsn: str):
        self.dsn = dsn
        # 추가
        logger.info("Retriever 내부 임베딩 모델 로드 중...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="jhgan/ko-sroberta-multitask",
            model_kwargs={'device': 'cpu'}, 
            encode_kwargs={'normalize_embeddings': True}
        )

    async def forward(
        self,
        *,
        queries: Sequence[Any], # 텍스트 질문
        # query_vector: List[float], #  질문을 768차원으로 임베딩한 리스트로 리턴 -> 내부에서 알아서 만들게끔 수정
        top_k: int = 5,
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
        filters: Dict[str, Any] = None, 
    ) -> List[ScoredChunk]:
        
        # if not queries or not query_vector:
        if not queries:
            return []
            
        q_text = queries[0].content if hasattr(queries[0], 'content') else str(queries[0])
        # asyncpg에서 pgvector와 통신하기 위해 파이썬 리스트를 벡터 문자열 포맷으로 변환
        #추가
        query_vector = self.embeddings.embed_query(q_text)
        q_vector_str = f"[{','.join(map(str, query_vector))}]"
        
        async with asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=5) as pool:
            async with pool.acquire() as conn:
                
                # 기본 파라미터 세팅
                args = [q_text, q_vector_str, top_k, bm25_weight, vector_weight]
                extra_where = ""
                
                # 동적 필터링 (source_knowledge의 subject 등 필터링)
                if filters:
                    for key, value in filters.items():
                        args.append(value)
                        # sk는 source_knowledge 테이블의 알리아스
                        extra_where += f" AND sk.{key} = ${len(args)}"

                #  4개 테이블을 JOIN하는 하이브리드 RRF 쿼리
                hybrid_sql = f"""
                WITH bm25_search AS (
                    -- 1. 키워드 기반 검색 (BM25)
                    SELECT 
                        sc.id AS chunk_id,
                        ts_rank_cd(sc.chunk_tsv, websearch_to_tsquery('simple', $1)) AS bm25_score
                    FROM source_chunk sc
                    JOIN map_source_chunk msc ON sc.id = msc.chunk_id
                    JOIN source_knowledge sk ON msc.source_id = sk.id
                    WHERE sc.chunk_tsv @@ websearch_to_tsquery('simple', $1)
                    {extra_where}
                    ORDER BY bm25_score DESC
                    LIMIT 100 -- 풀스캔 방지를 위해 적당히 끊음
                ),
                vector_search AS (
                    -- 2. 의미 기반 검색 (pgvector Cosine Similarity)
                    -- 1 - 코사인 거리 = 코사인 유사도 (높을수록 좋음)
                    SELECT 
                        scv.chunk_id,
                        1 - (scv.chunk_vec <=> $2::vector(768)) AS vector_score
                    FROM source_chunk_vec scv
                    JOIN map_source_chunk msc ON scv.chunk_id = msc.chunk_id
                    JOIN source_knowledge sk ON msc.source_id = sk.id
                    WHERE 1=1
                    {extra_where}
                    ORDER BY scv.chunk_vec <=> $2::vector(768)
                    LIMIT 100
                )
                -- 3. 두 결과를 결합하고 가중치 합산 (Weighted Sum)
                SELECT 
                    sc.id AS chunk_id, 
                    msc.source_id, 
                    sc.content, 
                    sc.chunk_index,
                    COALESCE(b.bm25_score, 0) AS raw_bm25,
                    COALESCE(v.vector_score, 0) AS raw_vector,
                    (COALESCE(b.bm25_score, 0) * $4) + (COALESCE(v.vector_score, 0) * $5) AS final_score
                FROM source_chunk sc
                JOIN map_source_chunk msc ON sc.id = msc.chunk_id
                LEFT JOIN bm25_search b ON sc.id = b.chunk_id
                LEFT JOIN vector_search v ON sc.id = v.chunk_id
                WHERE b.chunk_id IS NOT NULL OR v.chunk_id IS NOT NULL
                ORDER BY final_score DESC
                LIMIT $3;
                """
                
                try:
                    rows = await conn.fetch(hybrid_sql, *args)
                except Exception as e:
                    logger.error(f"하이브리드 SQL 실행 실패: {e}")
                    return []

        out: List[ScoredChunk] = []
        for r in rows:
            ch = SourceChunk(
                chunk_id=int(r["chunk_id"]),
                source_id=int(r["source_id"]), # 실제 source_id
                source_name="postgres_hybrid",
                content=str(r["content"]),
                metadata={
                    "chunk_index": int(r["chunk_index"]),
                    "raw_bm25_score": float(r["raw_bm25"]),
                    "raw_vector_score": float(r["raw_vector"])
                },
            )
            out.append(ScoredChunk(chunk=ch, score=float(r["final_score"])))
            
        return out
    
if __name__ == "__main__": 
    # Windows 환경 비동기 에러 방지용 설정 (맥/리눅스는 영향 없음)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 이 줄이 없으면 main 함수가 실행되지 않고 그냥 끝납니다!
    asyncio.run(main())