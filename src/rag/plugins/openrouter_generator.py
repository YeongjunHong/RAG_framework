import asyncio # 스트리밍을 위해 추가 
import os
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.rag.core.interfaces import RagGenerator
from src.common.logger import get_logger

logger = get_logger(__name__)

class OpenRouterGenerator(RagGenerator):
    def __init__(self, default_model: str = "google/gemini-2.5-flash"):
        self.default_model = default_model
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY 환경 변수가 없습니다.")

    # async def forward(self, prompt: Any, model: str | None = None) -> str:
    # 호출부(generator stage)에서 queue를 넘겨주도록 인터페이스를 확장
    async def forward(self, prompt: Any, model: str | None = None, stream_queue: asyncio.Queue | None = None) -> str:
        target_model = model or self.default_model
        logger.info(f"OpenRouter LLM 호출 중... (모델: {target_model})")
        
        try:
            llm = ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                model=target_model,
                temperature=0.1,
                max_tokens=2048,
                streaming=True, # 스트리밍 활성화
                timeout=30.0    # 안정성을 위한 타임아웃 추가
            )
            
            # 문자열이 들어오면 LangChain 메시지 규격으로 변환
            messages = [HumanMessage(content=str(prompt))] if isinstance(prompt, str) else prompt

            full_content = ""
            # 스트리밍 출력
            async for chunk in llm.astream(messages):
                token = chunk.content
                full_content += token
                if stream_queue:
                    await stream_queue.put(token)
            
            # 종료 시그널 전송 (중요)
            if stream_queue:
                await stream_queue.put(None)
                
            return full_content
            
            # response = await llm.ainvoke(messages)
            # return str(response.content)
            
        except Exception as e:
            logger.error(f"OpenRouter 생성 중 에러 발생: {e}")
            # return "죄송합니다. 답변을 생성하는 중 오류가 발생했습니다."
            err_msg = "답변을 생성하는 중 오류가 발생했습니다."
            if stream_queue:
                await stream_queue.put(err_msg)
                await stream_queue.put(None)
            return err_msg