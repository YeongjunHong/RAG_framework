import os
import httpx
from typing import Optional

from src.rag.core.interfaces import RagGenerator
from src.common.logger import get_logger

logger = get_logger(__name__)

class OpenRouterGenerator(RagGenerator):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.default_model = "google/gemini-2.5-flash-lite"

    async def forward(self, prompt: str, model: Optional[str] = None) -> str:
        target_model = model if model else self.default_model
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": target_model,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                
                return result["choices"][0]["message"]["content"]
                    
        except Exception as e:
            logger.error(f"OpenRouter LLM 호출 실패: {e}")
            return "죄송합니다. 답변을 생성하는 과정에서 일시적인 오류가 발생했습니다."