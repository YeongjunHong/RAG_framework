# import asyncio
# import re
# import sys
# from typing import List, Sequence, Dict, Any
# import asyncpg
# from langchain_huggingface import HuggingFaceEmbeddings

# from src.rag.core.types import SourceChunk, ScoredChunk
# from src.rag.core.interfaces import RagRetriever
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class PostgresHybridRetriever(RagRetriever):
#     def __init__(self, dsn: str):
#         self.dsn = dsn
#         logger.info("Retriever 내부 임베딩 모델 로드 중...")
#         self.embeddings = HuggingFaceEmbeddings(
#             model_name="jhgan/ko-sroberta-multitask",
#             model_kwargs={'device': 'cpu'}, 
#             encode_kwargs={'normalize_embeddings': True}
#         )

#     async def forward(
#         self,
#         *,
#         queries: Sequence[Any], 
#         top_k: int = 5,
#         bm25_weight: float = 0.3,
#         vector_weight: float = 0.7,
#         filters: Dict[str, Any] = None, 
#     ) -> List[ScoredChunk]:
        
#         if not queries:
#             return []

#         # 1. 쿼리 텍스트 추출 및 전처리 (다중 쿼리 지원)
#         q_texts = [q.content if hasattr(q, 'content') else str(q) for q in queries]
        
#         # 2. 배치 임베딩 (이벤트 루프 블로킹 방지를 위해 스레드 풀로 위임)
#         # embed_documents를 사용하여 여러 텍스트를 한 번의 연산으로 벡터화
#         query_vectors = await asyncio.to_thread(self.embeddings.embed_documents, q_texts)

#         # 3. 비동기 DB 작업 준비 (단일 쿼리용 SQL 실행 함수)
#         async def fetch_for_single_query(conn, text: str, vector: List[float]) -> List[dict]:
#             clean_text = re.sub(r'[^\w\s]', '', text)
#             tokens = [t for t in clean_text.split() if t]
#             tsquery_str = " | ".join(tokens) if tokens else ""
            
#             if not tsquery_str:
#                 return []

#             q_vector_str = f"[{','.join(map(str, vector))}]"
#             args = [tsquery_str, q_vector_str, top_k, bm25_weight, vector_weight]
#             extra_where = ""
            
#             # (보안 경고) 실제 운영시 key는 화이트리스트 검증 필요
#             if filters:
#                 for key, value in filters.items():
#                     args.append(value)
#                     extra_where += f" AND sk.{key} = ${len(args)}"

#             hybrid_sql = f"""
#             WITH bm25_search AS (
#                 SELECT sc.id AS chunk_id, ts_rank_cd(sc.chunk_tsv, to_tsquery('simple', $1)) AS bm25_score
#                 FROM source_chunk sc
#                 JOIN map_source_chunk msc ON sc.id = msc.chunk_id
#                 JOIN source_knowledge sk ON msc.source_id = sk.id
#                 WHERE sc.chunk_tsv @@ to_tsquery('simple', $1)
#                 {extra_where}
#                 ORDER BY bm25_score DESC LIMIT 100
#             ),
#             vector_search AS (
#                 SELECT scv.chunk_id, 1 - (scv.chunk_vec <=> $2::vector(768)) AS vector_score
#                 FROM source_chunk_vec scv
#                 JOIN map_source_chunk msc ON scv.chunk_id = msc.chunk_id
#                 JOIN source_knowledge sk ON msc.source_id = sk.id
#                 WHERE 1=1
#                 {extra_where}
#                 ORDER BY scv.chunk_vec <=> $2::vector(768) LIMIT 100
#             )
#             SELECT 
#                 sc.id AS chunk_id, msc.source_id, sc.content, sc.chunk_index,
#                 COALESCE(b.bm25_score, 0) AS raw_bm25,
#                 COALESCE(v.vector_score, 0) AS raw_vector,
#                 (COALESCE(b.bm25_score, 0) * $4) + (COALESCE(v.vector_score, 0) * $5) AS final_score
#             FROM source_chunk sc
#             JOIN map_source_chunk msc ON sc.id = msc.chunk_id
#             LEFT JOIN bm25_search b ON sc.id = b.chunk_id
#             LEFT JOIN vector_search v ON sc.id = v.chunk_id
#             WHERE b.chunk_id IS NOT NULL OR v.chunk_id IS NOT NULL
#             ORDER BY final_score DESC LIMIT $3;
#             """
#             return await conn.fetch(hybrid_sql, *args)

#         # 4. 커넥션 풀을 열고 모든 쿼리에 대해 동시 실행 (Concurrent I/O)
#         all_results = []
        
#         # 추후 FastAPI나 LangGraph 앱의 Lifespan 단계에서 풀을 한 번만 생성해서 공유하도록 아키텍처를 개선
#         async with asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=5) as pool:
#             async with pool.acquire() as conn:
#                 tasks = [
#                     fetch_for_single_query(conn, text, vector) 
#                     for text, vector in zip(q_texts, query_vectors)
#                 ]
#                 # DB I/O를 동시에 던지고 모두 끝날 때까지 대기
#                 results_per_query = await asyncio.gather(*tasks, return_exceptions=True)
                
#                 for res in results_per_query:
#                     if isinstance(res, Exception):
#                         logger.error(f"다중 쿼리 SQL 실행 실패: {res}")
#                     elif res:
#                         all_results.extend(res)

#         # 5. 결과 융합 (Result Fusion) 및 중복 제거
#         # 동일한 chunk_id가 여러 쿼리에서 검색되었을 경우, 가장 높은 final_score를 채택 (Max Score Fusion)
#         fused_chunks: Dict[int, ScoredChunk] = {}
        
#         for r in all_results:
#             cid = int(r["chunk_id"])
#             score = float(r["final_score"])
            
#             if cid not in fused_chunks or fused_chunks[cid].score < score:
#                 ch = SourceChunk(
#                     chunk_id=cid,
#                     source_id=int(r["source_id"]),
#                     source_name="postgres_hybrid",
#                     content=str(r["content"]),
#                     metadata={
#                         "chunk_index": int(r["chunk_index"]),
#                         "raw_bm25_score": float(r["raw_bm25"]),
#                         "raw_vector_score": float(r["raw_vector"])
#                     },
#                 )
#                 fused_chunks[cid] = ScoredChunk(chunk=ch, score=score)

#         # 6. 최종 점수순 정렬 후 top_k 개수만큼 잘라서 반환
#         sorted_out = sorted(fused_chunks.values(), key=lambda x: x.score, reverse=True)
#         return sorted_out[:top_k]
    
# if __name__ == "__main__": 
#     # Windows 환경 비동기 에러 방지용 설정 (맥/리눅스는 영향 없음)
#     if sys.platform == 'win32':
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
#     # asyncio.run(main()) # 테스트 시 main 함수 정의 후 활성화

# import asyncio
# import re
# import sys
# from typing import List, Sequence, Dict, Any
# import asyncpg
# from langchain_huggingface import HuggingFaceEmbeddings

# from src.rag.core.types import SourceChunk, ScoredChunk
# from src.rag.core.interfaces import RagRetriever
# from src.common.logger import get_logger

# logger = get_logger(__name__)
# import os
# class PostgresHybridRetriever(RagRetriever):
#     def __init__(self, dsn: str):
#         self.dsn = dsn

#         logger.info("Retriever 내부 임베딩 모델 로드 중...")
#         self.embeddings = HuggingFaceEmbeddings(
#             model_name="jhgan/ko-sroberta-multitask",
#             model_kwargs={'device': 'cpu'}, 
#             encode_kwargs={'normalize_embeddings': True}
#         )

#     async def forward(
#         self,
#         *,
#         queries: Sequence[Any], 
#         top_k: int = 5,
#         bm25_weight: float = 0.3,
#         vector_weight: float = 0.7,
#         filters: Dict[str, Any] = None, 
#     ) -> List[ScoredChunk]:
        
#         if not queries:
#             return []

#         # 1. 쿼리 텍스트 추출 및 전처리 (다중 쿼리 지원)
#         q_texts = [q.content if hasattr(q, 'content') else str(q) for q in queries]
        
#         # 2. 배치 임베딩 (이벤트 루프 블로킹 방지를 위해 스레드 풀로 위임)
#         query_vectors = await asyncio.to_thread(self.embeddings.embed_documents, q_texts)

#         # 3. 비동기 DB 작업 준비 (pool을 인자로 받아 각 태스크가 커넥션을 획득하도록 수정)
#         async def fetch_for_single_query(pool: asyncpg.Pool, text: str, vector: List[float]) -> List[dict]:
#             # 함수 내부에서 개별 커넥션을 꺼냄 (이 부분이 핵심 동시성 해결 포인트)
#             async with pool.acquire() as conn:
#                 clean_text = re.sub(r'[^\w\s]', '', text)
#                 tokens = [t for t in clean_text.split() if t]
#                 tsquery_str = " | ".join(tokens) if tokens else ""
                
#                 if not tsquery_str:
#                     return []

#                 q_vector_str = f"[{','.join(map(str, vector))}]"
#                 args = [tsquery_str, q_vector_str, top_k, bm25_weight, vector_weight]
#                 extra_where = ""
                
#                 # (보안 경고) 실제 운영시 key는 화이트리스트 검증 필요
#                 if filters:
#                     for key, value in filters.items():
#                         args.append(value)
#                         extra_where += f" AND sk.{key} = ${len(args)}"

#                 hybrid_sql = f"""
#                 WITH bm25_search AS (
#                     SELECT sc.id AS chunk_id, ts_rank_cd(sc.chunk_tsv, to_tsquery('simple', $1)) AS bm25_score
#                     FROM source_chunk sc
#                     JOIN map_source_chunk msc ON sc.id = msc.chunk_id
#                     JOIN source_knowledge sk ON msc.source_id = sk.id
#                     WHERE sc.chunk_tsv @@ to_tsquery('simple', $1)
#                     {extra_where}
#                     ORDER BY bm25_score DESC LIMIT 100
#                 ),
#                 vector_search AS (
#                     SELECT scv.chunk_id, 1 - (scv.chunk_vec <=> $2::vector(768)) AS vector_score
#                     FROM source_chunk_vec scv
#                     JOIN map_source_chunk msc ON scv.chunk_id = msc.chunk_id
#                     JOIN source_knowledge sk ON msc.source_id = sk.id
#                     WHERE 1=1
#                     {extra_where}
#                     ORDER BY scv.chunk_vec <=> $2::vector(768) LIMIT 100
#                 )
#                 SELECT 
#                     sc.id AS chunk_id, msc.source_id, sc.content, sc.chunk_index,
#                     COALESCE(b.bm25_score, 0) AS raw_bm25,
#                     COALESCE(v.vector_score, 0) AS raw_vector,
#                     (COALESCE(b.bm25_score, 0) * $4) + (COALESCE(v.vector_score, 0) * $5) AS final_score
#                 FROM source_chunk sc
#                 JOIN map_source_chunk msc ON sc.id = msc.chunk_id
#                 LEFT JOIN bm25_search b ON sc.id = b.chunk_id
#                 LEFT JOIN vector_search v ON sc.id = v.chunk_id
#                 WHERE b.chunk_id IS NOT NULL OR v.chunk_id IS NOT NULL
#                 ORDER BY final_score DESC LIMIT $3;
#                 """
#                 return await conn.fetch(hybrid_sql, *args)

#         # 4. 커넥션 풀을 열고 모든 쿼리에 대해 동시 실행 (Concurrent I/O)
#         all_results = []
        
#         # 다중 쿼리 동시 실행을 위해 풀의 최대 사이즈(max_size)를 확보
#         async with asyncpg.create_pool(dsn=self.dsn, min_size=3, max_size=10) as pool:
#             tasks = [
#                 fetch_for_single_query(pool, text, vector) 
#                 for text, vector in zip(q_texts, query_vectors)
#             ]
#             # DB I/O를 동시에 던지고 모두 끝날 때까지 대기
#             results_per_query = await asyncio.gather(*tasks, return_exceptions=True)
            
#             for res in results_per_query:
#                 if isinstance(res, Exception):
#                     logger.error(f"다중 쿼리 SQL 실행 실패: {res}")
#                 elif res:
#                     all_results.extend(res)

#         # 5. 결과 융합 (Result Fusion) 및 중복 제거
#         # 동일한 chunk_id가 여러 쿼리에서 검색되었을 경우, 가장 높은 final_score를 채택 (Max Score Fusion)
#         fused_chunks: Dict[int, ScoredChunk] = {}
        
#         for r in all_results:
#             cid = int(r["chunk_id"])
#             score = float(r["final_score"])
            
#             if cid not in fused_chunks or fused_chunks[cid].score < score:
#                 ch = SourceChunk(
#                     chunk_id=cid,
#                     source_id=int(r["source_id"]),
#                     source_name="postgres_hybrid",
#                     content=str(r["content"]),
#                     metadata={
#                         "chunk_index": int(r["chunk_index"]),
#                         "raw_bm25_score": float(r["raw_bm25"]),
#                         "raw_vector_score": float(r["raw_vector"])
#                     },
#                 )
#                 fused_chunks[cid] = ScoredChunk(chunk=ch, score=score)

#         # 6. 최종 점수순 정렬 후 top_k 개수만큼 잘라서 반환
#         sorted_out = sorted(fused_chunks.values(), key=lambda x: x.score, reverse=True)
#         return sorted_out[:top_k]
    
# if __name__ == "__main__": 
#     # Windows 환경 비동기 에러 방지용 설정
#     if sys.platform == 'win32':
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


import asyncio
import re
import sys
from typing import List, Sequence, Dict, Any
import asyncpg
from langchain_huggingface import HuggingFaceEmbeddings

from src.rag.core.types import SourceChunk, ScoredChunk
from src.rag.core.interfaces import RagRetriever
from src.common.logger import get_logger
import os

logger = get_logger(__name__)

class PostgresHybridRetriever(RagRetriever):
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.RRF_K = 60  # RRF 페널티 상수 (업계 표준 60)

        logger.info("Retriever 내부 임베딩 모델 로드 중...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="jhgan/ko-sroberta-multitask",
            model_kwargs={'device': 'cpu'}, 
            encode_kwargs={'normalize_embeddings': True}
        )

    async def forward(
        self,
        *,
        queries: Sequence[Any], 
        top_k: int = 40,
        bm25_weight: float = 0.5,  # RRF에서는 사용하지 않지만 인터페이스 호환성을 위해 유지
        vector_weight: float = 0.5,
        filters: Dict[str, Any] = None, 
    ) -> List[ScoredChunk]:
        
        if not queries:
            return []

        # 1. 채널별 쿼리 분류
        bm25_queries = []
        vector_queries = []
        
        for q in queries:
            text = q.content if hasattr(q, 'content') else str(q)
            # channels 속성이 없으면 기본적으로 하이브리드(둘 다)로 취급
            channels = q.channels if hasattr(q, 'channels') else {"bm25", "vector"}
            
            if "bm25" in channels:
                bm25_queries.append(text)
            if "vector" in channels:
                vector_queries.append(text)

        # 2. Vector 쿼리만 선택적 임베딩 연산
        query_vectors = []
        if vector_queries:
            query_vectors = await asyncio.to_thread(self.embeddings.embed_documents, vector_queries)

        # 3. 비동기 DB 작업 정의 (SQL 분리)
        async def fetch_bm25(pool: asyncpg.Pool, text: str) -> List[dict]:
            async with pool.acquire() as conn:
                clean_text = re.sub(r'[^\w\s]', '', text)
                tokens = [t for t in clean_text.split() if t]
                tsquery_str = " | ".join(tokens) if tokens else ""
                
                if not tsquery_str:
                    return []

                args = [tsquery_str, top_k]
                extra_where = ""
                if filters:
                    for key, value in filters.items():
                        args.append(value)
                        extra_where += f" AND sk.{key} = ${len(args)}"

                sql = f"""
                SELECT sc.id AS chunk_id, msc.source_id, sc.content, sc.chunk_index
                FROM source_chunk sc
                JOIN map_source_chunk msc ON sc.id = msc.chunk_id
                JOIN source_knowledge sk ON msc.source_id = sk.id
                WHERE sc.chunk_tsv @@ to_tsquery('simple', $1)
                  AND sc.is_active = TRUE   -- 추가됨: 활성화된 청크만
                  AND sk.is_active = TRUE   -- 추가됨: 활성화된 원본 문서만
                {extra_where}
                ORDER BY ts_rank_cd(sc.chunk_tsv, to_tsquery('simple', $1)) DESC
                LIMIT $2;
                """
                return await conn.fetch(sql, *args)

        async def fetch_vector(pool: asyncpg.Pool, vector: List[float]) -> List[dict]:
            async with pool.acquire() as conn:
                q_vector_str = f"[{','.join(map(str, vector))}]"
                args = [q_vector_str, top_k]
                extra_where = ""
                if filters:
                    for key, value in filters.items():
                        args.append(value)
                        extra_where += f" AND sk.{key} = ${len(args)}"

                sql = f"""
                SELECT sc.id AS chunk_id, msc.source_id, sc.content, sc.chunk_index
                FROM source_chunk sc
                JOIN source_chunk_vec scv ON sc.id = scv.chunk_id
                JOIN map_source_chunk msc ON sc.id = msc.chunk_id
                JOIN source_knowledge sk ON msc.source_id = sk.id
                WHERE sc.is_active = TRUE   -- 1=1 대신 활성화 조건 추가
                  AND sk.is_active = TRUE   -- 활성화된 원본 문서만
                {extra_where}
                ORDER BY scv.chunk_vec <=> $1::vector(768)
                LIMIT $2;
                """
                return await conn.fetch(sql, *args)

        # 4. 커넥션 풀을 열고 분리된 I/O를 병렬로 실행
        bm25_results_list = []
        vector_results_list = []
        
        async with asyncpg.create_pool(dsn=self.dsn, min_size=3, max_size=15) as pool:
            bm25_tasks = [fetch_bm25(pool, text) for text in bm25_queries]
            vector_tasks = [fetch_vector(pool, vec) for vec in query_vectors]
            
            # 두 채널의 태스크를 모두 모아 동시 실행
            all_tasks = bm25_tasks + vector_tasks
            if all_tasks:
                all_results = await asyncio.gather(*all_tasks, return_exceptions=True)
                
                # 결과 분류
                bm25_results_list = all_results[:len(bm25_tasks)]
                vector_results_list = all_results[len(bm25_tasks):]

        # 5. Application-Level RRF (Reciprocal Rank Fusion)
        fused_scores: Dict[int, float] = {}
        chunk_metadata: Dict[int, dict] = {}

        # BM25 결과 RRF 점수 누적
        for res in bm25_results_list:
            if isinstance(res, Exception):
                logger.error(f"BM25 쿼리 실행 실패: {res}")
                continue
            for rank, row in enumerate(res, start=1):
                cid = int(row["chunk_id"])
                fused_scores[cid] = fused_scores.get(cid, 0.0) + (1.0 / (self.RRF_K + rank))
                if cid not in chunk_metadata:
                    chunk_metadata[cid] = row

        # Vector 결과 RRF 점수 누적
        for res in vector_results_list:
            if isinstance(res, Exception):
                logger.error(f"Vector 쿼리 실행 실패: {res}")
                continue
            for rank, row in enumerate(res, start=1):
                cid = int(row["chunk_id"])
                fused_scores[cid] = fused_scores.get(cid, 0.0) + (1.0 / (self.RRF_K + rank))
                if cid not in chunk_metadata:
                    chunk_metadata[cid] = row

        # 6. 객체 조립 및 최종 정렬
        final_chunks = []
        for cid, score in fused_scores.items():
            row = chunk_metadata[cid]
            ch = SourceChunk(
                chunk_id=cid,
                source_id=int(row["source_id"]),
                source_name="postgres_hybrid",
                content=str(row["content"]),
                metadata={
                    "chunk_index": int(row["chunk_index"])
                },
            )
            final_chunks.append(ScoredChunk(chunk=ch, score=score))

        # RRF 점수 기준으로 내림차순 정렬 후 top_k 반환
        sorted_out = sorted(final_chunks, key=lambda x: x.score, reverse=True)
        return sorted_out[:top_k]
    
if __name__ == "__main__": 
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())