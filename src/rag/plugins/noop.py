from typing import List, Dict, Any

from src.rag.core.types import ScoredChunk
from src.rag.core.interfaces import RagReranker, RagPostChecker


class NoopReranker(RagReranker):
    async def forward(self, *, query: str, candidates: List[ScoredChunk], top_k: int) -> List[ScoredChunk]:
        # Assume candidates are already scored; just take top_k.
        items = sorted(candidates, key=lambda x: x.score, reverse=True)
        return items[:top_k]

## post-check 데모를 위한 추가
class NoopPostChecker(RagPostChecker):
    # forward 로 이름 변경
    async def forward(self, context: str, generation: str | None) -> Dict[str, Any]:
        return {
            "is_valid": True,
            "reason": "Guardrails bypassed (Noop)",
            "error_type": None
        }