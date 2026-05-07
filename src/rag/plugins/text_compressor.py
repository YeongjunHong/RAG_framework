

import asyncio
from typing import List
from src.common.logger import get_logger
from src.rag.core.interfaces import RagTextCompressor

logger = get_logger(__name__)

class PassThroughCompressorPlugin(RagTextCompressor):
    """
    한국어 문맥 훼손 방지를 위해 물리적 텍스트 압축을 수행하지 않고 
    Reranker와 Filter를 통과한 원본 청크를 그대로 Generator에 넘기는 Bypass 플러그인
    """
    def __init__(self):
        logger.info("[TextCompressor] 한국어 문맥 보존을 위해 압축을 생략(Bypass)합니다.")

    async def forward(self, texts: List[str]) -> List[str]:
        if not texts:
            return []
            
        logger.info(f"[TextCompressor] {len(texts)}개의 청크를 원본 상태로 유지하여 통과시킵니다.")
        # 아무런 변형 없이 원본 텍스트 리스트를 그대로 반환
        return texts