from typing import Any, Dict, List, Literal, TypeVar
from pydantic import BaseModel, Field


TConfig = TypeVar("TConfig", bound=BaseModel)


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
    channels: set[Literal["bm25", "tsv", "vector"]] = {}
    weight: float = 1.0


class FilteredChunk(BaseModel):
    chunk: SourceChunk
    kept: bool
    reasons: list[str] = []


class EvidenceGroup(BaseModel):
    group_id: str
    title: str | None = None
    chunks: list[SourceChunk]


class Citation(BaseModel):
    source_id: int
    chunk_id: int
    quote: str|None = None


class RagContext(BaseModel):
    # Planning
    plan_id: str = "default"
    plan: Dict[str, Any] = Field(default_factory=dict)

    # Query expansion
    expanded_queries: List[ExpandedQuery] = Field(default_factory=list)

    # Retrieval / ranking
    retrieved: List[ScoredChunk] = Field(default_factory=list)
    reranked: List[ScoredChunk] = Field(default_factory=list)
    filtered: List[FilteredChunk] = Field(default_factory=list)

    # Prompting / generation
    packed_context: str = ""
    prompt: str = ""
    raw_generation: str|None = None

    # Post checks / safety
    postcheck: Dict[str, Any] = Field(default_factory=dict)

    # Diagnostics
    timings_ms: Dict[str, float] = Field(default_factory=dict)
    errors: List[Dict[str, Any]] = Field(default_factory=list)


class RagRequest(BaseModel):
    trace_id: str = Field(..., description="Request-scoped trace id")
    user_query: str
    locale: str = "ko-KR"
    tenant: str|None = None
    budget: Dict[str, Any]|None = None
    # Example knobs for planning
    safety_level: Literal["low", "medium", "high"] = "medium"
    latency_slo_ms: int|None = None
    tools_allowed: bool = True

    
class RagResponse(BaseModel):
    trace_id: str
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)