# RAG Pipeline 

본 프로젝트는 데이터셋의 도메인에 구애받지 않고 고신뢰성 답변을 생성하기 위한 **범용 RAG(Retrieval-Augmented Generation) 프레임워크**입니다. 
안정적인 운영과 무한한 확장을 위해 **Interface**, **Stage**, **Service/Plugin**의 3계층 아키텍처로 설계되었습니다.
***이 레포에서는 실험을 위해 금융 정책 데이터셋을 사용함***
---

## 1. 계층별 역할 및 책임

### Interface 계층 (`src/rag/core/*`)
외부 의존성을 추상화하기 위한 인터페이스 레이어입니다. 실질적인 기능 구현체가 특정 인프라나 라이브러리에 종속되지 않도록 경계를 형성합니다.
* 외부 시스템과의 인터페이스 정의 (`src/rag/core/interfaces.py`)
* PostgreSQL, Local LLM, Cloud Router 등 구현체 교체 가능
* 테스트 시 Mock 또는 In-memory 구현으로 대체 가능

### Stage 계층 (`src/rag/stages/*`)
RAG 파이프라인의 각 단계를 독립적인 책임 단위로 분리한 실행 레이어입니다. 모든 스테이지는 공통 입출력 명세(`RagRequest`, `RagContext`)를 따릅니다.
* Input Guard, Planner, Query Expansion, Retrieval, Reranking 등 단계별 책임 분리
* LangGraph 노드 단위로 조합 및 조건부 분기(Conditional Edge) 가능
* 파이프라인을 관통하는 `RagContext`를 기반으로 데이터 및 텔레메트리 전달

### Service/Plugin 계층 (`src/rag/plugins/*`)
실제 로직(DB 쿼리, 벡터 검색, LLM 호출, 정규식 검사 등)을 수행하는 구현 레이어입니다.
* PostgreSQL + pgvector 하이브리드 검색 구현
* SLM Planner, Multi-Query Generator, LLM-as-a-Judge(Guardrails), 정규식 기반 Input Guard 등 포함

---

## 2. 검증 데이터셋 (Reference Dataset)
프레임워크의 성능과 신뢰성을 테스트하기 위해 아래의 고난도 도메인 데이터를 기본 레퍼런스로 활용하고 있습니다.

*   **금융/정책 통합 데이터셋:** 전문 용어, 복잡한 수치 정보, 상충하는 정책 지침이 포함된 비정형 텍스트 데이터
*   **특징:** 유사한 키워드가 많아 정교한 Reranking 및 Filtering 능력을 검증하기에 최적화된 데이터셋

---

## 3. RAG Pipeline Implementation Status

| Step | Process Name | Description | Status | 비고 |
| :--- | :--- | :--- | :---: | :--- |
| **00** | Input Guard | 악의적 프롬프트 및 PII 탐지 방어 | **완료** | 정규식 기반 프론트도어 방어 및 빠른 우회(Fail-fast) 적용 |
| **01** | Planner | 쿼리 의도 분석 및 동적 라우팅 | **완료** | SLM 기반 의도 분류(Chitchat, Search, Authoring 등) |
| **02** | Query Expansion | 질문 구체화 및 유사 질문 생성 | **완료** | 의도별 동적 확장 (키워드 추출 vs 다중 쿼리 생성) 및 강건한 JSON 파싱 |
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

## 4. 핵심 아키텍처 특징

* **Fail-fast Security Guard (프론트도어 방어):** 
  * 파이프라인의 가장 앞단에서 정규식 기반의 `InputGuard`가 Prompt Injection 및 PII(주민등록번호, 신용카드 등) 유출 시도를 즉각적으로 탐지합니다. 위협 감지 시 무거운 검색 모델을 호출하지 않고 즉시 방어 응답을 반환하여 컴퓨팅 리소스를 보호합니다.
* **Intent-Driven Dynamic Query Routing (동적 쿼리 라우팅):** 
  * `Planner`가 파악한 의도에 따라 쿼리 확장(Query Expansion) 전략이 동적으로 변경됩니다. 단순 정보 검색은 불용어를 제거한 핵심 키워드만 추출하여 **BM25 타겟 채널**로 전송하고, 복잡한 추론 검색은 의미가 보존된 다중 쿼리를 생성하여 **Vector 타겟 채널**로 전송하여 재현율(Recall)을 극대화합니다. 일상 대화(Chitchat)의 경우 검색 단계를 완전히 건너뜁니다.
* **Robust LLM Parser (강건한 출력 파서):** 
  * 오픈소스 모델 특유의 비결정적 출력(마크다운 포맷팅 섞임, 불필요한 인사말 생성 등)으로 인한 시스템 장애를 막기 위해, 텍스트 스트림에서 순수 JSON 블록만 안전하게 추출하는 정규식 방어 로직을 내장하여 파이프라인의 안정성(Robustness)을 보장합니다.
* **Domain-Agnostic Design:** 
  * 데이터 스키마와 검색 엔진이 분리되어 있어, 어떤 도메인의 텍스트 데이터도 즉시 주입 및 검색이 가능합니다.
* **Hybrid Filtering Logic:** 
  * 절대 하한선과 상대 편차 임계값을 결합하여 '정답이 없는 상황'에서도 환각을 방지하고 최소한의 문맥(`Min-K`)을 확보합니다.
* **Groundedness Post-check:** 
  * 생성된 답변이 제공된 문서에 완벽히 기반하는지를 최종 단계에서 LLM 판관(Judge) 모델이 엄격히 교차 검증하여 환각(Hallucination)을 원천 차단합니다.

---

## 5. 구조도 

```text
RAG_FRAMEWORK/
├── .venv/
├── pg-ext/
├── settings/
│   └── input_guard_rules.json        # Input Guard 정규식 패턴 및 보안 정책 룰셋
├── src/
│   ├── common/
│   │   └── logger.py                 # 표준 로깅 포맷 및 핸들러 설정
│   ├── rag/
│   │   ├── bulk_source/              
│   │   │   └── source_chunk_ingestion.py # 데이터셋 다운로드 및 pgvector 청크 적재 스크립트
│   │   ├── core/
│   │   │   ├── interfaces.py         # 파이프라인 확장을 위한 추상 기본 클래스 (ABC)
│   │   │   └── types.py              # Pydantic 기반 도메인 모델 (RagContext, Chunk 등)
│   │   ├── plugins/                  # 외부 의존성(DB, LLM, Model) 주입 플러그인
│   │   │   ├── input_guard_regex.py  # 정규식 기반 프론트도어 보안 검사기
│   │   │   ├── qe_keyword.py         # BM25 타격용 불용어 제거 및 키워드 추출기
│   │   │   ├── qe_multi_query.py     # Vector 타격용 다중 쿼리 생성기 (의미 확장)
│   │   │   ├── postgres_retriever.py # 채널 분리(비동기 병렬) 및 App-Level RRF 하이브리드 검색기
│   │   │   ├── local_reranker.py     # bge-reranker-v2-m3 추론 및 Sigmoid 정규화
│   │   │   ├── text_compressor.py    # SLM 기반 Semantic Text Compression (의미 압축) 플러그인
│   │   │   ├── slm_planner.py        # Llama-3-8b 기반 의도 분류 플래너
│   │   │   ├── guardrails_runner.py  # 답변 안전성 및 할루시네이션 검증 모듈
│   │   │   ├── openrouter_generator.py # OpenRouter 기반 비동기 스트리밍 답변 생성기
│   │   │   ├── noop.py               # 파이프라인 우회용 No-operation 더미 객체
│   │   │   └── router.py             # LLM 인스턴스 빌더 
│   │   ├── services/
│   │   │   ├── registry.py           # 플러그인 객체 생명주기를 관리하는 레지스트리 (DI 컨테이너)
│   │   │   └── wiring.py             # 애플리케이션 구동 시 플러그인 의존성 주입 조립
│   │   ├── stages/                   # LangGraph의 단일 책임을 가지는 실행 노드(Node)
│   │   │   ├── input_guard.py        # 프롬프트 인젝션 및 PII 즉시 차단 (Fail-fast)
│   │   │   ├── planner.py            # SLM을 통한 쿼리 의도 분석 및 라우팅 플래그 제어
│   │   │   ├── query_expansion.py    # 사용자 쿼리를 의도에 맞춰 다각화 (Keyword/Semantic)
│   │   │   ├── retrieval.py          # 비동기 병렬 DB 쿼리 및 RRF 결합 초기 문서 풀 확보
│   │   │   ├── reranking.py          # Cross-Encoder를 활용한 Query-Chunk 문맥 유사도 재평가
│   │   │   ├── filtering.py          # 정규화된 확률 점수(min_score) 기준 노이즈 하드 드랍
│   │   │   ├── assembly.py           # 파편화된 청크를 출처(Source) 단위 병합 및 논리적 정렬
│   │   │   ├── compression.py        # 2-Step 압축 (SLM 의미 압축 후 인코더 기반 Token 삭감)
│   │   │   ├── packing.py            # 압축된 객체를 XML 마크업 직렬화 및 Escape 처리
│   │   │   ├── prompt_maker.py       # 의도에 따른 시스템 지시어 스위칭 및 최종 Prompt 조립
│   │   │   ├── generator.py          # LLM API 호출 및 비동기 Queue 기반 스트리밍 처리
│   │   │   └── post_check.py         # 판관(Judge) 모델을 통한 Groundedness 사후 검증
│   │   └── graph.py                  # LangGraph StateMachine 정의 및 조건부 간선(Edge) 라우팅
├── run_showcase.py                   # 대화형 CLI 데모 및 복합 추론 시나리오 벤치마크 실행
└── showcase_history.jsonl            # 파이프라인 E2E 실행 로그 및 Telemetry 트레이스 덤프
├── main.py                                 # 어플리케이션 엔트리포인트
├── requirements.txt                        # 의존성 패키지
└── README.md
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

    subgraph "Phase 0: Security Gateway"
        InputGuard{Input Guard<br/>Regex & Policy}:::guard
    end

    subgraph "Phase 1: Planning & Routing"
        Planner{Planner<br/>SLM Intent Classifier}:::router
    end

    subgraph "Phase 2: Parallel Retrieval & Reranking"
        QueryExpansion[Query Expansion<br/>Keyword & Semantic]:::retrieval
        
        RetrievalSplit{Async Dispatch}:::router
        BM25[(pg_trgm / BM25<br/>Sparse Search)]:::retrieval
        Vector[(pgvector<br/>Dense Search)]:::retrieval
        RRF[App-Level RRF<br/>Rank Fusion]:::process
        
        Reranking[Reranking<br/>Cross-Encoder]:::retrieval
        Filtering[Filtering<br/>Threshold Drop]:::retrieval
    end

    subgraph "Phase 3: Context Engineering"
        Assembly[Assembly<br/>Source Grouping]:::process
        Compression[Compression<br/>Step 1: SLM Semantic<br/>Step 2: Token Budget]:::process
        Packing[Packing<br/>XML Serialization]:::process
    end

    subgraph "Phase 4: Generation & Safety"
        PromptMaker[Prompt Maker<br/>Dynamic System Prompt]:::generation
        Generator[Generator<br/>Async Streaming]:::generation
        PostCheck[Post Check<br/>LLM Judge Groundedness]:::guard
    end

    %% Data Flow & Routing
    InputGuard -- "is_safe: False" --> PromptMaker
    InputGuard -- "is_safe: True" --> Planner

    Planner -- "chitchat / security" --> PromptMaker
    Planner -- "search intent" --> QueryExpansion

    QueryExpansion --> RetrievalSplit
    RetrievalSplit --> BM25
    RetrievalSplit --> Vector
    BM25 --> RRF
    Vector --> RRF
    
    RRF --> Reranking
    Reranking --> Filtering
    Filtering --> Assembly
    
    Assembly --> Compression
    Compression --> Packing
    Packing --> PromptMaker

    PromptMaker --> Generator
    Generator --> PostCheck
    PostCheck --> End([Final Response]):::endpoin
  ```