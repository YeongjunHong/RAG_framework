import json
import time
import re
from typing import Dict, Any
from src.rag.core.interfaces import RagPostChecker
from src.common.logger import get_logger

logger = get_logger(__name__)

class CompositeGuardrails(RagPostChecker):
    def __init__(self, judge_llm, pii_patterns: list[str] = None):
        self.judge_llm = judge_llm
        
        # PII 정규식 사전 컴파일 (트래픽 인입 시 CPU 오버헤드 방어)
        default_pii = [r"\b\d{6}[-\s]?\d{7}\b", r"\b010[-\s]?\d{4}[-\s]?\d{4}\b"]
        patterns_to_compile = pii_patterns if pii_patterns else default_pii
        
        self.compiled_pii_patterns = [
            re.compile(p) for p in patterns_to_compile
        ]

    def _check_pii(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self.compiled_pii_patterns)

    async def forward(self, context: str, generation: str | None) -> Dict[str, Any]:
        logger.info("[Guardrails] 최종 답변 검증을 시작합니다.")

        if not generation or not generation.strip():
            return {"is_valid": False, "reason": "생성된 답변이 비어 있습니다.", "error_type": "empty_output"}

        if self._check_pii(generation):
            logger.warning("[Guardrails] PII 유출 감지. 즉시 차단합니다.")
            return {"is_valid": False, "reason": "답변 내에 개인 식별 정보(PII)가 포함되어 있습니다.", "error_type": "pii_leak"}

        judge_prompt = f"""당신은 RAG 시스템의 신뢰성을 검증하는 엄격한 판관입니다.
[Context]의 내용에만 기반하여 [Answer]가 작성되었는지 평가하십시오.

[Context]:
{context}

[Answer]:
{generation}

평가 규칙:
1. 외부 지식이나 환각(Hallucination)이 포함되었다면 is_valid는 false입니다.
2. 논리적으로 도출 가능하다면 is_valid는 true입니다.
3. 출력은 반드시 아래 JSON 포맷을 준수하십시오. 다른 설명은 절대 추가하지 마십시오.

{{
    "is_valid": true 또는 false,
    "reason": "판단에 대한 간략한 사유 (1~2문장)"
}}
"""
        try:
            logger.info("[Guardrails] 판관 LLM 추론 요청 전송...")
            start_time = time.perf_counter()
            
            # 내부 래퍼 호환성을 위해 kwargs(response_format) 생략하고 일반 텍스트 추론 요청
            judge_response_text = await self.judge_llm.forward(
                prompt=judge_prompt,
                model="openai/gpt-4o-mini"
            )

            elapsed = time.perf_counter() - start_time
            logger.info(f"[Guardrails] 판관 LLM 응답 수신 완료 (소요 시간: {elapsed:.2f}초)")

            # LLM이 뱉어내는 마크다운 백틱 클렌징 후 수동 파싱
            clean_text = judge_response_text.replace("```json", "").replace("```", "").strip()
            judge_result = json.loads(clean_text)
            
            is_valid = judge_result.get("is_valid", False)
            reason = judge_result.get("reason", "판단 사유 누락")
            
            if is_valid:
                return {"is_valid": True, "reason": "Pass", "error_type": None}
            else:
                logger.warning(f"[Guardrails] LLM Judge 검증 실패. 사유: {reason}")
                return {"is_valid": False, "reason": reason, "error_type": "hallucination"}
                
        except json.JSONDecodeError:
            logger.error(f"[Guardrails] 판관 LLM JSON 파싱 실패. 원본: {judge_response_text}")
            return {"is_valid": False, "reason": "판관 LLM 출력 포맷 오류", "error_type": "format_error"}
        except Exception as e:
            logger.error(f"[Guardrails] LLM Judge 시스템 예외 발생: {e}")
            return {"is_valid": False, "reason": "판관 LLM 시스템 에러", "error_type": "system_error"}