import sys
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings

# 1. 프로젝트 경로 세팅
current_file_path = Path(__file__).resolve()
project_root = current_file_path.parent
sys.path.append(str(project_root))

from src.rag.plugins.postgres_retriever import PostgresHybridRetriever

# 2. 환경 변수 로드
env_path = project_root / "settings" / ".env.poc"
load_dotenv(dotenv_path=env_path)

PG_HOST = os.getenv("PG1_HOST")
PG_PORT = os.getenv("PG1_PORT")
PG_DB = os.getenv("PG1_DATABASE")
PG_USER = os.getenv("PG1_USERNAME")
PG_PASS = os.getenv("PG1_PASSWORD")

DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# 3. 임베딩 모델 세팅 (데이터를 넣을 때와 동일한 모델 사용 필수)
EMBEDDING_MODEL_NAME = "jhgan/ko-sroberta-multitask"
print("임베딩 모델 로드 중...")
embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL_NAME,
    model_kwargs={'device': 'cpu'}, 
    encode_kwargs={'normalize_embeddings': True}
)

class DummyQuery:
    """Retriever가 기대하는 queries[0].content 포맷을 맞추기 위한 더미 클래스"""
    def __init__(self, text):
        self.content = text

async def main():
    print("\n=== RAG 하이브리드 검색 테스트 시작 ===")
    
    # 4. 검색기 초기화
    retriever = PostgresHybridRetriever(dsn=DATABASE_URL)
    
    # 5. 테스트할 검색어 설정
    test_query_text = "청년도약계좌나 청년주택드림청약통장 같은 청년 지원 금융 상품의 가입 조건이나 납입 관련 혜택이 어떻게 되나요?"
    print(f"\n[질문]: {test_query_text}")
    
    # 6. 질문을 768차원 벡터로 변환
    print("질문 벡터 변환 중...")
    query_vector = embeddings.embed_query(test_query_text)
    
    # 7. 하이브리드 검색 실행
    print("DB 하이브리드 검색 중 (BM25 + Vector)...\n")
    results = await retriever.forward(
        queries=[DummyQuery(test_query_text)],
        query_vector=query_vector,
        top_k=5,            # 상위 5개 가져오기
        bm25_weight=0.3,    # 키워드 매칭 가중치
        vector_weight=0.7   # 의미 매칭 가중치
    )
    
    # 8. 결과 출력
    if not results:
        print("검색 결과가 없습니다.")
        return

    for i, res in enumerate(results):
        meta = res.chunk.metadata
        print(f"🥇 Rank {i + 1} (Final Score: {res.score:.4f})")
        print(f"   - [Vector 점수]: {meta.get('raw_vector_score', 0):.4f} (가중치 70% 반영)")
        print(f"   - [BM25 점수]: {meta.get('raw_bm25_score', 0):.4f} (가중치 30% 반영)")
        print(f"   - [원본 텍스트]:\n{res.chunk.content}")
        print("-" * 70)

if __name__ == "__main__":
    # Windows 환경 비동기 에러 방지용 설정 (맥/리눅스는 영향 없음)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())