import os
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.rag.core.interfaces import RagGenerator
from src.common.logger import get_logger

logger = get_logger(__name__)

class OpenRouterGenerator(RagGenerator):
    def __init__(self, default_model: str = "google/gemma-3-27b-it:free"):
        self.default_model = default_model
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY 환경 변수가 없습니다.")

    async def forward(self, prompt: Any, model: str | None = None) -> str:
        target_model = model or self.default_model
        logger.info(f"OpenRouter LLM 호출 중... (모델: {target_model})")
        
        try:
            llm = ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                model=target_model,
                temperature=0.1,
                max_tokens=2048
            )
            
            # 문자열이 들어오면 LangChain 메시지 규격으로 변환
            messages = [HumanMessage(content=str(prompt))] if isinstance(prompt, str) else prompt
            
            response = await llm.ainvoke(messages)
            return str(response.content)
            
        except Exception as e:
            logger.error(f"OpenRouter 생성 중 에러 발생: {e}")
            return "죄송합니다. 답변을 생성하는 중 오류가 발생했습니다."