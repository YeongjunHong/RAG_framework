import os
import json
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.common.logger import get_logger

logger = get_logger(__name__)

class KeywordExtractorPlugin:
    def __init__(self, model_name: str = "meta-llama/llama-3-8b-instruct"):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY가 설정되지 않았습니다. Keyword Extractor가 정상 동작하지 않을 수 있습니다.")
            
        self.model_name = model_name
        
        self.llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            model=self.model_name,
            temperature=0.0,  # 무조건 일관된 추출을 위해 0.0 설정
            max_tokens=100,   # 단어 몇 개만 뽑으므로 토큰 낭비 방지
            model_kwargs={"response_format": {"type": "json_object"}} 
        )

    async def forward(self, query: str) -> List[str]:
        prompt = f"""
        당신은 검색 엔진 최적화(SEO) 및 데이터베이스 검색 전문가입니다.
        사용자의 질문에서 BM25(키워드 기반 검색)에 유리한 핵심 명사, 고유명사, 엔티티만 추출하세요.
        조사, 동사, 형용사, 불용어(알려줘, 뭐야 등)는 철저히 제거해야 합니다.
        결과는 반드시 아래 JSON 포맷으로 응답하세요.

        [출력 예시]
        User: 국민카드 고객센터 운영시간 언제부터야?
        Assistant: {{"keywords": ["국민카드", "고객센터", "운영시간"]}}

        User: 이번에 새로 나온 하이브리드 카드 단점 좀 정리해줘.
        Assistant: {{"keywords": ["하이브리드", "카드", "단점"]}}

        [사용자 질문]: {query}
        """
        
        try:
            res = await self.llm.ainvoke([HumanMessage(content=prompt)])
            parsed_data = json.loads(res.content)
            keywords = parsed_data.get("keywords", [])
            
            # 응답 검증: 빈 리스트거나 포맷이 이상할 경우
            if not isinstance(keywords, list) or not keywords:
                logger.warning("[KeywordExtractor] 유효한 키워드를 찾지 못해 Fallback(공백 분리)을 적용합니다.")
                return query.split()
                
            logger.info(f"[KeywordExtractor] 키워드 추출 완료: {keywords}")
            return keywords
            
        except json.JSONDecodeError:
            logger.error("[KeywordExtractor] JSON 파싱 실패.")
            return query.split()
        except Exception as e:
            logger.error(f"[KeywordExtractor] LLM 호출 중 에러 발생: {e}")
            # 시스템 장애를 막기 위한 Graceful Degradation (최소한 띄어쓰기로라도 분리해서 리턴)
            return query.split()