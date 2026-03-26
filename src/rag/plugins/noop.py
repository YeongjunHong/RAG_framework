from typing import List

from src.rag.core.types import ScoredChunk
from src.rag.core.interfaces import RagReranker


class NoopReranker(RagReranker):
    async def forward(self, *, query: str, candidates: List[ScoredChunk], top_k: int) -> List[ScoredChunk]:
        # Assume candidates are already scored; just take top_k.
        items = sorted(candidates, key=lambda x: x.score, reverse=True)
        return items[:top_k]
