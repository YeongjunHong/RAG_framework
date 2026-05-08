import os
os.environ["TOKENIZERS_PARALLELISM"] = "false" # 토크나이저 병렬처리 경고 차단
import sys
# [CRITICAL] 시스템 환경변수 최우선 로드
from dotenv import load_dotenv
load_dotenv(".env.poc")

import asyncio
import time
import json
import logging
import warnings
import transformers
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.ERROR, force=True)

import re
import pandas as pd
import random
from datetime import datetime
from uuid import uuid4


# --- [로깅 노이즈 ] ---
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.ERROR, force=True)
for logger_name in [
    "httpcore", "httpx", "openai", "sentence_transformers", 
    "src.rag", "langfuse", "urllib3", "transformers", 
    "filelock", "fsspec", "datasets", "bert_score"
]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

transformers.logging.set_verbosity_error()


from datasets import load_dataset
from bert_score import score as bert_score

from src.rag.graph import build_graph
from src.rag.core.types import RagRequest, RagContext
from src.rag.plugins.openrouter_generator import OpenRouterGenerator

# 터미널 컬러 및 스타일
C_CYAN, C_GREEN, C_YELLOW, C_RED, C_PURPLE, C_RESET, C_BOLD = \
    "\033[96m", "\033[92m", "\033[93m", "\033[91m", "\033[95m", "\033[0m", "\033[1m"

# ------------------------------------------------------------------------
# 1. 평가 로직 (Judge & BERTScore)
# ------------------------------------------------------------------------

async def evaluate_with_judge(query: str, answer: str, context: str) -> dict:
    """LLM Judge를 활용한 Faithfulness 평가 (Groundedness & Hallucination)"""
    if not context.strip():
        return {"groundedness_score": 0, "has_hallucination": True}

    judge_gen = OpenRouterGenerator(default_model="openai/gpt-4o-mini")
    
    prompt = f"""당신은 RAG 시스템의 신뢰성을 검증하는 '매우 엄격하고 융통성 없는' 평가자(Judge)입니다.
아래 [Context]에 '명시적으로' 기재된 텍스트만을 바탕으로 [Answer]를 평가하세요. 

[Query]: {query}
[Context]: 
{context}
[Answer]: 
{answer}

평가 기준:
1. groundedness_score (0~100): [Answer]의 내용이 [Context]에서 직접적으로 도출 가능한가? 외부 지식이 섞였다면 0점.
2. has_hallucination (true/false): [Answer]가 [Context]에 없는 외부 지식이나 수치를 지어내어 덧붙였다면 무조건 true.

Output JSON format:
{{"groundedness_score": 0, "has_hallucination": true}}
"""
    try:
        res = await judge_gen.forward(prompt=prompt)
        json_match = re.search(r'\{.*\}', res, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception:
        pass
    
    return {"groundedness_score": 0, "has_hallucination": True}

def calculate_bertscore(candidate: str, reference: str) -> float:
    """BERTScore를 통한 정답과의 의미적 유사도(F1) 계산"""
    if not candidate or not reference:
        return 0.0
    
    # [수정됨] klue/roberta-base는 bert-score의 공식 딕셔너리에 없으므로,
    # 해당 모델의 히든 레이어 개수인 num_layers=12를 명시적으로 전달
    P, R, F1 = bert_score(
        [candidate], 
        [reference], 
        lang="ko", 
        model_type="klue/roberta-base", 
        num_layers=12,  # <--- 이 부분 추가
        verbose=False
    )
    return round(F1.item() * 100, 2)

# ------------------------------------------------------------------------
# 2. 벤치마크 파이프라인
# ------------------------------------------------------------------------

async def run_single_benchmark(app, vanilla_gen, query: str, ground_truth: str, index: int):
    print(f"\n{C_BOLD}{C_CYAN}======================================================================{C_RESET}")
    print(f"{C_BOLD}{C_PURPLE} [Test-{index:02d}]{C_RESET} {query}")
    print(f" {C_YELLOW}[정답지]{C_RESET} {ground_truth[:80]}...")
    print(f"{C_CYAN}----------------------------------------------------------------------{C_RESET}")
    
    # [A] Without RAG (Vanilla)
    print(f"{C_YELLOW} Vanilla LLM 생성 및 BERTScore 계산 중...{C_RESET}", end="\r")
    t0_vanilla = time.perf_counter()
    vanilla_ans = await vanilla_gen.forward(prompt=query)
    vanilla_lat = (time.perf_counter() - t0_vanilla) * 1000
    
    # [B] With RAG
    print(f"{C_YELLOW} RAG 파이프라인 실행 중...{' '*30}{C_RESET}", end="\r")
    req = RagRequest(trace_id=f"bench_{uuid4().hex[:6]}", user_query=query, stream_response=False)
    ctx = RagContext()
    
    t0_rag = time.perf_counter()
    state = await app.ainvoke({"request": req, "ctx": ctx})
    rag_lat = (time.perf_counter() - t0_rag) * 1000
    
    out_ctx = state["ctx"]
    rag_ans = out_ctx.raw_generation or "생성 실패"
    rag_context_str = "\n".join([f"[{c.chunk.source_name}] {c.chunk.content}" for c in out_ctx.retrieved])
    timings = out_ctx.timings_ms
    
    # [C] 3각 평가 수행 (병렬 처리)
    print(f"{C_YELLOW} LLM Judge 및 BERTScore 정량 평가 중...{' '*30}{C_RESET}", end="\r")
    
    eval_vanilla, eval_rag = await asyncio.gather(
        evaluate_with_judge(query, vanilla_ans, rag_context_str),
        evaluate_with_judge(query, rag_ans, rag_context_str)
    )
    
    # BERTScore는 CPU 연산이므로 백그라운드 스레드에서 실행
    vanilla_f1 = await asyncio.to_thread(calculate_bertscore, vanilla_ans, ground_truth)
    rag_f1 = await asyncio.to_thread(calculate_bertscore, rag_ans, ground_truth)
    
    # 터미널 시각화 출력
    sys.stdout.write("\033[K")
    print(f"{C_BOLD}[Without RAG]{C_RESET} {vanilla_ans[:100]}...\n")
    vanilla_hal_color = C_RED if eval_vanilla.get('has_hallucination') else C_GREEN
    print(f"  ↳ Hallucination: {vanilla_hal_color}{eval_vanilla.get('has_hallucination')}{C_RESET} | Groundedness: {eval_vanilla.get('groundedness_score')}점 | {C_BOLD}BERT_F1: {vanilla_f1}점{C_RESET} | Latency: {vanilla_lat:.0f}ms\n")

    print(f"{C_BOLD}[With RAG]{C_RESET} {rag_ans[:100]}...\n")
    rag_hal_color = C_RED if eval_rag.get('has_hallucination') else C_GREEN
    print(f"  ↳ Hallucination: {rag_hal_color}{eval_rag.get('has_hallucination')}{C_RESET} | Groundedness: {eval_rag.get('groundedness_score')}점 | {C_BOLD}{C_GREEN}BERT_F1: {rag_f1}점{C_RESET} | Latency: {rag_lat:.0f}ms")
    print(f"    (Retrieval: {timings.get('retrieval', 0):.0f}ms, Rerank: {timings.get('reranking', 0):.0f}ms, Gen: {timings.get('generator', 0):.0f}ms)")

    return {
        "Query": query,
        "Ground_Truth": ground_truth,
        "NoRAG_Answer": vanilla_ans,
        "NoRAG_Groundedness": eval_vanilla.get("groundedness_score"),
        "NoRAG_Hallucination": eval_vanilla.get("has_hallucination"),
        "NoRAG_BERT_F1": vanilla_f1,
        "NoRAG_Latency_ms": round(vanilla_lat, 2),
        "RAG_Answer": rag_ans,
        "RAG_Groundedness": eval_rag.get("groundedness_score"),
        "RAG_Hallucination": eval_rag.get("has_hallucination"),
        "RAG_BERT_F1": rag_f1,
        "RAG_Total_Latency_ms": round(rag_lat, 2),
        "RAG_Retrieval_ms": round(timings.get("retrieval", 0), 2),
        "RAG_Reranking_ms": round(timings.get("reranking", 0), 2),
        "RAG_Gen_ms": round(timings.get("generator", 0), 2),
        "Retrieved_Docs": len(out_ctx.retrieved)
    }

async def main():
    print(f"{C_BOLD}{C_GREEN} A/B Test Benchmark Framework (Ground Truth 기반) 가동...{C_RESET}")
    
    # 1. 캐시 초기화
    try:
        from src.rag.plugins.cache_manager import SemanticCacheManager
        temp_manager = SemanticCacheManager(host="localhost", port=6379)
        temp_manager.clear_cache()
        print(f"{C_YELLOW} [*] 평가 정합성을 위해 Redis Semantic Cache를 초기화했습니다.{C_RESET}")
    except Exception as e:
        print(f"{C_RED} [!] Cache 초기화 실패: {e}{C_RESET}")

    # 2. 허깅페이스 데이터셋 동적 로드 및 샘플링
    print(f"{C_CYAN} [*] 허깅페이스에서 BCCard-Finance-Kor-QnA 평가 데이터셋을 로드합니다...{C_RESET}")
    dataset = load_dataset("BCCard/BCCard-Finance-Kor-QnA", split="train")
    
    # 데모용으로 랜덤하게 5개 추출 (원하는 개수로 조절 가능)
    SAMPLE_SIZE = 5
    sampled_data = random.sample(list(dataset), SAMPLE_SIZE)
    
    app = build_graph()
    vanilla_gen = OpenRouterGenerator()
    results = []

    for idx, item in enumerate(sampled_data, 1):
        # 데이터셋 스키마(Alpaca vs 일반 QnA)에 맞춘 동적 키 추출
        query = item.get("question") or item.get("instruction") or "질문 없음"
        
        # input 필드가 존재하면 질문에 문맥(Context)으로 덧붙임
        if item.get("input"):
            query = f"{query}\n[조건]: {item['input']}"
            
        ground_truth = item.get("answer") or item.get("output") or "정답 없음"
        
        res = await run_single_benchmark(app, vanilla_gen, query, ground_truth, idx)
        results.append(res)
    
    print(f"\n{C_BOLD}{C_CYAN}======================================================================{C_RESET}")
    print(f"{C_BOLD}벤치마크 종료. 결과를 CSV로 추출합니다...{C_RESET}")
    
    os.makedirs("data", exist_ok=True)
    output_path = f"data/ab_test_report_gt_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    
    # 요약 통계 출력
    avg_norag_f1 = df["NoRAG_BERT_F1"].mean()
    avg_rag_f1 = df["RAG_BERT_F1"].mean()
    print(f"\n{C_BOLD}[요약 리포트]{C_RESET}")
    print(f" - 평균 BERTScore F1 (No-RAG) : {avg_norag_f1:.2f}점")
    print(f" - 평균 BERTScore F1 (RAG)    : {C_GREEN}{avg_rag_f1:.2f}점{C_RESET}")
    print(f"\n{C_GREEN}성공적으로 저장되었습니다: {C_BOLD}{output_path}{C_RESET}")

if __name__ == "__main__":
    asyncio.run(main())