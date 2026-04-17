import asyncio
from src.common.utils import get_pg_url
from settings.config import cfg
from src.rag.plugins.postgres_retriever import PostgresHybridRetriever

# 평가에 사용할 쿼리 목록
QUERIES = [
    "BC카드 고객센터 전화번호 알려줘",
    "신용카드 리볼빙의 단점이 뭐야?",
    "DSR 규제 강화가 대출 한도에 미치는 영향",
    "제공된 문서들을 바탕으로 신입사원을 위한 금융 보안 가이드 문서를 작성해줘."
]

async def find_ground_truth():
    print("DB에서 쿼리별 최상위 청크를 탐색합니다...\n")
    db_url = get_pg_url(cfg.PG1_DATABASE, cfg.PG1_HOST, cfg.PG1_PORT, cfg.PG1_USERNAME, cfg.PG1_PASSWORD)
    async_db_url = db_url.replace("+psycopg", "")
    
    retriever = PostgresHybridRetriever(dsn=async_db_url)

    for query in QUERIES:
        print(f"{'='*60}")
        print(f"[Query] {query}")
        print(f"{'='*60}")
        
        # 각 쿼리당 상위 5개의 검색 결과를 가져옴
        results = await retriever.forward(queries=[query], top_k=5)
        
        for i, doc in enumerate(results):
            c = doc.chunk
            # 현재 eval_threshold.py는 source_id를 기준으로 정답을 체크하고 있음
            print(f"Rank {i+1} | Source ID: {c.source_id} | Chunk ID: {c.chunk_id} | Score: {doc.score:.4f}")
            print(f"Content: {c.content.strip()[:100]}...\n")

if __name__ == "__main__":
    asyncio.run(find_ground_truth())