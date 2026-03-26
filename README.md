# RAG 파이프라인

RAG 파이프라인을 안정적으로 운영하고 확장하기 위해 파이프라인의 각 단계는 interface, stage, 기능(service, plugin) 세 가지 구성으로 설계
세 개의 계층은 역할과 책임을 명확히 분리하여 재사용성, 유지보수성, 확장성을 높이는 것을 목표

---

## 1. 계층의 역할

### interface 계층

외부 의존성을 추상화하기 위한 인터페이스 레이어
실질적인 기능 구현체가 특정 인프라나 라이브러리에 종속되지 않도록 경계를 형성

* 외부 시스템과의 인터페이스 정의
* PostgreSQL, Local LLM, Cloud Router 등 구현체 교체 가능
* 테스트 시 Mock 또는 In-memory 구현으로 대체 가능

---

### stage 계층

RAG 파이프라인의 각 단계를 독립적인 책임 단위로 분리한 실행 레이어
모든 `src/rag/stages/*`은 interfaces.py, types.py 입출력 명세를 따름

* Query Expansion, Retrieval, Reranking 등 단계별 책임 분리
* LangGraph 노드 단위로 조합 및 분기 가능
* 플랜 변경 시 그래프 구조는 유지하되 내부 기능 구현체 선택권을 조정하여 흐름 제어 가능
* 파이프라인을 관통하는 Context를 기반으로 데이터 전달

---

### 기능(service, plugin) 계층

실제 로직(DB 쿼리, 벡터 검색, LLM 호출 등)을 수행하는 구현 레이어
인터페이스를 상속받아 구현하며, 인프라 변경 시 영향 범위를 최소화

* PostgreSQL + pgvector + pgsearch 하이브리드 검색 구현
* OpenRouter 또는 Local LLM 호출 로직
* Reranker, Guardrails, 평가 로직 등 실제 기능 포함

---

## 2. 계층 분리 목적

* RAG에서 Planner가 만든 플랜에 따라 각 노드의 흐름을 Agentic 하고, 유연하게 변경
* 동일한 단계에서도 인터페이스 구현체 또는 Config 변경을 통해 동작 제어 및 확장
* 프레임워크(LangGraph)와 Core 로직을 분리하여 재사용성 확보
* 기능 교체, 실험, A/B 테스트를 최소한의 코드 수정으로 가능

---


## 3. 구조도 

```
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
│       │   ├── noop.py
│       │   ├── openrouter_generator.py
│       │   ├── openrouter.py
│       │   ├── postgres_retriever.py
│       │   ├── router.py
│       │   └── tracing.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── registry.py
│       │   └── wiring.py
│       ├── stages/
│       │   ├── assembly.py
│       │   ├── compression.py
│       │   ├── filtering.py
│       │   ├── generator.py
│       │   ├── packing.py
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
├── main.py
├── README.md
├── requirements.txt
├── test_api.py
├── test_graph.py
├── test_retriever.py
```
