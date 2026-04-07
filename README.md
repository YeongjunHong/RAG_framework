# RAG Pipeline 

본 프로젝트는 데이터셋의 도메인에 구애받지 않고 고신뢰성 답변을 생성하기 위한 **범용 RAG(Retrieval-Augmented Generation) 프레임워크**입니다. 
안정적인 운영과 무한한 확장을 위해 **Interface**, **Stage**, **Service/Plugin**의 3계층 아키텍처로 설계되었습니다.
***이 레포에서는 실험을 위해 금융 정책 데이터셋을 사용함***
---

## 1. 계층별 역할 및 책임

###  Interface 계층 (`src/rag/core/*`)
외부 의존성을 추상화하기 위한 인터페이스 레이어입니다. 실질적인 기능 구현체가 특정 인프라나 라이브러리에 종속되지 않도록 경계를 형성합니다.
* 외부 시스템과의 인터페이스 정의 (`src/rag/core/interfaces.py`)
* PostgreSQL, Local LLM, Cloud Router 등 구현체 교체 가능
* 테스트 시 Mock 또는 In-memory 구현으로 대체 가능

### stage 계층 (`src/rag/stages/*`)
RAG 파이프라인의 각 단계를 독립적인 책임 단위로 분리한 실행 레이어입니다. 모든 `src/rag/stages/*`은 공통 입출력 명세를 따릅니다.
* Query Expansion, Retrieval, Reranking 등 단계별 책임 분리
* LangGraph 노드 단위로 조합 및 분기 가능
* 파이프라인을 관통하는 `RagContext`를 기반으로 데이터 전달

### 기능(Service/Plugin) 계층 (`src/rag/plugins/*`)
실제 로직(DB 쿼리, 벡터 검색, LLM 호출 등)을 수행하는 구현 레이어입니다.
* PostgreSQL + pgvector 하이브리드 검색 구현
* SLM Planner, Reranker, LLM-as-a-Judge(Guardrails) 등 실제 기능 포함

---

## 2. 검증 데이터셋 (Reference Dataset)
프레임워크의 성능과 신뢰성을 테스트하기 위해 아래의 고난도 도메인 데이터를 기본 레퍼런스로 활용하고 있습니다.

*   **금융/정책 통합 데이터셋:** 전문 용어, 복잡한 수치 정보, 상충하는 정책 지침이 포함된 비정형 텍스트 데이터
*   **특징:** 유사한 키워드가 많아 정교한 Reranking 및 Filtering 능력을 검증하기에 최적화된 데이터셋

---

## 3. RAG Pipeline Implementation Status

| Step | Process Name | Description | Status | 비고 |
| :--- | :--- | :--- | :---: | :--- |
| **01** | Planner | 쿼리 의도 분석 및 동적 라우팅 | **완료** | 정규식 프론트도어 및 SLM 기반 동적 라우팅 |
| **02** | Query Expansion | 질문 구체화 및 유사 질문 생성 | **대기** | 향후 멀티 쿼리 생성 및 가중치 결합 예정 |
| **03** | Retrieval | 유사 문서 후보군 탐색 | **완료** | pgvector와 BM25를 결합한 하이브리드 검색 |
| **04** | Reranking | 검색 결과 순위 재조정 | **완료** | Cross-Encoder 모델 및 Sigmoid 정규화 적용 |
| **05** | Filtering | 점수 기반 동적 노이즈 제거 | **완료** | **하이브리드 필터링 (Floor + Margin + Min-K)** |
| **06** | Assembly | 정보 조각 조립 및 복원 | **완료** | Source ID 기준 병합 및 문맥 논리 순서 복원 |
| **07** | Compression | 토큰 최적화 및 요약 | **완료** | 인코더 기반 토큰 예산 맞춤형 가지치기 |
| **08** | Packing | LLM 입력 최적화 (XML) | **완료** | 파싱 최적화 XML 구조화 및 Escape 처리 |
| **09** | Prompt Maker | 최종 프롬프트 생성 | **완료** | 인텐트(Intent)에 따른 동적 지시어 스위칭 |
| **10** | Generator LLM | 답변 생성 | **완료** | OpenRouter 연동 및 비동기 스트리밍 최적화 |
| **11** | Post Check | 사후 안전성 및 근거 검증 | **완료** | **LLM Judge 기반 Groundedness 검증 가동** |

---

## 3. 핵심 아키텍처 특징

* **Domain-Agnostic Design:** 데이터 스키마와 검색 엔진이 분리되어 있어, 어떤 도메인의 텍스트 데이터도 즉시 주입 및 검색이 가능합니다.
* **Hybrid Filtering Logic:** 절대 하한선과 상대 편차 임계값을 결합하여 '정답이 없는 상황'에서도 환각을 방지하고 최소한의 문맥(`Min-K`)을 확보합니다.
* **Fail-fast Guardrails:** 생성된 답변이 제공된 문서에 기반하는지(`Groundedness`)를 최종 단계에서 엄격히 검증하여 신뢰성을 담보합니다.

---

## 4. 구조도 

```
RAG_FRAMEWORK/
├── .venv/
├── .vscode/
├── pg-ext/
├── settings/                               # 환경 변수 및 임계값 아티팩트
├── src/
│   ├── api/
│   ├── common/
│   ├── evaluation/
│   ├── pgdb/
│   │   ├── versions/
│   │   ├── env.py
│   │   ├── pg_crud.py
│   │   ├── schema.py
│   │   ├── script.py.mako
│   │   └── readme.md
│   └── rag/
│       ├── bulk_source/
│       │   ├── source_chunk_ingestion.py
│       │   └── source_fewshot_example.py
│       ├── core/                           # 공통 타입 및 인터페이스
│       │   ├── interfaces.py
│       │   └── types.py
│       ├── plugins/                        # 리트리버, 리랭커, 가드레일 구현체
│       │   ├── __init__.py
│       │   ├── guardrails_runner.py
│       │   ├── inmemory.py
│       │   ├── local_reranker.py
│       │   ├── noop.py
│       │   ├── openrouter.py
│       │   ├── openrouter_generator.py
│       │   ├── postgres_retriever.py
│       │   ├── router.py
│       │   ├── slm_planner.py
│       │   └── tracing.py
│       ├── services/                       # 의존성 주입 및 레지스트리
│       │   ├── __init__.py
│       │   ├── registry.py
│       │   └── wiring.py
│       ├── stages/                         # 파이프라인 단계별 노드
│       │   ├── assembly.py
│       │   ├── compression.py
│       │   ├── dynamic_skip.py
│       │   ├── filtering.py
│       │   ├── generator.py
│       │   ├── packing.py
│       │   ├── planner.py
│       │   ├── post_check.py
│       │   ├── prompt_maker.py
│       │   ├── query_expansion.py
│       │   ├── reranking.py
│       │   └── retrieval.py
│       ├── graph.py                        # LangGraph 아키텍처 정의
│
├── tests/
├── .gitignore
├── .python-version
├── eval_threshold.py                       # 필터링 임계값 최적화 스크립트
├── main.py                                 # 어플리케이션 엔트리포인트
├── requirements.txt                        # 의존성 패키지
└── README.md



```