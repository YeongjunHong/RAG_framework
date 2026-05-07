import asyncio
from enum import Enum
from typing import Any, Dict, List, Literal, TypeVar, Optional
from pydantic import BaseModel, Field

TConfig = TypeVar("TConfig", bound=BaseModel)

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

class ExpandedQuery(BaseModel):
    content: str
    intent: Literal["original", "keyword", "semantic"]
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

# [NEW] 의도를 엄격하게 제어하기 위한 Enum
class QueryIntent(str, Enum):
    CHITCHAT = "chitchat"
    SIMPLE_SEARCH = "simple_search"
    COMPLEX_MATH_SOLVING = "complex_math_solving"
    AUTHORING = "authoring"
    SECURITY_VIOLATION = "security_violation"
    CACHE_HIT = "cache_hit"
    UNKNOWN = "unknown"

class RagContext(BaseModel):
    # [MODIFIED] Enum 적용으로 파편화 방지
    intent: QueryIntent = QueryIntent.UNKNOWN
    
    skip_retrieval: bool = False
    skip_reranker: bool = False
    
    is_streaming: bool = True
    strict_validation: bool = False
    
    plan_id: str = "default"
    plan: Dict[str, Any] = Field(default_factory=dict)

    input_guard: InputGuardResponse = Field(default_factory=InputGuardResponse)

    expanded_queries: List[ExpandedQuery] = Field(default_factory=list)

    retrieved: List[ScoredChunk] = Field(default_factory=list)
    reranked: List[ScoredChunk] = Field(default_factory=list)
    filtered: List[FilteredChunk] = Field(default_factory=list)

    evidence_groups: List[EvidenceGroup] = Field(default_factory=list)

    packed_context: str = ""
    prompt: str = ""
    raw_generation: str | None = None

    postcheck: Dict[str, Any] = Field(default_factory=dict)

    timings_ms: Dict[str, float] = Field(default_factory=dict)
    errors: List[Dict[str, Any]] = Field(default_factory=list)

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
    
    stream_response: bool = True 
    
class RagResponse(BaseModel):
    trace_id: str
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)