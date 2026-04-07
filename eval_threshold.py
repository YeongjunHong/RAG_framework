# import asyncio
# import numpy as np
# from typing import List, Tuple

# # DB 커넥션 설정을 위한 임포트
# from src.common.utils import get_pg_url
# from settings.config import cfg

# from src.rag.core.types import ScoredChunk
# from src.rag.plugins.postgres_retriever import PostgresHybridRetriever
# from src.rag.plugins.local_reranker import LocalCrossEncoderReranker

# # [평가용 샘플 데이터셋] 
# # 실제 서비스 수준의 평가를 원한다면 이 리스트를 20~30개 이상으로 늘리는 것을 권장.
# EVAL_DATASET: List[Tuple[str, List[int]]] = [
#     ("BC카드 고객센터 전화번호 알려줘", [68446, 68904]),
#     ("신용카드 리볼빙의 단점이 뭐야?", [85762]),
#     ("DSR 규제 강화가 대출 한도에 미치는 영향", [10293, 10294]),
# ]

# async def evaluate_thresholds():
#     print("평가 파이프라인 초기화 중...")
    
#     # DB 커넥션 문자열 파싱 (psycopg 부분 제거)
#     db_url = get_pg_url(cfg.PG1_DATABASE, cfg.PG1_HOST, cfg.PG1_PORT, cfg.PG1_USERNAME, cfg.PG1_PASSWORD)
#     async_db_url = db_url.replace("+psycopg", "")
    
#     # 의존성 주입 규격에 맞춰 Retriever 및 Reranker 초기화
#     retriever = PostgresHybridRetriever(dsn=async_db_url)
#     reranker = LocalCrossEncoderReranker()
    
#     # 평가할 Threshold 후보군 (0.05부터 0.95까지 0.05 간격)
#     thresholds = np.arange(0.05, 1.0, 0.05)
    
#     # Threshold별 결과를 저장할 딕셔너리
#     results = {th: {"tp": 0, "fp": 0, "fn": 0} for th in thresholds}

#     print(f"총 {len(EVAL_DATASET)}개의 쿼리에 대해 평가를 시작합니다...\n")

#     for query, true_source_ids in EVAL_DATASET:
#         # 1. Retrieval (Top-40): forward 인터페이스 사용 및 다중 쿼리 리스트 형태로 전달
#         retrieved_chunks = await retriever.forward(queries=[query], top_k=40)
        
#         # 2. Reranking & 정규화 (Sigmoid 적용된 확률 점수)
#         reranked_chunks = await reranker.forward(query=query, candidates=retrieved_chunks, top_k=20)
        
#         # 3. 각 Threshold 지표별로 성능 측정
#         for th in thresholds:
#             # 설정된 Threshold 이상인 청크만 '유지(Kept)'로 간주
#             kept_chunks = [c for c in reranked_chunks if c.score >= th]
#             kept_source_ids = set(c.chunk.source_id for c in kept_chunks)
#             target_ids = set(true_source_ids)
            
#             # True Positive (정답 문서를 제대로 남김)
#             tp = len(kept_source_ids.intersection(target_ids))
#             # False Positive (쓸데없는 문서를 남김)
#             fp = len(kept_source_ids - target_ids)
#             # False Negative (정답 문서인데 버려짐)
#             fn = len(target_ids - kept_source_ids)
            
#             results[th]["tp"] += tp
#             results[th]["fp"] += fp
#             results[th]["fn"] += fn

#     # 로거에 먹히지 않도록 print 함수로 명시적 출력
#     print("\n=== Threshold Evaluation Report ===")
#     print(f"{'Threshold':<10} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10}")
#     print("-" * 50)
    
#     best_th = 0.0
#     best_f1 = 0.0
    
#     for th in thresholds:
#         tp = results[th]["tp"]
#         fp = results[th]["fp"]
#         fn = results[th]["fn"]
        
#         precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
#         recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
#         f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
#         print(f"{th:.2f}       | {precision:.4f}     | {recall:.4f}     | {f1:.4f}")
        
#         # F1 스코어가 가장 높은 Threshold 탐색
#         if f1 > best_f1:
#             best_f1 = f1
#             best_th = th

#     print("-" * 50)
#     print(f"최적의 Threshold (min_score): {best_th:.2f} (F1: {best_f1:.4f})\n")

# if __name__ == "__main__":
#     asyncio.run(evaluate_thresholds())

# import asyncio
# import json
# import numpy as np
# from pathlib import Path
# from typing import List, Dict

# from src.common.utils import get_pg_url
# from settings.config import cfg
# from src.rag.plugins.postgres_retriever import PostgresHybridRetriever
# from src.rag.plugins.local_reranker import LocalCrossEncoderReranker

# # 인텐트가 포함된 형태로 데이터셋 구조 변경
# EVAL_DATASET = [
#     # 1. simple_search: 핀포인트 정답 (Rank 1)
#     {"intent": "simple_search", "query": "BC카드 고객센터 전화번호 알려줘", "target_ids": [68713]},
    
#     # 2. search: DB에 실제 존재하는 내용으로 쿼리 수정 (리볼빙 -> 하이브리드 카드)
#     {"intent": "search", "query": "하이브리드 카드의 단점이 뭐야?", "target_ids": [68260]},
    
#     # 3. search: 복합 문맥 (Rank 1, Rank 3)
#     {"intent": "search", "query": "DSR 규제 강화가 대출 한도에 미치는 영향", "target_ids": [69942, 69906]},
    
#     # 4. authoring: 다중 문서 조합 필수 (Rank 1, 2, 3)
#     {"intent": "authoring", "query": "제공된 문서들을 바탕으로 신입사원을 위한 금융 보안 가이드 문서를 작성해줘.", "target_ids": [69792, 69771, 69794]}
# ]

# ARTIFACT_PATH = Path("settings/dynamic_thresholds.json")

# async def evaluate_thresholds():
#     print("평가 파이프라인 초기화 중...")
#     db_url = get_pg_url(cfg.PG1_DATABASE, cfg.PG1_HOST, cfg.PG1_PORT, cfg.PG1_USERNAME, cfg.PG1_PASSWORD)
#     async_db_url = db_url.replace("+psycopg", "")
    
#     retriever = PostgresHybridRetriever(dsn=async_db_url)
#     reranker = LocalCrossEncoderReranker()
    
#     thresholds = np.arange(0.05, 1.0, 0.05)
    
#     # 인텐트별로 데이터를 분리
#     datasets_by_intent: Dict[str, List[dict]] = {}
#     for item in EVAL_DATASET:
#         datasets_by_intent.setdefault(item["intent"], []).append(item)

#     optimal_thresholds = {}

#     print(f"총 {len(EVAL_DATASET)}개의 쿼리에 대해 인텐트별 평가를 시작합니다...\n")

#     for intent, items in datasets_by_intent.items():
#         print(f"--- [Intent: {intent}] 평가 중 ---")
#         results = {th: {"tp": 0, "fp": 0, "fn": 0} for th in thresholds}
        
#         for item in items:
#             query = item["query"]
#             target_ids = set(item["target_ids"])
            
#             retrieved_chunks = await retriever.forward(queries=[query], top_k=40)
#             reranked_chunks = await reranker.forward(query=query, candidates=retrieved_chunks, top_k=20)
            
#             for th in thresholds:
#                 kept_chunks = [c for c in reranked_chunks if c.score >= th]
#                 if not kept_chunks and reranked_chunks:
#                     kept_chunks = [reranked_chunks[0]] # Top-1 Rescue
                    
#                 kept_source_ids = set(c.chunk.source_id for c in kept_chunks)
                
#                 results[th]["tp"] += len(kept_source_ids.intersection(target_ids))
#                 results[th]["fp"] += len(kept_source_ids - target_ids)
#                 results[th]["fn"] += len(target_ids - kept_source_ids)

#         best_th, best_f1 = 0.0, 0.0
#         for th in thresholds:
#             tp, fp, fn = results[th]["tp"], results[th]["fp"], results[th]["fn"]
#             precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
#             recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
#             f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            
#             if f1 > best_f1:
#                 best_f1 = f1
#                 best_th = th
                
#         optimal_thresholds[intent] = round(best_th, 2)
#         print(f"최적 Threshold: {best_th:.2f} (F1: {best_f1:.4f})\n")

#     # 기본값 추가 및 JSON 아티팩트로 저장
#     optimal_thresholds["default"] = 0.50
#     ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
#     with open(ARTIFACT_PATH, "w") as f:
#         json.dump(optimal_thresholds, f, indent=4)
        
#     print(f"동적 임계값 아티팩트가 성공적으로 저장되었습니다: {ARTIFACT_PATH}")

# if __name__ == "__main__":
#     asyncio.run(evaluate_thresholds())

import asyncio
import json
import numpy as np
from pathlib import Path
from typing import List, Dict

from src.common.utils import get_pg_url
from settings.config import cfg
from src.rag.plugins.postgres_retriever import PostgresHybridRetriever
from src.rag.plugins.local_reranker import LocalCrossEncoderReranker
from src.rag.stages.filtering import IntentFilterRule, FilteringConfig

# 업데이트된 Ground Truth 데이터셋
EVAL_DATASET = [
    {"intent": "simple_search", "query": "BC카드 고객센터 전화번호 알려줘", "target_ids": [68713]},
    {"intent": "search", "query": "하이브리드 카드의 단점이 뭐야?", "target_ids": [68260]},
    {"intent": "search", "query": "DSR 규제 강화가 대출 한도에 미치는 영향", "target_ids": [69942, 69906]},
    {"intent": "authoring", "query": "제공된 문서들을 바탕으로 신입사원을 위한 금융 보안 가이드 문서를 작성해줘.", "target_ids": [69792, 69771, 69794]}
]

ARTIFACT_PATH = Path("settings/dynamic_thresholds.json")

def simulate_hybrid_filter(chunks, floor_score: float, rule: IntentFilterRule):
    """서빙 파이프라인의 하이브리드 필터링 로직을 동일하게 시뮬레이션"""
    step1 = [c for c in chunks if c.score >= floor_score]
    if not step1:
        return []
    
    max_score = step1[0].score
    step2 = [c for c in step1 if c.score >= (max_score - rule.relative_margin)]
    
    if len(step2) < rule.min_k:
        return step1[:rule.min_k]
    return step2[:rule.max_k]

async def evaluate_thresholds():
    print("하이브리드 필터링 평가 파이프라인 초기화 중...")
    db_url = get_pg_url(cfg.PG1_DATABASE, cfg.PG1_HOST, cfg.PG1_PORT, cfg.PG1_USERNAME, cfg.PG1_PASSWORD)
    async_db_url = db_url.replace("+psycopg", "")
    
    retriever = PostgresHybridRetriever(dsn=async_db_url)
    reranker = LocalCrossEncoderReranker()
    filter_config = FilteringConfig()
    
    # 탐색할 하한선(Floor) 범위
    floor_candidates = np.arange(0.10, 0.85, 0.05)
    
    datasets_by_intent: Dict[str, List[dict]] = {}
    for item in EVAL_DATASET:
        datasets_by_intent.setdefault(item["intent"], []).append(item)

    optimal_floors = {}

    for intent, items in datasets_by_intent.items():
        print(f"\n--- [Intent: {intent}] 최적 하한선(Floor) 탐색 중 ---")
        rule = filter_config.rules.get(intent, filter_config.rules["default"])
        
        results = {fl: {"tp": 0, "fp": 0, "fn": 0} for fl in floor_candidates}
        
        for item in items:
            query = item["query"]
            target_ids = set(item["target_ids"])
            
            retrieved_chunks = await retriever.forward(queries=[query], top_k=40)
            reranked_chunks = await reranker.forward(query=query, candidates=retrieved_chunks, top_k=20)
            
            for fl in floor_candidates:
                # 하이브리드 필터 적용 시뮬레이션
                kept_chunks = simulate_hybrid_filter(reranked_chunks, fl, rule)
                kept_source_ids = set(c.chunk.source_id for c in kept_chunks)
                
                results[fl]["tp"] += len(kept_source_ids.intersection(target_ids))
                results[fl]["fp"] += len(kept_source_ids - target_ids)
                results[fl]["fn"] += len(target_ids - kept_source_ids)

        best_fl, best_f1 = 0.0, 0.0
        for fl in floor_candidates:
            tp, fp, fn = results[fl]["tp"], results[fl]["fp"], results[fl]["fn"]
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            
            if f1 >= best_f1:  # 동일 F1이면 가급적 높은 하한선 선택
                best_f1 = f1
                best_fl = fl
                
        optimal_floors[intent] = round(best_fl, 2)
        print(f"적용 룰: Margin {rule.relative_margin}, Min K {rule.min_k}")
        print(f"최적 Floor: {best_fl:.2f} (F1: {best_f1:.4f})")

    optimal_floors["default"] = 0.30
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACT_PATH, "w") as f:
        json.dump(optimal_floors, f, indent=4)
        
    print(f"\n하이브리드 동적 임계값 아티팩트 저장 완료: {ARTIFACT_PATH}")

if __name__ == "__main__":
    asyncio.run(evaluate_thresholds())