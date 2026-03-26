# import asyncio
# from typing import List
# from sentence_transformers import CrossEncoder
# from src.rag.core.types import ScoredChunk
# from src.rag.core.interfaces import RagReranker
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class LocalCrossEncoderReranker(RagReranker):
#     def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
#         logger.info(f"Reranker 모델({model_name}) 로드 중... (초기 1회는 다운로드로 인해 시간이 걸릴 수 있습니다)")
#         # CrossEncoder 로드 (CPU 환경 기준, GPU가 있다면 device='cuda' 옵션 추가)
#         self.model = CrossEncoder(model_name, max_length=512, activation_fn=None)
#         logger.info("Reranker 로드 완료!")

#     async def forward(self, *, query: str, candidates: List[ScoredChunk], top_k: int) -> List[ScoredChunk]:
#         if not candidates:
#             return []

#         # 1. 모델에 넣을 (질문, 문서내용) 쌍의 리스트
#         sentence_pairs = [[query, doc.chunk.content] for doc in candidates]

#         # 2. Cross-Encoder로 문맥 유사도를 정밀 채점
#         # scores = self.model.predict(sentence_pairs)
#         scores = await asyncio.to_thread(self.model.predict, sentence_pairs)

#         # 3. 기존 객체에 새로운 점수를 부여하고 정렬
#         for i, doc in enumerate(candidates):
#             # 원래 DB에서 가져온 점수(retrieval_score)는 백업
#             doc.signals['retrieval_score'] = doc.score 
#             doc.score = float(scores[i])

#         # 4. 점수가 높은 순으로 정렬하여 top_k 개만 잘라서 반환
#         reranked_candidates = sorted(candidates, key=lambda x: x.score, reverse=True)
#         return reranked_candidates[:top_k]

import asyncio
import numpy as np
from typing import List
from sentence_transformers import CrossEncoder

from src.rag.core.types import ScoredChunk
from src.rag.core.interfaces import RagReranker
from src.common.logger import get_logger

logger = get_logger(__name__)

class LocalCrossEncoderReranker(RagReranker):
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        logger.info(f"Reranker 모델({model_name}) 로드 중... (초기 1회는 다운로드로 인해 시간이 걸릴 수 있습니다)")
        # activation_fn=None으로 로짓 값을 그대로 받은 뒤, 우리가 직접 제어함
        self.model = CrossEncoder(model_name, max_length=512, activation_fn=None)
        logger.info("Reranker 로드 완료!")

    async def forward(self, *, query: str, candidates: List[ScoredChunk], top_k: int) -> List[ScoredChunk]:
        if not candidates:
            return []

        # 1. 모델에 넣을 (질문, 문서내용) 쌍의 리스트
        sentence_pairs = [[query, doc.chunk.content] for doc in candidates]

        # 2. Cross-Encoder로 문맥 유사도를 정밀 채점 (Raw Logits 1D Array 반환)
        logits = await asyncio.to_thread(self.model.predict, sentence_pairs)

        # 3. Sigmoid 정규화 적용 (Numpy 벡터 연산으로 0~1 사이 값으로 변환)
        scores = 1 / (1 + np.exp(-logits))

        # 4. 기존 객체에 새로운 확률 점수를 부여
        for i, doc in enumerate(candidates):
            doc.signals['retrieval_score'] = doc.score 
            doc.score = float(scores[i])

        # 5. 점수가 높은 순으로 정렬하여 top_k 개만 잘라서 반환
        reranked_candidates = sorted(candidates, key=lambda x: x.score, reverse=True)
        return reranked_candidates[:top_k]