# RAG Pipeline (Enterprise Edition)

본 프로젝트는 금융 및 정책 도메인에 특화된 RAG(Retrieval-Augmented Generation) 파이프라인으로, 안정적인 운영과 유연한 확장을 위해 **Interface**, **Stage**, **Service/Plugin**의 3계층 아키텍처로 설계되었습니다.

---

## 1. 계층별 역할 및 책임

### interface 계층
외부 의존성을 추상화하기 위한 인터페이스 레이어입니다. 실질적인 기능 구현체가 특정 인프라나 라이브러리에 종속되지 않도록 경계를 형성합니다.
* 외부 시스템과의 인터페이스 정의 (`src/rag/core/interfaces.py`)
* PostgreSQL, Local LLM, Cloud Router 등 구현체 교체 가능
* 테스트 시 Mock 또는 In-memory 구현으로 대체 가능

### stage 계층
RAG 파이프라인의 각 단계를 독립적인 책임 단위로 분리한 실행 레이어입니다. 모든 `src/rag/stages/*`은 공통 입출력 명세를 따릅니다.
* Query Expansion, Retrieval, Reranking 등 단계별 책임 분리
* LangGraph 노드 단위로 조합 및 분기 가능
* 파이프라인을 관통하는 `RagContext`를 기반으로 데이터 전달

### 기능(service, plugin) 계층
실제 로직(DB 쿼리, 벡터 검색, LLM 호출 등)을 수행하는 구현 레이어입니다.
* PostgreSQL + pgvector 하이브리드 검색 구현
* SLM Planner, Reranker, LLM-as-a-Judge(Guardrails) 등 실제 기능 포함

---

## 2. RAG Pipeline Implementation Status

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

* **Hybrid Filtering Logic**: 1등 문서와의 점수 차이(Relative Margin)와 절대 하한선(Floor)을 결합하되, `Min-K` 보장 로직으로 컨텍스트 기아 현상을 방지합니다.
* **Agentic Routing**: 일상 대화(Chitchat)와 지식 검색 질문을 Planner가 분리하여 리소스 소모를 최적화합니다.
* **Fail-fast Guardrails**: 주민번호 등 PII 감지 시 즉시 차단하며, LLM Judge를 통해 문서에 근거하지 않은 환각(Hallucination)을 검증합니다.

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