# import os
# import asyncio
# from typing import List
# from langchain_openai import ChatOpenAI
# from langchain_core.messages import HumanMessage

# from src.common.logger import get_logger
# # 수정: 존재하지 않는 RagPlugin 대신 우리가 정의한 RagTextCompressor 임포트
# from src.rag.core.interfaces import RagTextCompressor

# logger = get_logger(__name__)

# # 수정: RagTextCompressor 인터페이스 상속
# class SLMTextCompressorPlugin(RagTextCompressor):
#     def __init__(self, model_name: str = "meta-llama/llama-3-8b-instruct"):
#         self.api_key = os.getenv("OPENROUTER_API_KEY")
#         self.model_name = model_name
        
#         # 압축 작업은 창의성이 필요 없으므로 temperature=0으로 고정
#         self.llm = ChatOpenAI(
#             base_url="https://openrouter.ai/api/v1",
#             api_key=self.api_key,
#             model=self.model_name,
#             temperature=0.0,
#             max_tokens=500
#         )

#     async def _compress_single_chunk(self, text: str) -> str:
#         """단일 텍스트를 밀도 있게 압축"""
#         prompt = f"""
#         당신은 텍스트 압축기입니다. 다음 텍스트에서 불필요한 조사, 부사, 수식어, 인사말을 모두 제거하고, 
#         명사, 동사, 고유명사, 수치(Entity) 등 핵심 정보만 남겨서 텍스트의 길이를 절반 이하로 압축하세요.
#         문법이 조금 어색해져도 좋으니 정보의 손실 없이 최대한 짧게 요약식(개조식)으로 작성하세요.

#         [원본 텍스트]
#         {text}
        
#         [압축된 텍스트]:
#         """
#         try:
#             res = await self.llm.ainvoke([HumanMessage(content=prompt)])
#             compressed = res.content.strip()
#             # 비정상적으로 압축 실패(오히려 길어지거나 빈 문자열) 시 원본 반환 (Fail-safe)
#             if not compressed or len(compressed) > len(text):
#                 return text
#             return compressed
#         except Exception as e:
#             logger.error(f"[TextCompressor] 텍스트 압축 중 에러 발생: {e}")
#             return text

#     async def forward(self, texts: List[str]) -> List[str]:
#         """비동기 병렬로 여러 청크를 동시에 압축"""
#         if not texts:
#             return []
            
#         logger.info(f"[TextCompressor] {len(texts)}개의 청크에 대해 병렬 압축을 시작합니다.")
        
#         # Retrieval 때 썼던 비동기 병렬 처리(Gather)를 여기서도 똑같이 적용
#         tasks = [self._compress_single_chunk(text) for text in texts]
#         compressed_texts = await asyncio.gather(*tasks, return_exceptions=False)
        
#         return compressed_texts
# import asyncio
# from typing import List
# from llmlingua import PromptCompressor

# from src.common.logger import get_logger
# from src.rag.core.interfaces import RagTextCompressor

# logger = get_logger(__name__)

# class LLMLinguaCompressorPlugin(RagTextCompressor):
#     def __init__(self, target_token_ratio: float = 0.5):
#         self.target_token_ratio = target_token_ratio
#         logger.info("[TextCompressor] LLMLingua-2 로드 중...")
        
#         self.compressor = PromptCompressor(
#             model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank", 
#             use_llmlingua2=True,  # 핵심: 인코더 기반 토큰 분류 파이프라인 활성화
#             device_map="cpu"
#         )

#     async def forward(self, texts: List[str]) -> List[str]:
#         if not texts:
#             return []
            
#         logger.info(f"[TextCompressor] {len(texts)}개의 청크에 대해 LLMLingua 개별 병렬 압축 시작.")
        
#         def compress_single(text: str) -> str:
#             try:
#                 # 단일 청크가 512토큰을 넘는 경우를 대비한 안전장치 (Truncation)
#                 safe_text = " ".join(text.split()[:350])
                
#                 # LLMLingua-2는 instruction/question 불필요
#                 res = self.compressor.compress_prompt(
#                     safe_text,
#                     target_token=int(len(safe_text.split()) * self.target_token_ratio)
#                 )
#                 return res.get("compressed_prompt", safe_text)
#             except Exception as e:
#                 logger.error(f"[TextCompressor] 단일 청크 압축 실패 (원본 유지): {e}")
#                 return text

#         # 백그라운드 스레드에서 병렬(Scatter-Gather) 실행
#         tasks = [asyncio.to_thread(compress_single, t) for t in texts]
#         compressed_texts = await asyncio.gather(*tasks)
        
#         return [text.strip() for text in compressed_texts if text.strip()]


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