
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
#             temperature=0.0,  # 라우팅은 창의성보다 일관성이 중요하므로 0.0 유지
#             max_tokens=150,
#             model_kwargs={"response_format": {"type": "json_object"}} 
#         )

#     async def forward(self, query: str) -> Dict[str, Any]:
#         # 파이썬 f-string에서 JSON 괄호를 표현하기 위해 {{ }} 사용
#         prompt = f"""
#         당신은 금융/정책 RAG 파이프라인의 시맨틱 라우터입니다.
#         사용자의 질문을 분석하여 반드시 JSON 포맷으로만 응답하세요.

#         [분류 기준]
#         1. intent: 
#            - "chitchat": 인사, 감정 표현 등 지식 검색이 필요 없는 일상 대화
#            - "simple_search": 전화번호, 운영시간, 주소, 위치 등 단답형 팩트 검색
#            - "search": 원리 설명, 장단점 분석, 영향 등 복잡한 문서 검토와 추론이 필요한 일반 질문
#            - "authoring": 교육 자료, 리포트, 가이드 문서 작성 등 정보의 100% 무결성과 엄격한 검증이 요구되는 생성 작업
#         2. requires_db: true (DB 검색 필수) | false (DB 검색 불필요)
#         3. complexity: "low" (간단한 답변) | "high" (복잡한 추론 필요)
#         4. strict_validation: true (환각 절대 불가, 엄격한 검증) | false (일반적인 유연한 답변)

#         [출력 예시]
#         User: 안녕하세요. 오늘 날씨 좋네요.
#         Assistant: {{"intent": "chitchat", "requires_db": false, "complexity": "low", "strict_validation": false}}

#         User: 국민카드 고객센터 운영시간 언제부터야?
#         Assistant: {{"intent": "simple_search", "requires_db": true, "complexity": "low", "strict_validation": false}}

#         User: 금리 인상이 부동산 대출에 미치는 영향을 설명해줘.
#         Assistant: {{"intent": "search", "requires_db": true, "complexity": "high", "strict_validation": false}}

#         User: 제공된 문서들을 바탕으로 신입사원을 위한 금융 보안 가이드 문서를 작성해줘.
#         Assistant: {{"intent": "authoring", "requires_db": true, "complexity": "high", "strict_validation": true}}

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
        
        # 라우팅의 일관성을 위해 temperature는 0.0, response_format은 json_object로 고정
        self.llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            model=self.model_name,
            temperature=0.0,
            max_tokens=200,
            model_kwargs={"response_format": {"type": "json_object"}} 
        )

    async def forward(self, query: str) -> Dict[str, Any]:
        # [핵심] 프롬프트 보강: 어투보다 '키워드'와 '의도'에 집중하도록 지시
        prompt = f"""
        당신은 금융/정책 RAG 파이프라인의 고성능 시맨틱 라우터입니다.
        사용자의 질문을 분석하여 파이프라인의 실행 계획을 세우고, 반드시 JSON 포맷으로만 응답하세요.

        [분류 기준 및 우선순위]
        1. intent: 
           - "chitchat": 단순 인사, 날씨, 감정 표현 등 '지식 검색이 전혀 필요 없는' 일상적 대화. 
             *주의: 질문에 '비씨카드', '은행', '결제', '금리' 등 금융 키워드가 하나라도 있다면 절대 chitchat이 아닙니다.*
           - "simple_search": 전화번호, 운영시간, 주소 등 단답형 팩트 확인.
           - "search": 원리, 관계, 장단점, 영향 분석 등 문서 검토가 필요한 일반적 질문.
           - "authoring": 가이드라인 작성, 리포트 생성 등 고도의 무결성이 필요한 작업.
           
        2. requires_db: true (문서 근거 필요) | false (모델 자체 지식으로 답변 가능)
        3. complexity: "low" | "high"
        4. strict_validation: true (사후 검증 필수) | false (일반 응답)

        [중요 가이드라인]
        - 사용자의 말투가 상냥하거나 대화체(~인가요?, ~해주시겠어요?)라고 해서 함부로 "chitchat"으로 분류하지 마십시오.
        - 질문의 '형식'보다 '내용'에 집중하십시오. 구체적인 고유명사나 경제 용어가 있다면 반드시 "search" 계열로 분류하십시오.

        [출력 예시]
        User: 비씨카드와 은행의 관계가 뭐야?
        Assistant: {{"intent": "search", "requires_db": true, "complexity": "high", "strict_validation": false}}

        User: 안녕 반가워!
        Assistant: {{"intent": "chitchat", "requires_db": false, "complexity": "low", "strict_validation": false}}

        [사용자 질문]: {query}
        """
        
        try:
            res = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            # 응답 텍스트 정제 (불필요한 공백 제거)
            clean_content = res.content.strip()
            plan = json.loads(clean_content)
            
            # 최소한의 스키마 보장 로직
            if "intent" not in plan:
                plan["intent"] = "search"
            if "requires_db" not in plan:
                plan["requires_db"] = True
                
            logger.info(f"[CloudSlmPlanner] 분석 결과: {plan}")
            return plan
            
        except json.JSONDecodeError as je:
            logger.error(f"[CloudSlmPlanner] JSON 파싱 에러: {je} | Raw: {res.content}")
            return {"intent": "search", "requires_db": True, "complexity": "high", "strict_validation": False}
        except Exception as e:
            logger.error(f"[CloudSlmPlanner] 실행 중 예외 발생: {e}")
            return {"intent": "search", "requires_db": True, "complexity": "high", "strict_validation": False}