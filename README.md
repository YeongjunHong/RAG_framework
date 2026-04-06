# RAG Pipeline

RAG 파이프라인을 안정적으로 운영하고 확장하기 위해 파이프라인의 각 단계는 interface, stage, 기능(service, plugin) 세 가지 구성으로 설계되었습니다.
세 개의 계층은 역할과 책임을 명확히 분리하여 재사용성, 유지보수성, 확장성을 높이는 것을 목표로 합니다.

---

## 1. 계층의 역할

### interface 계층
외부 의존성을 추상화하기 위한 인터페이스 레이어입니다.
실질적인 기능 구현체가 특정 인프라나 라이브러리에 종속되지 않도록 경계를 형성합니다.

* 외부 시스템과의 인터페이스 정의
* PostgreSQL, Local LLM, Cloud Router 등 구현체 교체 가능
* 테스트 시 Mock 또는 In-memory 구현으로 대체 가능

---

### stage 계층
RAG 파이프라인의 각 단계를 독립적인 책임 단위로 분리한 실행 레이어입니다.
모든 `src/rag/stages/*`은 `interfaces.py`, `types.py` 입출력 명세를 따릅니다.

* Query Expansion, Retrieval, Reranking 등 단계별 책임 분리
* LangGraph 노드 단위로 조합 및 분기 가능
* 플랜 변경 시 그래프 구조는 유지하되 내부 기능 구현체 선택권을 조정하여 흐름 제어 가능
* 파이프라인을 관통하는 Context를 기반으로 데이터 전달

---

### 기능(service, plugin) 계층
실제 로직(DB 쿼리, 벡터 검색, LLM 호출 등)을 수행하는 구현 레이어입니다.
인터페이스를 상속받아 구현하며, 인프라 변경 시 영향 범위를 최소화합니다.

* PostgreSQL + pgvector + pgsearch 하이브리드 검색 구현
* OpenRouter 또는 Local LLM 호출 로직
* SLM Planner, Reranker, Guardrails, 평가 로직 등 실제 기능 포함

---

## 2. 계층 분리 목적

* RAG에서 Planner가 만든 플랜에 따라 각 노드의 흐름을 Agentic 하고 유연하게 변경
* 동일한 단계에서도 인터페이스 구현체 또는 Config 변경을 통해 동작 제어 및 확장
* 프레임워크(LangGraph)와 Core 로직을 분리하여 재사용성 확보
* 기능 교체, 실험, A/B 테스트를 최소한의 코드 수정으로 가능

---

## 3. RAG Pipeline Implementation Status

| Step | Process Name | Description | Status | 비고 |
| :--- | :--- | :--- | :---: | :--- |
| **01** | Planner | 쿼리 의도 분석 및 동적 라우팅 | **완료** | 정규식 프론트도어 및 SLM 도입으로 동적 라우팅 구현 |
| **02** | Query Expansion | 질문 구체화 및 유사 질문 생성 | **대기** | 향후 Agent 도입 및 가중치 튜닝 예정 |
| **03** | Retrieval | 유사 문서 후보군 탐색 | **완료** | pgvector와 BM25를 결합한 하이브리드 검색 |
| **04** | Reranking | 검색 결과 순위 재조정 | **완료** | Cross-Encoder 모델 및 Sigmoid 확률 정규화 적용 |
| **05** | Filtering | 메타데이터/점수 기반 필터링 | **완료** | 정규화 점수 임계값(Threshold) 기반 노이즈 필터링 |
| **06** | Assembly | 정보 조각 조립 | **완료** | Source ID 기준 병합 및 문맥 논리 순서 복원 |
| **07** | Compression | 토큰 최적화 및 요약 | **완료** | 인코더 기반 토큰 예산 맞춤형 가지치기 |
| **08** | Packing | LLM 입력 최적화 | **완료** | 파싱에 최적화된 XML 직렬화 및 Escape 처리 |
| **09** | Prompt Maker | 최종 프롬프트 생성 | **완료** | 쿼리 의도(Intent)에 따른 동적 지시어 스위칭 |
| **10** | Generator LLM | 답변 생성 | **완료** | OpenRouter 연동 및 비동기 스트리밍 최적화 |
| **11** | Post Check | 환각(Hallucination) 검증 | **대기** | Guardrails 규칙 기반 사후 안전성 검증 로직 구현 예정 |

---

## 4. 구조도 

RAG_FRAMEWORK/
├── .venv/
├── .vscode/
├── pg-ext/
├── settings/
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
│       ├── core/
│       │   ├── interfaces.py
│       │   └── types.py
│       ├── plugins/
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
│       ├── services/
│       │   ├── __init__.py
│       │   ├── registry.py
│       │   └── wiring.py
│       ├── stages/
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
│       ├── graph.py
│       └── readme.md
├── tests/
├── .gitignore
├── .python-version
├── eval_threshold.py
├── main.py
├── README.md
├── requirements.txt
├── run_demo.py
├── test_api.py
├── test_graph.py
└── test_retriever.py