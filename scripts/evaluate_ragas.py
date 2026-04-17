import asyncio
import json
import warnings
import logging
from dotenv import load_dotenv

# --- [RAGAS 텔레메트리 원천 차단 (가장 먼저 실행되어야 함)] ---
os.environ["RAGAS_DO_NOT_TRACK"] = "true"

# 환경변수 로드 (.env.poc에 OPENROUTER_API_KEY가 있어야 함)
load_dotenv(".env.poc")

# --- [로깅 노이즈 완벽 차단] ---
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.ERROR, force=True)
# 외부 통신 및 분석 과정의 지저분한 DEBUG/INFO 로그 강제 차단
for logger_name in [
    "httpcore", "httpx", "sentence_transformers", "urllib3", 
    "openai", "ragas", "ragas._analytics"
]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings

from src.rag.graph import build_graph
from src.rag.core.types import RagRequest, RagContext
from src.rag.plugins.cache_manager import SemanticCacheManager

# 1. Ground Truth (정답) 데이터셋
with open("data/golden_eval_dataset.json", "r", encoding="utf-8") as f:
    EVAL_DATASET = json.load(f)

async def run_evaluation():
    print("RAG 파이프라인 가동 및 평가 데이터 수집 중...\n")
    app = build_graph()

    data_samples = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": []
    }

    # 2. 파이프라인을 통과시켜 실제 답변과 검색된 컨텍스트 수집
    for item in EVAL_DATASET:
        question = item["question"]
        print(f"[질의 실행] {question}")
        
        req = RagRequest(trace_id="ragas_eval", user_query=question, stream_response=False)
        ctx = RagContext()
        
        # 순수 검색/생성 능력 평가를 위해 캐시 강제 초기화
        SemanticCacheManager(host="localhost", port=6379).clear_cache()
        
        final_state = await app.ainvoke({"request": req, "ctx": ctx})
        final_ctx = final_state["ctx"]
        
        answer = getattr(final_ctx, "raw_generation", "답변 생성 실패")
        
        # 필터링을 통과한 문서들의 내용을 리스트로 추출
        filtered_chunks = getattr(final_ctx, "filtered", [])
        contexts = [c.chunk.content for c in filtered_chunks]
        
        data_samples["question"].append(question)
        data_samples["answer"].append(answer)
        data_samples["contexts"].append(contexts)
        data_samples["ground_truth"].append(item["ground_truth"])

    dataset = Dataset.from_dict(data_samples)

    print("\n데이터 수집 완료. RAGAS 판관(Judge) LLM을 통한 정량 평가를 시작합니다...")
    
    # 3. RAGAS 평가자 (Evaluator) 모델 초기화
    
    # [OpenRouter 연동] Base URL을 OpenRouter로 덮어쓰기
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY가 환경 변수에 설정되지 않았습니다.")

    evaluator_llm = ChatOpenAI(
        api_key=openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini", # OpenRouter 상의 모델 ID
        temperature=0.0
    )

    # [로컬 임베딩 연동] 기존 RAG에 쓰던 모델 재사용
    print("평가용 로컬 임베딩 모델 로드 중...")
    evaluator_embeddings = HuggingFaceEmbeddings(
        model_name="jhgan/ko-sroberta-multitask"
    )

    metrics = [
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ]

    # 4. RAGAS 실행
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
    )

    print("\n=== RAGAS 정량 평가 결과 ===")
    print(result)
    
    # 5. 상세 결과 저장
    result_dict = result.to_pandas().to_dict(orient="records")
    with open("scripts/ragas_report.json", "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=4)
    print("\n평가 상세 리포트가 scripts/ragas_report.json에 저장되었습니다.")

if __name__ == "__main__":
    asyncio.run(run_evaluation())