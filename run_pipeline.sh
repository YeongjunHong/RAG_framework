#!/bin/bash
#chmod +x run_pipeline.sh   
set -e

C_GREEN='\033[0;32m'
C_CYAN='\033[0;36m'
C_YELLOW='\033[1;33m'
C_NC='\033[0m' # No Color

# 첫 번째 인자가 있으면 사용하고, 없으면 기본값 5로 설정
SAMPLES_PER_INTENT=${1:-5}

echo -e "${C_GREEN} Starting RAG MLOps Pipeline...${C_NC}"
echo "====================================================="

echo -e "${C_CYAN}\n[Step 1] Building Golden Evaluation Dataset...${C_NC}"
echo -e "${C_YELLOW}  인텐트당 ${SAMPLES_PER_INTENT}개의 샘플을 추출합니다.${C_NC}"
PYTHONPATH=. python scripts/build_eval_dataset.py --samples $SAMPLES_PER_INTENT

echo -e "${C_CYAN}\n[Step 2] Tuning Dynamic Thresholds (Calibration)...${C_NC}"
PYTHONPATH=. python scripts/tune_threshold.py

echo -e "${C_CYAN}\n[Step 3] Running Showcase Demo (Sanity Check)...${C_NC}"
# 데모 자동 넘기기 (필요시 주석 해제)
# echo -e "y\n\n\n\n\n\n" | PYTHONPATH=. python examples/run_showcase.py
PYTHONPATH=. python examples/run_showcase.py

echo -e "${C_CYAN}\n[Step 4] RAGAS 정량 평가 실행...${C_NC}"
PYTHONPATH=. python scripts/evaluate_ragas.py

echo "====================================================="
echo -e "${C_GREEN} Pipeline Completed Successfully!${C_NC}"