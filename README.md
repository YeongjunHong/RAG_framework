# RAG Pipeline Framework (High-Reliability & Cost-Optimized)

본 프로젝트는 데이터셋의 도메인에 구애받지 않고 고신뢰성 답변을 생성하기 위한 **범용 RAG(Retrieval-Augmented Generation) 프레임워크**입니다. 
단순한 답변 생성을 넘어 **비용 최적화(Semantic Caching)**, **품질 자동 교정(Dynamic Thresholding)**, **정량적 검증(RAGAS Evaluation)** 시스템을 통합한 MLOps 지향적 아키텍처로 설계되었습니다.

---

## 1. 계층별 역할 및 책임

### Interface 계층 (`src/rag/core/*`)
외부 의존성을 추상화하기 위한 인터페이스 레이어입니다. 
* 외부 시스템과의 인터페이스 정의 (`src/rag/core/interfaces.py`)
* PostgreSQL, Local LLM, Cloud Router 등 구현체 교체 가능

### Stage 계층 (`src/rag/stages/*`)
LangGraph 노드 단위로 실행되는 독립적 책임 단위입니다.
* 모든 스테이지는 공통 입출력 명세(`RagRequest`, `RagContext`)를 따릅니다.
* 단계별 에러 핸들링 및 조건부 분기(Conditional Edge)를 지원합니다.

### Service/Plugin 계층 (`src/rag/plugins/*`)
실제 비즈니스 로직과 알고리즘을 수행하는 구현 레이어입니다.
* 하이브리드 검색, Reranker, Semantic Compressor, Cache Manager 등이 포함됩니다.

---

## 2. 검증 데이터셋 (Reference Dataset)
프레임워크의 성능을 테스트하기 위해 아래의 고난도 금융/정책 오픈 소스 데이터를 활용합니다.
* `allganize/RAG-Evaluation-Dataset-KO`
* `BCCard/BCCard-Finance-Kor-QnA`
* `kifai/KoInFoBench`

---

## 3. Implementation Status

| Step | Process Name | Description | Status | 비고 |
| :--- | :--- | :--- | :---: | :--- |
| **00** | Input Guard | 악의적 프롬프트 및 PII 탐지 방어 | **완료** | 정규식 기반 Fail-fast 적용 |
| **01** | Semantic Cache | Redis 기반 의미 유사도 캐싱 | **완료** | **LLM 호출 비용 90% 절감 (Similarity 0.90)** |
| **02** | Planner | 쿼리 의도 분석 및 동적 라우팅 | **완료** | SLM 기반 의도 분류 및 Bypass 전략 |
| **03** | Query Expansion | 질문 구체화 및 유사 질문 생성 | **완료** | 키워드 추출 vs 다중 쿼리 생성 전략 |
| **04** | Retrieval | 유사 문서 후보군 탐색 | **완료** | pgvector + BM25 하이브리드 검색 |
| **05** | Reranking | 검색 결과 순위 재조정 | **완료** | Cross-Encoder 및 Sigmoid 정규화 |
| **06** | Filtering | 점수 기반 동적 노이즈 제거 | **완료** | **Floor + Margin + Min-K 하이브리드 필터링** |
| **07** | Post Check | 사후 안전성 및 근거 검증 | **완료** | **LLM Judge 기반 Groundedness 검증** |
| **-** | **Threshold Tuner**| 임계값 자동 최적화 | **완료** | **F1-Score 기반 Calibration 스크립트** |
| **-** | **RAGAS Evaluator**| 정량적 품질 품질 채점 | **완료** | **Faithfulness, Relevancy 등 지표 추적** |

---

## 4. 핵심 아키텍처 특징

* **Semantic Cache & Early Exit:** * Redis Vector Search를 이용한 캐싱으로 중복 질문에 대한 비용을 0으로 만듭니다. 
  * 검색 결과가 없는 경우(Context Starvation) LLM을 호출하지 않고 조기 종료(Early Exit)하여 할루시네이션을 원천 차단합니다.
* **Intent-Driven Filtering (Min-K Guarantee):** * 검색 결과의 절대 점수가 낮더라도 최소한의 문맥(`Min-K`)을 보장하거나 인텐트에 따라 Reranker를 우회하여 답변 재현율(Recall)을 확보합니다.
* **Config-Driven MLOps Pipeline:** * 코드 수정 없이 설정 파일(`dynamic_thresholds.json`)과 쉘 스크립트만으로 최적화와 평가 전 과정을 제어합니다.
* **Groundedness Enforcement:** * 생성된 답변이 제공된 문서에 완벽히 기반하는지를 최종 단계에서 LLM 판관 모델이 검증하여 신뢰성을 보장합니다.

---

## 5. Directory Structure 

본 프레임워크는 유지보수와 확장성을 극대화하기 위해 책임이 명확히 분리된 디렉토리 구조를 가집니다.

## 5. Directory Structure 

본 프레임워크는 각 모듈의 책임이 엄격히 분리되어 있으며, 특히 **LangGraph 기반의 Stage**와 **구현체 중심의 Plugin** 구조를 통해 높은 확장성을 보장합니다.

```text
RAG_framework/
├── data/                             # Golden Dataset 및 평가 결과 리포트 적재
├── examples/                         # 시스템 시연 및 시나리오 벤치마크
│   ├── run_demo.py                   # 기본 기능 단위 검증용 데모
│   └── run_showcase.py               # E2E 복합 추론 및 보안 시나리오 통합 데모
├── pg-ext/                           # Docker 기반 PostgreSQL/pgvector 인프라 구성
├── scripts/                          # MLOps 자동화 및 하이퍼파라미터 튜닝
│   ├── build_eval_dataset.py         # HF 데이터셋 기반 평가 데이터 자동 구축
│   ├── evaluate_ragas.py             # RAGAS 기반 정량 품질 평가 엔진
│   ├── find_ground_truth.py          # 평가용 정답지 매칭 보조 툴
│   └── tune_threshold.py             # F1-Score 기반 검색 임계값 최적화 (Calibration)
├── settings/                         # 전역 환경 변수 및 DB 마이그레이션 설정
├── src/
│   ├── api/                          # FastAPI 서빙 레이어 및 라우팅 (routes.py)
│   ├── common/                       # 공통 유틸리티 (Config, Logger, Helper, Utils)
│   ├── evaluation/                   # 성능 지표(Metrics) 정의 및 Runner
│   ├── pgdb/                         # Database 추상화 및 Alembic 마이그레이션 관리
│   │   ├── schema.py                 # SQLAlchemy 기반 DB 스키마 명세
│   │   ├── pg_crud.py                # CRUD 및 비동기 DB 인터페이스 구현체
│   │   └── versions/                 # Alembic 기반 점진적 스키마 히스토리 (init ~ 2026-04)
│   └── rag/                          # 핵심 RAG 도메인 로직
│       ├── bulk_source/              # 데이터 Ingestion 및 Few-shot 예제 관리
│       ├── core/                     # 인터페이스 추상화(ABC) 및 공통 도메인 모델(Types)
│       ├── graph.py                  # LangGraph 상태 머신 및 전체 워크플로우 정의
│       ├── services/                 # 플러그인 생명주기 및 의존성 주입(Wiring) 관리
│       ├── plugins/                  # 실질적인 로직을 수행하는 구현체 레이어 (Adapters)
│       │   ├── cache_manager.py      # Redis 기반 Semantic Vector Caching
│       │   ├── guardrails_runner.py  # 답변 안전성 검증 실행기
│       │   ├── input_guard_regex.py  # 정규식 기반 보안 정책 검사
│       │   ├── local_reranker.py     # Cross-Encoder 기반 로컬 재채점 엔진
│       │   ├── openrouter_generator.py # OpenRouter API 기반 스트리밍 생성기
│       │   ├── postgres_retriever.py # Hybrid Search(Vector+BM25) 물리 엔진
│       │   ├── qe_keyword.py         # BM25 타격용 키워드 추출기
│       │   ├── qe_multi_query.py     # 의미론적 확장을 위한 다중 쿼리 생성기
│       │   ├── slm_planner.py        # SLM 기반 의도 분류 및 라우팅 플래너
│       │   ├── text_compressor.py    # 토큰 최적화를 위한 2-Step 텍스트 압축기
│       │   └── tracing.py            # 파이프라인 텔레메트리 트레이싱
│       └── stages/                   # LangGraph 노드 단위 실행 로직
│           ├── input_guard.py        # 보안 및 PII 차단 (Fail-fast)
│           ├── planner.py            # 쿼리 의도 분석 및 라우팅 결정
│           ├── query_expansion.py    # 사용자 쿼리 다각화
│           ├── retrieval.py          # 하이브리드 검색 및 RRF 랭킹 결합
│           ├── reranking.py          # 문맥 유사도 재평가
│           ├── filtering.py          # 동적 임계값 기반 노이즈 제거
│           ├── dynamic_skip.py       # 의도에 따른 특정 스테이지 동적 스킵 로직
│           ├── assembly.py           # 청크 병합 및 논리적 정렬
│           ├── compression.py        # 토큰 예산 기반 컨텍스트 압축
│           ├── packing.py            # XML 마크업 직렬화
│           ├── prompt_maker.py       # 시스템 지시어 스위칭 및 최종 프롬프트 조립
│           ├── generator.py          # 조기 종료가 적용된 LLM 답변 생성
│           └── post_check.py         # LLM Judge 기반 근거(Groundedness) 검증
└── tests/                            # 모듈별 단위 테스트 및 통합 테스트
├── run_pipeline.sh                   # [Build -> Tune -> Demo -> Eval] 원클릭 실행기
├── main.py                           # 애플리케이션 엔트리포인트 (API 실행)
└── requirements.txt                  # 프로젝트 의존성 명세
```
---

---
## 6. 파이프라인 


```mermaid
graph TD
    classDef default fill:#ffffff,stroke:#333,stroke-width:1px,color:#333;
    classDef router fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#000;
    classDef retrieval fill:#fff3e0,stroke:#f57c00,stroke-width:1px,color:#000;
    classDef process fill:#f3e5f5,stroke:#7b1fa2,stroke-width:1px,color:#000;
    classDef generation fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#000;
    classDef endpoint fill:#eceff1,stroke:#607d8b,stroke-width:2px,color:#000;
    classDef guard fill:#ffebee,stroke:#c62828,stroke-width:2px,color:#000;

    Start([User Query]):::endpoint --> InputGuard

    subgraph "Phase 0: Gateway & Cache"
        InputGuard{Input Guard}:::guard -- "Safe" --> CacheCheck{Semantic Cache<br/>Hit?}:::guard
    end

    subgraph "Phase 1: Planning & Routing"
        CacheCheck -- "Miss" --> Planner{Planner<br/>SLM Intent Classifier}:::router
    end

    subgraph "Phase 2: Retrieval & Reranking"
        Planner -- "Search" --> QueryExpansion[Query Expansion]:::retrieval
        QueryExpansion --> Retrieval[(Hybrid Retrieval<br/>Vector + BM25)]:::retrieval
        Retrieval --> Reranking[Reranking<br/>Cross-Encoder]:::retrieval
        Reranking --> Filtering[Filtering<br/>Dynamic Threshold]:::retrieval
    end

    subgraph "Phase 3: Context Engineering"
        Filtering --> Assembly[Assembly]:::process
        Assembly --> Compression[Compression]:::process
        Compression --> Packing[Packing]:::process
    end

    subgraph "Phase 4: Generation & Safety"
        Packing --> PromptMaker[Prompt Maker]:::generation
        CacheCheck -- "Hit" --> PromptMaker
        PromptMaker --> Generator[Generator<br/>Early Exit Check]:::generation
        Generator -- "Gen Success" --> CacheSave[(Save to Cache)]:::guard
        Generator --> PostCheck[Post Check<br/>LLM Judge]:::guard
    end

    subgraph "Phase 5: MLOps Governance (Offline)"
        GoldenSet[(Golden Dataset)] --> Eval[RAGAS Evaluator]:::process
        Eval --> Tuner[Threshold Tuner]:::process
        Tuner --> DynamicConfig[Dynamic Thresholds.json]:::process
    end

    PostCheck --> End([Final Response]):::endpoint
    InputGuard -- "Violated" --> End
  ```

---

---

## 7. How to Run 

본 프레임워크는 데이터셋 구축부터 정량 평가까지의 전 과정을 **원클릭 파이프라인 자동화**로 지원합니다.

###  사전 준비
`.env.poc` 파일에 OpenRouter API Key 및 DB 연결 정보가 설정되어 있어야 합니다.

###  파이프라인 실행
터미널에서 아래 명령어를 순서대로 입력하세요.

```bash
# 1. 필수 의존성 라이브러리 설치
pip install -r requirements.txt

# 2. 실행 권한 부여
chmod +x run_pipeline.sh

# 3. 전체 파이프라인 자동 실행 (인자값: 인텐트당 샘플 개수, 기본값: 5)
# 시퀀스: [Build Dataset] -> [Tune Thresholds] -> [Run Showcase] -> [Evaluate RAGAS]
./run_pipeline.sh 3

---
