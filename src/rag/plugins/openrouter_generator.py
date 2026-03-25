# import asyncio # 스트리밍을 위해 추가 
# import os
# from typing import Any
# from langchain_openai import ChatOpenAI
# from langchain_core.messages import HumanMessage

# from src.rag.core.interfaces import RagGenerator
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class OpenRouterGenerator(RagGenerator):
#     def __init__(self, default_model: str = "google/gemini-2.5-flash"):
#         self.default_model = default_model
#         self.api_key = os.getenv("OPENROUTER_API_KEY")
        
#         if not self.api_key:
#             logger.warning("OPENROUTER_API_KEY 환경 변수가 없습니다.")

#     # async def forward(self, prompt: Any, model: str | None = None) -> str:
#     # 호출부(generator stage)에서 queue를 넘겨주도록 인터페이스를 확장
#     async def forward(self, prompt: Any, model: str | None = None, stream_queue: asyncio.Queue | None = None) -> str:
#         target_model = model or self.default_model
#         logger.info(f"OpenRouter LLM 호출 중... (모델: {target_model})")
        
#         try:
#             llm = ChatOpenAI(
#                 base_url="https://openrouter.ai/api/v1",
#                 api_key=self.api_key,
#                 model=target_model,
#                 temperature=0.1,
#                 max_tokens=2048,
#                 streaming=True, # 스트리밍 활성화
#                 timeout=30.0    # 안정성을 위한 타임아웃 추가
#             )
            
#             # 문자열이 들어오면 LangChain 메시지 규격으로 변환
#             messages = [HumanMessage(content=str(prompt))] if isinstance(prompt, str) else prompt

#             full_content = ""
#             # 스트리밍 출력
#             async for chunk in llm.astream(messages):
#                 token = chunk.content
#                 full_content += token
#                 if stream_queue:
#                     await stream_queue.put(token)
            
#             # 종료 시그널 전송 (중요)
#             if stream_queue:
#                 await stream_queue.put(None)
                
#             return full_content
            
#             # response = await llm.ainvoke(messages)
#             # return str(response.content)
            
#         except Exception as e:
#             logger.error(f"OpenRouter 생성 중 에러 발생: {e}")
#             # return "죄송합니다. 답변을 생성하는 중 오류가 발생했습니다."
#             err_msg = "답변을 생성하는 중 오류가 발생했습니다."
#             if stream_queue:
#                 await stream_queue.put(err_msg)
#                 await stream_queue.put(None)
#             return err_msg

# Fallback(대체 모델 호출) 로직 추가 0325

import asyncio
import os
from typing import Any, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.rag.core.interfaces import RagGenerator
from src.common.logger import get_logger

logger = get_logger(__name__)

class OpenRouterGenerator(RagGenerator):
    def __init__(self, default_model: str = "google/gemini-2.5-flash", fallback_models: List[str] = None):
        self.default_model = default_model
        # 메인 모델 실패 시 시도할 Fallback 모델 파이프라인 구성
        self.fallback_models = fallback_models or ["openai/gpt-4o-mini", "anthropic/claude-3-haiku"]
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY 환경 변수가 없습니다.")

    async def forward(self, prompt: Any, model: str | None = None, stream_queue: asyncio.Queue | None = None) -> str:
        primary_model = model or self.default_model
        models_to_try = [primary_model] + self.fallback_models # 메인 모델 실패 시 지정된 경량/안정성 높은 모델로 자동 전환
        
        messages = [HumanMessage(content=str(prompt))] if isinstance(prompt, str) else prompt

        for current_model in models_to_try:
            logger.info(f"OpenRouter LLM 호출 시도 중... (모델: {current_model})")
            
            try:
                llm = ChatOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.api_key,
                    model=current_model,
                    temperature=0.1,
                    max_tokens=2048,
                    streaming=True,
                    timeout=30.0
                )
                
                full_content = ""
                chunk_count =  0 

                '''
                토큰이 이미 프론트로 흘러간 상태(chunk_count > 0)에서 터지면 억지로 재시도하지 않고 에러를 명시한 뒤 스트림을 닫도록 방어 로직
                '''
                
                async for chunk in llm.astream(messages):
                    token = chunk.content
                    full_content += token
                    chunk_count += 1
                    if stream_queue:
                        await stream_queue.put(token)
                
                # 성공적으로 스트리밍 완료
                if stream_queue:
                    await stream_queue.put(None)
                    
                return full_content
                
            except Exception as e:
                logger.warning(f"모델 {current_model} 생성 실패: {e}")
                
                # 스트리밍 도중(토큰이 이미 전송된 후) 실패한 경우의 방어 로직
                if chunk_count > 0:
                    logger.error("스트리밍 도중 연결이 끊어졌습니다. 무결성을 위해 Fallback을 중단합니다.")
                    err_msg = "\n[네트워크 오류로 인해 답변이 중단되었습니다.]"
                    if stream_queue:
                        await stream_queue.put(err_msg)
                        await stream_queue.put(None)
                    return full_content + err_msg
                
                # chunk_count가 0이라면 (연결 실패, rate limit 등) 다음 모델로 조용히 Fallback 진행
                continue
        
        # 설정된 모든 모델이 실패한 경우 (최종 에러 처리)
        logger.error("모든 Fallback 모델 호출에 실패했습니다.")
        final_err_msg = "답변을 생성하는 중 서버 오류가 발생했습니다."
        
        if stream_queue:
            await stream_queue.put(final_err_msg)
            await stream_queue.put(None)
            
        return final_err_msg