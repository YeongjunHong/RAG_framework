from typing import List, Sequence

from src.rag.core.types import SourceChunk, ScoredChunk
from src.rag.core.interfaces import RagRetriever


class InMemoryRetriever(RagRetriever):
    """Local-only retriever for tests and offline runs."""

    def __init__(self, chunks: List[SourceChunk]=[]):
        self._chunks = chunks

    async def forward(
        self,
        *,
        queries: Sequence[str],
        top_k: int,
        bm25_weight: float,
        vector_weight: float,
        filters: dict = None, # 여기도 추가
    ) -> List[ScoredChunk]:
        # Very naive: keyword containment scoring.
        q = " ".join(queries).lower()
        out: List[ScoredChunk] = []
        for ch in self._chunks:
            score = 0.0
            if q and q in ch.content.lower():
                score = 1.0
            out.append(ScoredChunk(chunk=ch, score=score))
        out.sort(key=lambda x: x.score, reverse=True)
        return out[:top_k]
