# import asyncio
# from typing import Any, Dict, List, Literal, TypeVar
# from pydantic import BaseModel, Field


# TConfig = TypeVar("TConfig", bound=BaseModel)


# class SourceChunk(BaseModel):
#     chunk_id: int
#     source_id: int
#     source_name: str
#     content: str
#     metadata: Dict[str, Any] = Field(default_factory=dict)


# class ScoredChunk(BaseModel):
#     chunk: SourceChunk
#     score: float
#     signals: Dict[str, Any] = Field(default_factory=dict)


# class ExpandedQuery(BaseModel):
#     content: str
#     intent: Literal["original", "keyword", "semantic"]
#     channels: set[Literal["bm25", "tsv", "vector"]] = {}
#     weight: float = 1.0


# class FilteredChunk(BaseModel):
#     chunk: SourceChunk
#     kept: bool
#     reasons: list[str] = []
#     score: float = 0.0 # 새롭게 추가


# class EvidenceGroup(BaseModel):
#     group_id: str
#     title: str | None = None
#     chunks: list[SourceChunk]


# class Citation(BaseModel):
#     source_id: int
#     chunk_id: int
#     quote: str|None = None


# class RagContext(BaseModel):
#     # Planning
#     plan_id: str = "default"
#     plan: Dict[str, Any] = Field(default_factory=dict)

#     # Query expansion
#     expanded_queries: List[ExpandedQuery] = Field(default_factory=list)

#     # Retrieval / ranking
#     retrieved: List[ScoredChunk] = Field(default_factory=list)
#     reranked: List[ScoredChunk] = Field(default_factory=list)
#     filtered: List[FilteredChunk] = Field(default_factory=list)

#     # Prompting / generation
#     packed_context: str = ""
#     prompt: str = ""
#     raw_generation: str|None = None

#     # Post checks / safety
#     postcheck: Dict[str, Any] = Field(default_factory=dict)

#     # Diagnostics
#     timings_ms: Dict[str, float] = Field(default_factory=dict)
#     errors: List[Dict[str, Any]] = Field(default_factory=list)

#     # 스트리밍을 위한 큐 (Pydantic 직렬화에서는 제외)
#     stream_queue: asyncio.Queue|None = Field(default=None, exclude=True)
    
#     class Config:
#         arbitrary_types_allowed = True


# class RagRequest(BaseModel):
#     trace_id: str = Field(..., description="Request-scoped trace id")
#     user_query: str
#     locale: str = "ko-KR"
#     tenant: str|None = None
#     budget: Dict[str, Any]|None = None
#     # Example knobs for planning
#     safety_level: Literal["low", "medium", "high"] = "medium"
#     latency_slo_ms: int|None = None
#     tools_allowed: bool = True

    
# class RagResponse(BaseModel):
#     trace_id: str
#     answer: str
#     citations: List[Citation] = Field(default_factory=list)
#     diagnostics: Dict[str, Any] = Field(default_factory=dict)

# import asyncio
# from typing import Any, Dict, List, Literal, TypeVar
# from pydantic import BaseModel, Field

# TConfig = TypeVar("TConfig", bound=BaseModel)

# class SourceChunk(BaseModel):
#     chunk_id: int
#     source_id: int
#     source_name: str
#     content: str
#     metadata: Dict[str, Any] = Field(default_factory=dict)

# class ScoredChunk(BaseModel):
#     chunk: SourceChunk
#     score: float
#     signals: Dict[str, Any] = Field(default_factory=dict)

# class ExpandedQuery(BaseModel):
#     content: str
#     intent: Literal["original", "keyword", "semantic"]
#     channels: set[Literal["bm25", "tsv", "vector"]] = {}
#     weight: float = 1.0

# class FilteredChunk(BaseModel):
#     chunk: SourceChunk
#     kept: bool
#     reasons: list[str] = []
#     score: float = 0.0

# class EvidenceGroup(BaseModel):
#     group_id: str
#     title: str | None = None
#     chunks: list[SourceChunk]

# class Citation(BaseModel):
#     source_id: int
#     chunk_id: int
#     quote: str|None = None

# class RagContext(BaseModel):
#     # --- Planning & Routing (명시적 플래그로 승격) ---
#     intent: str = "search"
#     skip_retrieval: bool = False
#     skip_reranker: bool = False
    
#     plan_id: str = "default"
#     plan: Dict[str, Any] = Field(default_factory=dict)

#     # --- Query expansion ---
#     expanded_queries: List[ExpandedQuery] = Field(default_factory=list)

#     # --- Retrieval / ranking ---
#     retrieved: List[ScoredChunk] = Field(default_factory=list)
#     reranked: List[ScoredChunk] = Field(default_factory=list)
#     filtered: List[FilteredChunk] = Field(default_factory=list)

#     # Assembly와 Compression 사이에서 데이터를 주고받을 구조화된 컨테이너 (추가!)
#     evidence_groups: List[EvidenceGroup] = Field(default_factory=list)

#     # --- Prompting / generation ---
#     packed_context: str = ""
#     prompt: str = ""
#     raw_generation: str|None = None

#     # --- Post checks / safety ---
#     postcheck: Dict[str, Any] = Field(default_factory=dict)

#     # --- Diagnostics ---
#     timings_ms: Dict[str, float] = Field(default_factory=dict)
#     errors: List[Dict[str, Any]] = Field(default_factory=list)

#     # 스트리밍을 위한 큐 (Pydantic 직렬화에서는 제외)
#     stream_queue: asyncio.Queue|None = Field(default=None, exclude=True)
    
#     # Planner 단계에서 최종 결정된 스트리밍 및 검증 모드 플래그 
#     is_streaming: bool = True
#     strict_validation: bool = False
    
#     class Config:
#         arbitrary_types_allowed = True

# class RagRequest(BaseModel):
#     trace_id: str = Field(..., description="Request-scoped trace id")
#     user_query: str
#     locale: str = "ko-KR"
#     tenant: str|None = None
#     budget: Dict[str, Any]|None = None
#     safety_level: Literal["low", "medium", "high"] = "medium"
#     latency_slo_ms: int|None = None
#     tools_allowed: bool = True
#     # Client에서 스트리밍 / 비스트리밍(콘텐츠 제작)을 요청할 수 있는 진입점. 
#     stream_response: bool = True
    
# class RagResponse(BaseModel):
#     trace_id: str
#     answer: str
#     citations: List[Citation] = Field(default_factory=list)
#     diagnostics: Dict[str, Any] = Field(default_factory=dict)

# import asyncio
# from typing import Any, Dict, List, Literal, TypeVar
# from pydantic import BaseModel, Field

# TConfig = TypeVar("TConfig", bound=BaseModel)

# class SourceChunk(BaseModel):
#     chunk_id: int
#     source_id: int
#     source_name: str
#     content: str
#     metadata: Dict[str, Any] = Field(default_factory=dict)

# class ScoredChunk(BaseModel):
#     chunk: SourceChunk
#     score: float
#     signals: Dict[str, Any] = Field(default_factory=dict)

# class ExpandedQuery(BaseModel):
#     content: str
#     intent: Literal["original", "keyword", "semantic"]
#     channels: set[Literal["bm25", "tsv", "vector"]] = {}
#     weight: float = 1.0

# class FilteredChunk(BaseModel):
#     chunk: SourceChunk
#     kept: bool
#     reasons: list[str] = []
#     score: float = 0.0

# class EvidenceGroup(BaseModel):
#     group_id: str
#     title: str | None = None
#     chunks: list[SourceChunk]

# class Citation(BaseModel):
#     source_id: int
#     chunk_id: int
#     quote: str|None = None

# class RagContext(BaseModel):
#     # --- Planning & Routing ---
#     intent: str = "search"
#     skip_retrieval: bool = False
#     skip_reranker: bool = False
    
#     # 신규: 스트리밍 및 검증 제어 상태 플래그
#     is_streaming: bool = True
#     strict_validation: bool = False
    
#     plan_id: str = "default"
#     plan: Dict[str, Any] = Field(default_factory=dict)

#     # --- Query expansion ---
#     expanded_queries: List[ExpandedQuery] = Field(default_factory=list)

#     # --- Retrieval / ranking ---
#     retrieved: List[ScoredChunk] = Field(default_factory=list)
#     reranked: List[ScoredChunk] = Field(default_factory=list)
#     filtered: List[FilteredChunk] = Field(default_factory=list)

#     # Assembly와 Compression 사이에서 데이터를 주고받을 구조화된 컨테이너
#     evidence_groups: List[EvidenceGroup] = Field(default_factory=list)

#     # --- Prompting / generation ---
#     packed_context: str = ""
#     prompt: str = ""
#     raw_generation: str|None = None

#     # --- Post checks / safety ---
#     postcheck: Dict[str, Any] = Field(default_factory=dict)

#     # --- Diagnostics ---
#     timings_ms: Dict[str, float] = Field(default_factory=dict)
#     errors: List[Dict[str, Any]] = Field(default_factory=list)

#     # 스트리밍을 위한 큐 (Pydantic 직렬화에서는 제외)
#     stream_queue: asyncio.Queue|None = Field(default=None, exclude=True)
    
#     class Config:
#         arbitrary_types_allowed = True

# class RagRequest(BaseModel):
#     trace_id: str = Field(..., description="Request-scoped trace id")
#     user_query: str
#     locale: str = "ko-KR"
#     tenant: str|None = None
#     budget: Dict[str, Any]|None = None
#     safety_level: Literal["low", "medium", "high"] = "medium"
#     latency_slo_ms: int|None = None
#     tools_allowed: bool = True
    
#     # 신규: 클라이언트 측 스트리밍 요청 여부 (기본값 True)
#     stream_response: bool = True 
    
# class RagResponse(BaseModel):
#     trace_id: str
#     answer: str
#     citations: List[Citation] = Field(default_factory=list)
#     diagnostics: Dict[str, Any] = Field(default_factory=dict)

import asyncio
from enum import Enum
from typing import Any, Dict, List, Literal, TypeVar, Optional
from pydantic import BaseModel, Field

TConfig = TypeVar("TConfig", bound=BaseModel)

# --- 신규: 보안 관련 타입 정의 ---
class SecurityStatus(str, Enum):
    SAFE = "safe"
    INJECTION_ATTEMPT = "injection_attempt"
    PII_LEAK = "pii_leak"
    MALICIOUS_QUERY = "malicious_query"

class InputGuardResponse(BaseModel):
    is_safe: bool = True
    status: SecurityStatus = SecurityStatus.SAFE
    reason: Optional[str] = None
    hit_patterns: List[str] = Field(default_factory=list)

# --- 기존 클래스들 유지 ---
class SourceChunk(BaseModel):
    chunk_id: int
    source_id: int
    source_name: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ScoredChunk(BaseModel):
    chunk: SourceChunk
    score: float
    signals: Dict[str, Any] = Field(default_factory=dict)

# class ExpandedQuery(BaseModel):
#     content: str
#     intent: Literal["original", "keyword", "semantic"]
#     channels: set[Literal["bm25", "tsv", "vector"]] = Field(default_factory=set)
#     weight: float = 1.0

class ExpandedQuery(BaseModel):
    content: str
    intent: Literal["original", "keyword", "semantic"]
    # 변경점: default_factory를 통해 기본적으로 bm25, vector 양쪽 모두를 탐색하도록 세팅
    channels: set[Literal["bm25", "tsv", "vector"]] = Field(default_factory=lambda: {"bm25", "vector"})
    weight: float = 1.0

class FilteredChunk(BaseModel):
    chunk: SourceChunk
    kept: bool
    reasons: list[str] = []
    score: float = 0.0

class EvidenceGroup(BaseModel):
    group_id: str
    title: str | None = None
    chunks: list[SourceChunk]

class Citation(BaseModel):
    source_id: int
    chunk_id: int
    quote: str | None = None

class RagContext(BaseModel):
    # --- Planning & Routing ---
    intent: str = "search"
    skip_retrieval: bool = False
    skip_reranker: bool = False
    
    # 신규: 스트리밍 및 검증 제어 상태 플래그
    is_streaming: bool = True
    strict_validation: bool = False
    
    plan_id: str = "default"
    plan: Dict[str, Any] = Field(default_factory=dict)

    # --- 신규: Input Guard 결과 저장 필드 ---
    input_guard: InputGuardResponse = Field(default_factory=InputGuardResponse)

    # --- Query expansion ---
    expanded_queries: List[ExpandedQuery] = Field(default_factory=list)

    # --- Retrieval / ranking ---
    retrieved: List[ScoredChunk] = Field(default_factory=list)
    reranked: List[ScoredChunk] = Field(default_factory=list)
    filtered: List[FilteredChunk] = Field(default_factory=list)

    # Assembly와 Compression 사이에서 데이터를 주고받을 구조화된 컨테이너
    evidence_groups: List[EvidenceGroup] = Field(default_factory=list)

    # --- Prompting / generation ---
    packed_context: str = ""
    prompt: str = ""
    raw_generation: str | None = None

    # --- Post checks / safety ---
    postcheck: Dict[str, Any] = Field(default_factory=dict)

    # --- Diagnostics ---
    timings_ms: Dict[str, float] = Field(default_factory=dict)
    errors: List[Dict[str, Any]] = Field(default_factory=list)

    # 스트리밍을 위한 큐 (Pydantic 직렬화에서는 제외)
    stream_queue: asyncio.Queue | None = Field(default=None, exclude=True)
    
    class Config:
        arbitrary_types_allowed = True

class RagRequest(BaseModel):
    trace_id: str = Field(..., description="Request-scoped trace id")
    user_query: str
    locale: str = "ko-KR"
    tenant: str | None = None
    budget: Dict[str, Any] | None = None
    safety_level: Literal["low", "medium", "high"] = "medium"
    latency_slo_ms: int | None = None
    tools_allowed: bool = True
    
    # 신규: 클라이언트 측 스트리밍 요청 여부 (기본값 True)
    stream_response: bool = True 
    
class RagResponse(BaseModel):
    trace_id: str
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)