from abc import ABC, abstractmethod
import asyncio  # 추가
from typing import List, Sequence, Generic, TypeVar, Any
import time

from .types import ScoredChunk, ExpandedQuery, FilteredChunk, EvidenceGroup, RagRequest, RagContext, TConfig


TInterface = TypeVar("TInterface", bound=ABC)


class RagQueryExpander(ABC):
    @abstractmethod
    async def forward(self) -> List[ExpandedQuery]:
        raise NotImplementedError


class RagRetriever(ABC):
    """Retrieval port for hybrid search (BM25 + vector + FTS)."""
    @abstractmethod
    async def forward(self, *, queries: Sequence[Any], top_k: int, bm25_weight: float, vector_weight: float, filters: dict = None) -> List[ScoredChunk]:
    # 동적 메타데이터 필터링을 위해 filters 인자 추가 ; jules
        raise NotImplementedError


class RagReranker(ABC):
    @abstractmethod
    async def forward(self, *, query: str, candidates: List[ScoredChunk], top_k: int) -> List[ScoredChunk]:
        raise NotImplementedError


class RagFilterer(ABC):
    @abstractmethod
    async def forward(self) -> List[FilteredChunk]:
        raise NotImplementedError


class RagAssembler(ABC):
    @abstractmethod
    async def forward(self) -> List[EvidenceGroup]:
        raise NotImplementedError


class RagCompressor(ABC):
    @abstractmethod
    async def forward(self) -> List[EvidenceGroup]:
        raise NotImplementedError


class RagPacker(ABC):
    @abstractmethod
    async def forward(self) -> List[EvidenceGroup]:
        raise NotImplementedError

class RagPromptMaker(ABC):
    @abstractmethod
    async def forward(self) -> List[EvidenceGroup]:
        raise NotImplementedError

    
# class RagGenerator(ABC):
#     """Generator/Router port (OpenRouter / other routers / local)."""

#     @abstractmethod
#     async def forward(self, *, prompt: str, model: str|None=None) -> str:
#         raise NotImplementedError

class RagGenerator(ABC):
    """Generator/Router port (OpenRouter / other routers / local)."""

    @abstractmethod
    async def forward(
        self, 
        *, 
        prompt: str, 
        model: str | None = None, 
        stream_queue: asyncio.Queue | None = None  # 추가된 부분
    ) -> str:
        raise NotImplementedError
    

class RagPostChecker(ABC):
    @abstractmethod
    async def forward(self) -> List[EvidenceGroup]:
        raise NotImplementedError


class Tracer(ABC):
    """Minimal tracing abstraction to avoid hard dependency in core."""

    @abstractmethod
    def span(self, name: str, **attrs):
        """Return a context manager."""
        raise NotImplementedError


class RagStage(ABC, Generic[TConfig]):
    """Framework-agnostic async step.

    Contract:
    - Input: RagRequest + RagContext
    - Output: updated RagContext (immutable-by-convention, but we allow mutation for speed)
    """

    name: str

    def __init__(self, config: TConfig):
        self.config = config

    async def __call__(self, request: RagRequest, ctx: RagContext) -> RagContext:
        t0 = time.perf_counter()
        try:
            out = await self.run(request, ctx)
            return out
        except Exception as e:
            ctx.errors.append({"step": self.name, "error": repr(e)})
            raise
        finally:
            dt = (time.perf_counter() - t0) * 1000.0
            ctx.timings_ms[self.name] = dt

    @abstractmethod
    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        raise NotImplementedError