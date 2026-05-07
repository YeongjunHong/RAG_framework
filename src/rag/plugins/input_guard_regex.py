
import re
import json
from pathlib import Path
from typing import List, Dict, Any

from src.rag.core.interfaces import RagInputGuard
from src.rag.core.types import InputGuardResponse, SecurityStatus
from src.common.logger import get_logger

logger = get_logger(__name__)

class RegexInputGuard(RagInputGuard):
    def __init__(self, config_path: str = "settings/input_guard_rules.json"):
        self.config_path = Path(config_path)
        self.rules = self._load_rules()
        self.enabled = self.rules.get("enabled", True)
        
        # [MODIFIED] 초기화 시점에 정규식을 미리 컴파일하여 CPU 오버헤드 제거
        self.compiled_patterns: List[re.Pattern] = []
        for pattern_str in self.rules.get("risk_patterns", []):
            try:
                self.compiled_patterns.append(re.compile(pattern_str, re.IGNORECASE))
            except re.error as e:
                logger.error(f"정규식 패턴 컴파일 실패 (무시됨): {pattern_str} ({e})")

        # PII 판별을 위한 특정 패턴 (주민등록번호, 전화번호 등)
        self.pii_keywords = ["\\d{6}", "\\d{4}"]

    def _load_rules(self) -> Dict[str, Any]:
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("input_guard", {})
        except Exception as e:
            logger.error(f"보안 규칙 로드 중 오류 발생: {e}")
        return {"enabled": True, "risk_patterns": []}

    async def forward(self, query: str) -> InputGuardResponse:
        if not self.enabled:
            return InputGuardResponse(is_safe=True)

        hit_patterns = []
        
        # [MODIFIED] 미리 컴파일된 정규식 객체로 O(1) 매칭
        for compiled_regex in self.compiled_patterns:
            if compiled_regex.search(query):
                hit_patterns.append(compiled_regex.pattern)

        if hit_patterns:
            logger.warning("[INTERNAL_SECURITY] Detection rules triggered.")

            status = SecurityStatus.INJECTION_ATTEMPT
            reason = "Unauthorized request pattern detected."

            for p in hit_patterns:
                if any(kw in p for kw in self.pii_keywords):
                    status = SecurityStatus.PII_LEAK
                    reason = "민감한 개인정보(PII) 노출 의심 패턴 감지."
                    break
            
            return InputGuardResponse(
                is_safe=False,
                status=status,
                reason=reason,
                hit_patterns=hit_patterns
            )

        return InputGuardResponse(is_safe=True, status=SecurityStatus.SAFE)