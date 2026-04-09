import os
import asyncio
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.common.logger import get_logger
# 수정: 존재하지 않는 RagPlugin 대신 우리가 정의한 RagTextCompressor 임포트
from src.rag.core.interfaces import RagTextCompressor

logger = get_logger(__name__)

# 수정: RagTextCompressor 인터페이스 상속
class SLMTextCompressorPlugin(RagTextCompressor):
    def __init__(self, model_name: str = "meta-llama/llama-3-8b-instruct"):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model_name = model_name
        
        # 압축 작업은 창의성이 필요 없으므로 temperature=0으로 고정
        self.llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            model=self.model_name,
            temperature=0.0,
            max_tokens=500
        )

    async def _compress_single_chunk(self, text: str) -> str:
        """단일 텍스트를 밀도 있게 압축"""
        prompt = f"""
        당신은 텍스트 압축기입니다. 다음 텍스트에서 불필요한 조사, 부사, 수식어, 인사말을 모두 제거하고, 
        명사, 동사, 고유명사, 수치(Entity) 등 핵심 정보만 남겨서 텍스트의 길이를 절반 이하로 압축하세요.
        문법이 조금 어색해져도 좋으니 정보의 손실 없이 최대한 짧게 요약식(개조식)으로 작성하세요.

        [원본 텍스트]
        {text}
        
        [압축된 텍스트]:
        """
        try:
            res = await self.llm.ainvoke([HumanMessage(content=prompt)])
            compressed = res.content.strip()
            # 비정상적으로 압축 실패(오히려 길어지거나 빈 문자열) 시 원본 반환 (Fail-safe)
            if not compressed or len(compressed) > len(text):
                return text
            return compressed
        except Exception as e:
            logger.error(f"[TextCompressor] 텍스트 압축 중 에러 발생: {e}")
            return text

    async def forward(self, texts: List[str]) -> List[str]:
        """비동기 병렬로 여러 청크를 동시에 압축"""
        if not texts:
            return []
            
        logger.info(f"[TextCompressor] {len(texts)}개의 청크에 대해 병렬 압축을 시작합니다.")
        
        # Retrieval 때 썼던 비동기 병렬 처리(Gather)를 여기서도 똑같이 적용
        tasks = [self._compress_single_chunk(text) for text in texts]
        compressed_texts = await asyncio.gather(*tasks, return_exceptions=False)
        
        return compressed_texts