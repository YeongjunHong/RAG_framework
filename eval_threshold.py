import asyncio
import numpy as np
from typing import List, Tuple

# DB 커넥션 설정을 위한 임포트
from src.common.utils import get_pg_url
from settings.config import cfg

from src.rag.core.types import ScoredChunk
from src.rag.plugins.postgres_retriever import PostgresHybridRetriever
from src.rag.plugins.local_reranker import LocalCrossEncoderReranker

# [평가용 샘플 데이터셋] 
# 실제 서비스 수준의 평가를 원한다면 이 리스트를 20~30개 이상으로 늘리는 것을 권장.
EVAL_DATASET: List[Tuple[str, List[int]]] = [
    ("BC카드 고객센터 전화번호 알려줘", [68446, 68904]),
    ("신용카드 리볼빙의 단점이 뭐야?", [85762]),
    ("DSR 규제 강화가 대출 한도에 미치는 영향", [10293, 10294]),
]

async def evaluate_thresholds():
    print("평가 파이프라인 초기화 중...")
    
    # DB 커넥션 문자열 파싱 (psycopg 부분 제거)
    db_url = get_pg_url(cfg.PG1_DATABASE, cfg.PG1_HOST, cfg.PG1_PORT, cfg.PG1_USERNAME, cfg.PG1_PASSWORD)
    async_db_url = db_url.replace("+psycopg", "")
    
    # 의존성 주입 규격에 맞춰 Retriever 및 Reranker 초기화
    retriever = PostgresHybridRetriever(dsn=async_db_url)
    reranker = LocalCrossEncoderReranker()
    
    # 평가할 Threshold 후보군 (0.05부터 0.95까지 0.05 간격)
    thresholds = np.arange(0.05, 1.0, 0.05)
    
    # Threshold별 결과를 저장할 딕셔너리
    results = {th: {"tp": 0, "fp": 0, "fn": 0} for th in thresholds}

    print(f"총 {len(EVAL_DATASET)}개의 쿼리에 대해 평가를 시작합니다...\n")

    for query, true_source_ids in EVAL_DATASET:
        # 1. Retrieval (Top-40): forward 인터페이스 사용 및 다중 쿼리 리스트 형태로 전달
        retrieved_chunks = await retriever.forward(queries=[query], top_k=40)
        
        # 2. Reranking & 정규화 (Sigmoid 적용된 확률 점수)
        reranked_chunks = await reranker.forward(query=query, candidates=retrieved_chunks, top_k=20)
        
        # 3. 각 Threshold 지표별로 성능 측정
        for th in thresholds:
            # 설정된 Threshold 이상인 청크만 '유지(Kept)'로 간주
            kept_chunks = [c for c in reranked_chunks if c.score >= th]
            kept_source_ids = set(c.chunk.source_id for c in kept_chunks)
            target_ids = set(true_source_ids)
            
            # True Positive (정답 문서를 제대로 남김)
            tp = len(kept_source_ids.intersection(target_ids))
            # False Positive (쓸데없는 문서를 남김)
            fp = len(kept_source_ids - target_ids)
            # False Negative (정답 문서인데 버려짐)
            fn = len(target_ids - kept_source_ids)
            
            results[th]["tp"] += tp
            results[th]["fp"] += fp
            results[th]["fn"] += fn

    # 로거에 먹히지 않도록 print 함수로 명시적 출력
    print("\n=== Threshold Evaluation Report ===")
    print(f"{'Threshold':<10} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10}")
    print("-" * 50)
    
    best_th = 0.0
    best_f1 = 0.0
    
    for th in thresholds:
        tp = results[th]["tp"]
        fp = results[th]["fp"]
        fn = results[th]["fn"]
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        print(f"{th:.2f}       | {precision:.4f}     | {recall:.4f}     | {f1:.4f}")
        
        # F1 스코어가 가장 높은 Threshold 탐색
        if f1 > best_f1:
            best_f1 = f1
            best_th = th

    print("-" * 50)
    print(f"최적의 Threshold (min_score): {best_th:.2f} (F1: {best_f1:.4f})\n")

if __name__ == "__main__":
    asyncio.run(evaluate_thresholds())