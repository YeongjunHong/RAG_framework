import os
import json
import random
import argparse
import logging
import warnings
from pathlib import Path
from datasets import load_dataset
from src.common.logger import get_logger

# --- [로깅 노이즈 완벽 차단] ---
warnings.filterwarnings("ignore")
# 기본 로깅 레벨을 ERROR로 강제 고정
logging.basicConfig(level=logging.ERROR, force=True)
# 외부 통신 및 데이터셋 로드 과정의 지저분한 DEBUG/INFO 로그 강제 차단
for logger_name in ["httpcore", "httpx", "datasets", "urllib3", "fsspec", "filelock"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

logger = get_logger(__name__)

# 저장될 골든 데이터셋 경로
OUTPUT_PATH = Path("data/golden_eval_dataset.json")

# 사용할 HuggingFace 데이터셋 정의
DATASETS_CONFIG = [
    {"path": "allganize/RAG-Evaluation-Dataset-KO", "split": "test", "q_col": "question", "a_col": "target_answer"},
    {"path": "BCCard/BCCard-Finance-Kor-QnA", "split": "train", "q_col": "question", "a_col": "answer"},
    {"path": "kifai/KoInFoBench", "split": "train", "q_col": "instruction", "a_col": "output"}
]

def classify_intent(question: str) -> str:
    """질문의 패턴과 길이를 분석하여 가상의 Intent를 부여하는 휴리스틱 함수"""
    question = question.strip()
    
    authoring_keywords = ["작성해줘", "비교해", "설명해", "요약해", "차이점", "보고서"]
    if any(kw in question for kw in authoring_keywords) or len(question) > 50:
        return "authoring"
        
    simple_keywords = ["언제", "얼마", "누구", "어디", "번호", "주소", "금액"]
    if any(kw in question for kw in simple_keywords) or len(question) < 20:
        return "simple_search"
        
    return "search"

def build_golden_dataset(samples_per_intent=5):
    print(f" HuggingFace 데이터셋 다운로드 및 파싱 시작 (인텐트당 {samples_per_intent}개)...")
    
    raw_pool = []
    
    for config in DATASETS_CONFIG:
        try:
            print(f" - Loading {config['path']}...")
            ds = load_dataset(config["path"], split=config["split"])
            
            for item in ds:
                q = item.get(config["q_col"], "")
                a = item.get(config["a_col"], "")
                
                if q and a and len(q.strip()) > 5:
                    raw_pool.append({
                        "question": q.strip(),
                        "ground_truth": a.strip(),
                        "source": config["path"]
                    })
        except Exception as e:
            logger.error(f"데이터셋 로드 실패 ({config['path']}): {e}")

    print(f"\n총 {len(raw_pool)}개의 유효한 질문-정답 쌍 수집 완료.")
    
    random.seed(42)
    random.shuffle(raw_pool)

    intent_buckets = {
        "simple_search": [],
        "search": [],
        "authoring": []
    }

    for item in raw_pool:
        intent = classify_intent(item["question"])
        item["intent"] = intent
        
        if len(intent_buckets[intent]) < samples_per_intent:
            intent_buckets[intent].append(item)

    golden_dataset = []
    for intent, items in intent_buckets.items():
        golden_dataset.extend(items)
        print(f" [Intent: {intent}] {len(items)}개 샘플링 완료")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(golden_dataset, f, ensure_ascii=False, indent=4)
        
    print(f"\n Golden Evaluation Dataset 생성 완료! ({OUTPUT_PATH})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Golden Dataset Builder")
    parser.add_argument(
        "--samples", 
        type=int, 
        default=5, 
        help="각 인텐트(Intent)별 샘플링할 질문의 개수 (기본값: 5)"
    )
    args = parser.parse_args()
    
    build_golden_dataset(samples_per_intent=args.samples)