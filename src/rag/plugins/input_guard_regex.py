import re
import json
from pathlib import Path
from src.rag.core.interfaces import RagInputGuard
from src.rag.core.types import InputGuardResponse, SecurityStatus
from src.common.logger import get_logger

logger = get_logger(__name__)

class RegexInputGuard(RagInputGuard):
    """정규식 패턴 매칭을 이용한 가벼운 인풋 가드레일 플러그인"""

    def __init__(self, config_path: str = "settings/input_guard_rules.json"):
        self.config_path = Path(config_path)
        self.rules = self._load_rules()

    def _load_rules(self) -> dict:
        """JSON 설정 파일에서 보안 규칙 로드"""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("input_guard", {})
            else:
                logger.warning(f"보안 규칙 파일을 찾을 수 없습니다: {self.config_path}")
        except Exception as e:
            logger.error(f"보안 규칙 로드 중 오류 발생: {e}")
            
        # 기본값 반환
        return {"enabled": True, "risk_patterns": []}

    # async def forward(self, query: str) -> InputGuardResponse:
    #     """
    #     인터페이스 규격에 따른 보안 검사 수행
    #     """
    #     if not self.rules.get("enabled", True):
    #         return InputGuardResponse(is_safe=True)

    #     hit_patterns = []
    #     patterns = self.rules.get("risk_patterns", [])

    #     # 대소문자 구분 없이 모든 패턴 검사
    #     for pattern in patterns:
    #         try:
    #             if re.search(pattern, query, re.IGNORECASE):
    #                 hit_patterns.append(pattern)
    #         except re.error as e:
    #             logger.error(f"잘못된 정규식 패턴 발견: {pattern} ({e})")

    #     if hit_patterns:
    #         logger.error(f"[Security] 프롬프트 인젝션 의심 패턴 감지: {hit_patterns}")
    #         return InputGuardResponse(
    #             is_safe=False,
    #             status=SecurityStatus.INJECTION_ATTEMPT,
    #             reason="Malicious prompt pattern detected",
    #             hit_patterns=hit_patterns
    #         )

    #     return InputGuardResponse(
    #         is_safe=True, 
    #         status=SecurityStatus.SAFE
    #     )
    async def forward(self, query: str) -> InputGuardResponse:
        if not self.rules.get("enabled", True):
            return InputGuardResponse(is_safe=True)

        hit_patterns = []
        patterns = self.rules.get("risk_patterns", [])

        for pattern in patterns:
            try:
                if re.search(pattern, query, re.IGNORECASE):
                    hit_patterns.append(pattern)
            except re.error as e:
                logger.error(f"잘못된 정규식 패턴: {pattern} ({e})")

        if hit_patterns:
            # error 대신 warning을 사용하여 터미널 노출을 막음 (런타임 로깅 설정에 따라 다름)
            # 실제 운영에서는 보안 전용 로거를 분리하는 것이 정석
            logger.warning(f"[INTERNAL_SECURITY] Detection rules triggered.")
            
            return InputGuardResponse(
                is_safe=False,
                status=SecurityStatus.INJECTION_ATTEMPT,
                reason="Unauthorized request pattern detected.",
                hit_patterns=hit_patterns  # DB 기록을 위해 컨텍스트에는 원본 패턴 유지
            )

        return InputGuardResponse(is_safe=True, status=SecurityStatus.SAFE)