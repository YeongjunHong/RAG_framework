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