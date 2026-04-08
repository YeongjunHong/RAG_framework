import os
import json
import re
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.common.logger import get_logger
from src.rag.core.interfaces import RagQueryExpander

logger = get_logger(__name__)

class KeywordExtractorPlugin(RagQueryExpander):
    def __init__(self, model_name: str = "meta-llama/llama-3-8b-instruct"):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY가 설정되지 않았습니다. Keyword Extractor가 정상 동작하지 않을 수 있습니다.")
            
        self.model_name = model_name
        
        self.llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            model=self.model_name,
            temperature=0.0,
            # 만약을 대비해 100에서 200으로 토큰 버퍼 확보
            max_tokens=200,   
            model_kwargs={"response_format": {"type": "json_object"}} 
        )

    async def forward(self, query: str) -> List[str]:
        prompt = f"""
        당신은 검색 엔진 최적화(SEO) 및 데이터베이스 검색 전문가입니다.
        사용자의 질문에서 BM25(키워드 기반 검색)에 유리한 핵심 명사, 고유명사, 엔티티만 추출하세요.
        조사, 동사, 형용사, 불용어(알려줘, 뭐야 등)는 철저히 제거해야 합니다.
        
        [지침]
        1. 결과는 반드시 "keywords" 키를 가진 JSON 포맷으로 응답하세요.
        2. **절대로 인사말, 설명, 마크다운 기호(```)를 포함하지 마세요. 오직 중괄호 '{{' 로 시작하고 '}}' 로 끝나는 순수 JSON 문자열만 출력해야 합니다.**

        [출력 예시]
        {{
            "keywords": ["국민카드", "고객센터", "운영시간"]
        }}

        [사용자 질문]: {query}
        """
        
        try:
            res = await self.llm.ainvoke([HumanMessage(content=prompt)])
            raw_content = res.content.strip()
            
            raw_content = re.sub(r'^```(?:json)?\s*', '', raw_content, flags=re.IGNORECASE)
            raw_content = re.sub(r'\s*```$', '', raw_content)
            
            start_idx = raw_content.find('{')
            end_idx = raw_content.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                raw_content = raw_content[start_idx:end_idx+1]
            else:
                logger.warning(f"[KeywordExtractor] JSON 중괄호를 찾을 수 없습니다. 원본: {raw_content[:100]}")
                return query.split()
            
            parsed_data = json.loads(raw_content)
            keywords = parsed_data.get("keywords", [])
            
            if not isinstance(keywords, list) or not keywords:
                logger.warning("[KeywordExtractor] 유효한 키워드를 찾지 못해 Fallback(공백 분리)을 적용합니다.")
                return query.split()
                
            logger.info(f"[KeywordExtractor] 키워드 추출 완료: {keywords}")
            return keywords
            
        except json.JSONDecodeError as e:
            logger.error(f"[KeywordExtractor] JSON 파싱 실패. 원본 응답: {res.content[:100]}... | 에러: {e}")
            return query.split()
        except Exception as e:
            logger.error(f"[KeywordExtractor] LLM 호출 중 에러 발생: {e}")
            return query.split()