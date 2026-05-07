
import asyncio
import re
from typing import List, Sequence, Dict, Any
import asyncpg
from langchain_huggingface import HuggingFaceEmbeddings

from src.rag.core.types import SourceChunk, ScoredChunk
from src.rag.core.interfaces import RagRetriever
from src.common.logger import get_logger

logger = get_logger(__name__)

class PostgresHybridRetriever(RagRetriever):
    # [MODIFIED] pool과 dsn을 모두 받을 수 있도록 인터페이스 유연화
    def __init__(self, pool: asyncpg.Pool = None, dsn: str = None):
        self.pool = pool
        self.dsn = dsn
        self.RRF_K = 60

        logger.info("Retriever 내부 임베딩 모델 로드 중...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="jhgan/ko-sroberta-multitask",
            model_kwargs={'device': 'cpu'}, 
            encode_kwargs={'normalize_embeddings': True}
        )

        self.allowed_filter_keys = {"category", "doc_type", "author"}

    async def forward(
        self,
        *,
        queries: Sequence[Any], 
        top_k: int = 40,
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
        filters: Dict[str, Any] = None, 
    ) -> List[ScoredChunk]:
        
        # [NEW] 지연 초기화 (Lazy Initialization)
        # 런타임에 첫 쿼리가 들어왔을 때 pool이 없다면 한 번만 생성하여 클래스 변수에 저장
        if self.pool is None:
            if not self.dsn:
                raise ValueError("[Retriever] DB 연결을 위한 pool이나 dsn이 제공되지 않았습니다.")
            logger.info("[Retriever] Asyncpg Connection Pool 지연 생성 중...")
            self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=3, max_size=15)

        if not queries:
            return []

        bm25_queries = []
        vector_queries = []
        
        for q in queries:
            text = q.content if hasattr(q, 'content') else str(q)
            channels = q.channels if hasattr(q, 'channels') else {"bm25", "vector"}
            
            if "bm25" in channels:
                bm25_queries.append(text)
            if "vector" in channels:
                vector_queries.append(text)

        query_vectors = []
        if vector_queries:
            query_vectors = await asyncio.to_thread(self.embeddings.embed_documents, vector_queries)

        def build_filter_clause(args_list: list) -> str:
            if not filters:
                return ""
            extra_where = ""
            for key, value in filters.items():
                if key in self.allowed_filter_keys:
                    args_list.append(value)
                    extra_where += f" AND sk.{key} = ${len(args_list)}"
                else:
                    logger.warning(f"허용되지 않은 필터 키가 무시되었습니다: {key}")
            return extra_where

        async def fetch_bm25(text: str) -> List[dict]:
            async with self.pool.acquire() as conn:
                clean_text = re.sub(r'[^\w\s]', '', text)
                tokens = [t for t in clean_text.split() if t]
                tsquery_str = " | ".join(tokens) if tokens else ""
                
                if not tsquery_str:
                    return []

                args = [tsquery_str, top_k]
                extra_where = build_filter_clause(args)

                sql = f"""
                SELECT sc.id AS chunk_id, msc.source_id, sc.content, sc.chunk_index
                FROM source_chunk sc
                JOIN map_source_chunk msc ON sc.id = msc.chunk_id
                JOIN source_knowledge sk ON msc.source_id = sk.id
                WHERE sc.chunk_tsv @@ to_tsquery('simple', $1)
                  AND sc.is_active = TRUE
                  AND sk.is_active = TRUE
                {extra_where}
                ORDER BY ts_rank_cd(sc.chunk_tsv, to_tsquery('simple', $1)) DESC
                LIMIT $2;
                """
                return await conn.fetch(sql, *args)

        async def fetch_vector(vector: List[float]) -> List[dict]:
            async with self.pool.acquire() as conn:
                q_vector_str = f"[{','.join(map(str, vector))}]"
                args = [q_vector_str, top_k]
                extra_where = build_filter_clause(args)

                sql = f"""
                SELECT sc.id AS chunk_id, msc.source_id, sc.content, sc.chunk_index
                FROM source_chunk sc
                JOIN source_chunk_vec scv ON sc.id = scv.chunk_id
                JOIN map_source_chunk msc ON sc.id = msc.chunk_id
                JOIN source_knowledge sk ON msc.source_id = sk.id
                WHERE sc.is_active = TRUE
                  AND sk.is_active = TRUE
                {extra_where}
                ORDER BY scv.chunk_vec <=> $1::vector(768)
                LIMIT $2;
                """
                return await conn.fetch(sql, *args)

        bm25_tasks = [fetch_bm25(text) for text in bm25_queries]
        vector_tasks = [fetch_vector(vec) for vec in query_vectors]
        
        all_tasks = bm25_tasks + vector_tasks
        if not all_tasks:
            return []

        all_results = await asyncio.gather(*all_tasks, return_exceptions=True)
        
        bm25_results_list = all_results[:len(bm25_tasks)]
        vector_results_list = all_results[len(bm25_tasks):]

        fused_scores: Dict[int, float] = {}
        chunk_metadata: Dict[int, dict] = {}

        for res in bm25_results_list + vector_results_list:
            if isinstance(res, Exception):
                logger.error(f"쿼리 실행 실패: {res}")
                continue
            for rank, row in enumerate(res, start=1):
                cid = int(row["chunk_id"])
                fused_scores[cid] = fused_scores.get(cid, 0.0) + (1.0 / (self.RRF_K + rank))
                if cid not in chunk_metadata:
                    chunk_metadata[cid] = row

        final_chunks = []
        for cid, score in fused_scores.items():
            row = chunk_metadata[cid]
            ch = SourceChunk(
                chunk_id=cid,
                source_id=int(row["source_id"]),
                source_name="postgres_hybrid",
                content=str(row["content"]),
                metadata={"chunk_index": int(row["chunk_index"])},
            )
            final_chunks.append(ScoredChunk(chunk=ch, score=score))

        sorted_out = sorted(final_chunks, key=lambda x: x.score, reverse=True)
        return sorted_out[:top_k]