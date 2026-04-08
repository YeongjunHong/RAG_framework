import os
import json
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.common.logger import get_logger

logger = get_logger(__name__)

class MultiQueryPlugin:
    def __init__(self, model_name: str = "meta-llama/llama-3-8b-instruct"):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY가 설정되지 않았습니다. MultiQueryPlugin이 정상 동작하지 않을 수 있습니다.")
            
        self.model_name = model_name
        
        self.llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            model=self.model_name,
            # 키워드 추출(0.0)과 달리, 다양한 각도의 질문을 만들기 위해 온도를 약간 올림
            temperature=0.7,  
            max_tokens=200,
            model_kwargs={"response_format": {"type": "json_object"}} 
        )

    async def forward(self, query: str) -> List[str]:
        prompt = f"""
        당신은 AI 언어 모델이자 데이터베이스 검색 도우미입니다.
        사용자의 원본 질문을 분석하여, 벡터 데이터베이스(Vector DB)에서 코사인 유사도 검색 시 
        재현율(Recall)을 극대화할 수 있도록 의미적으로 동일하지만 표현이 다른 3개의 검색 쿼리를 생성하세요.

        [지침]
        1. 동의어, 유의어를 적극 활용하세요.
        2. 질문의 관점을 살짝 틀어서 다른 방식으로 질문해보세요.
        3. 원본 질문의 핵심 의도는 무조건 보존해야 합니다.
        4. **생성되는 모든 쿼리는 반드시 '한국어'로만 작성해야 합니다.** (영어 등 타 언어 사용 금지)
        5. 결과는 반드시 "queries" 키를 가진 JSON 배열 포맷으로 응답하세요.

        [출력 예시]
        User: 하이브리드 카드의 단점이 뭐야?
        Assistant: {{"queries": ["하이브리드 카드의 주요 단점과 한계점은 무엇인가요?", "체크카드와 비교했을 때 하이브리드 카드가 가지는 불편한 점", "하이브리드 신용카드 사용 시 주의사항 및 연체 위험성"]}}

        [사용자 질문]: {query}
        """
        
        try:
            res = await self.llm.ainvoke([HumanMessage(content=prompt)])
            parsed_data = json.loads(res.content)
            queries = parsed_data.get("queries", [])
            
            if not isinstance(queries, list) or not queries:
                logger.warning("[MultiQuery] 유효한 쿼리 목록을 생성하지 못해 빈 리스트를 반환합니다.")
                return []
                
            logger.info(f"[MultiQuery] 다중 쿼리 확장 완료: {queries}")
            return queries
            
        except json.JSONDecodeError:
            logger.error("[MultiQuery] JSON 파싱 실패.")
            return []
        except Exception as e:
            logger.error(f"[MultiQuery] LLM 호출 중 에러 발생: {e}")
            return []