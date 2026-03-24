import os
import json
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.rag.core.interfaces import RagPlanner
from src.common.logger import get_logger

logger = get_logger(__name__)

class CloudSlmPlanner(RagPlanner):
    def __init__(self, model_name: str = "meta-llama/llama-3-8b-instruct"):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY가 설정되지 않았습니다. Planner가 정상 동작하지 않을 수 있습니다.")
            
        self.model_name = model_name
        
        self.llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            model=self.model_name,
            temperature=0.0,
            max_tokens=150,
            model_kwargs={"response_format": {"type": "json_object"}} 
        )

    async def forward(self, query: str) -> Dict[str, Any]:
        prompt = f"""
        당신은 사용자의 질문 의도를 분석하는 라우팅 시스템입니다.
        아래 질문을 분석하여 반드시 JSON 포맷으로만 응답하세요.

        분류 기준:
        1. intent: "search" (지식 검색 필요) | "chitchat" (단순 인사/대화) 
        2. requires_db: true (DB 검색 필수) | false (DB 검색 불필요)
        3. complexity: "low" (간단한 답변) | "high" (복잡한 추론 필요)

        [사용자 질문]: {query}
        """
        
        try:
            res = await self.llm.ainvoke([HumanMessage(content=prompt)])
            plan = json.loads(res.content)
            logger.info(f"Planner 분석 결과: {plan}")
            return plan
            
        except json.JSONDecodeError:
            logger.error("Planner가 유효한 JSON을 반환하지 않았습니다.")
            return {"intent": "search", "requires_db": True, "complexity": "high"}
        except Exception as e:
            logger.error(f"Planner 실행 중 에러 발생: {e}")
            return {"intent": "search", "requires_db": True, "complexity": "high"}