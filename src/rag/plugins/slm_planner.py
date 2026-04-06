# import os
# import json
# from typing import Dict, Any
# from langchain_openai import ChatOpenAI
# from langchain_core.messages import HumanMessage

# from src.rag.core.interfaces import RagPlanner
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class CloudSlmPlanner(RagPlanner):
#     def __init__(self, model_name: str = "meta-llama/llama-3-8b-instruct"):
#         self.api_key = os.getenv("OPENROUTER_API_KEY")
#         if not self.api_key:
#             logger.warning("OPENROUTER_API_KEY가 설정되지 않았습니다. Planner가 정상 동작하지 않을 수 있습니다.")
            
#         self.model_name = model_name
        
#         self.llm = ChatOpenAI(
#             base_url="https://openrouter.ai/api/v1",
#             api_key=self.api_key,
#             model=self.model_name,
#             temperature=0.0,
#             max_tokens=150,
#             model_kwargs={"response_format": {"type": "json_object"}} 
#         )

#     async def forward(self, query: str) -> Dict[str, Any]:
#         prompt = f"""
#         당신은 사용자의 질문 의도를 분석하는 라우팅 시스템입니다.
#         아래 질문을 분석하여 반드시 JSON 포맷으로만 응답하세요.

#         분류 기준:
#         1. intent: "search" (지식 검색 필요) | "chitchat" (단순 인사/대화) 
#         2. requires_db: true (DB 검색 필수) | false (DB 검색 불필요)
#         3. complexity: "low" (간단한 답변) | "high" (복잡한 추론 필요)

#         [사용자 질문]: {query}
#         """
        
#         try:
#             res = await self.llm.ainvoke([HumanMessage(content=prompt)])
#             plan = json.loads(res.content)
#             logger.info(f"Planner 분석 결과: {plan}")
#             return plan
            
#         except json.JSONDecodeError:
#             logger.error("Planner가 유효한 JSON을 반환하지 않았습니다.")
#             return {"intent": "search", "requires_db": True, "complexity": "high"}
#         except Exception as e:
#             logger.error(f"Planner 실행 중 에러 발생: {e}")
#             return {"intent": "search", "requires_db": True, "complexity": "high"}

#내일 데모

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
            temperature=0.0,  # 라우팅은 창의성보다 일관성이 중요하므로 0.0 유지
            max_tokens=150,
            model_kwargs={"response_format": {"type": "json_object"}} 
        )

    async def forward(self, query: str) -> Dict[str, Any]:
        # 파이썬 f-string에서 JSON 괄호를 표현하기 위해 {{ }} 사용
        prompt = f"""
        당신은 금융/정책 RAG 파이프라인의 시맨틱 라우터입니다.
        사용자의 질문을 분석하여 반드시 JSON 포맷으로만 응답하세요.

        [분류 기준]
        1. intent: 
           - "chitchat": 인사, 감정 표현 등 지식 검색이 필요 없는 일상 대화
           - "simple_search": 전화번호, 운영시간, 주소, 위치 등 단답형 팩트 검색
           - "search": 원리 설명, 장단점 분석, 영향 등 복잡한 문서 검토와 추론이 필요한 일반 질문
           - "authoring": 교육 자료, 리포트, 가이드 문서 작성 등 정보의 100% 무결성과 엄격한 검증이 요구되는 생성 작업
        2. requires_db: true (DB 검색 필수) | false (DB 검색 불필요)
        3. complexity: "low" (간단한 답변) | "high" (복잡한 추론 필요)
        4. strict_validation: true (환각 절대 불가, 엄격한 검증) | false (일반적인 유연한 답변)

        [출력 예시]
        User: 안녕하세요. 오늘 날씨 좋네요.
        Assistant: {{"intent": "chitchat", "requires_db": false, "complexity": "low", "strict_validation": false}}

        User: 국민카드 고객센터 운영시간 언제부터야?
        Assistant: {{"intent": "simple_search", "requires_db": true, "complexity": "low", "strict_validation": false}}

        User: 금리 인상이 부동산 대출에 미치는 영향을 설명해줘.
        Assistant: {{"intent": "search", "requires_db": true, "complexity": "high", "strict_validation": false}}

        User: 제공된 문서들을 바탕으로 신입사원을 위한 금융 보안 가이드 문서를 작성해줘.
        Assistant: {{"intent": "authoring", "requires_db": true, "complexity": "high", "strict_validation": true}}

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