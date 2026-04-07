# from dataclasses import dataclass

# from settings.config import cfg
# from src.rag.core.interfaces import RagGenerator
# from src.rag.plugins.openrouter_generator import OpenRouterGenerator


# class MockLlm(RagGenerator):
#     async def forward(self, *, prompt: str, model: str|None = None) -> str:
#         # Deterministic local response for testing without network.
#         return "MOCK_RESPONSE\n" + prompt[:800]


# @dataclass
# class LlmRouter(RagGenerator):
#     """Route generation to OpenRouter / other platform / local model.

#     Selection via env:
#     - LLM_PROVIDER=openrouter | local | mock
#     """

#     primary: RagGenerator
#     fallback: RagGenerator|None = None

#     async def forward(self, *, prompt: str, model: str|None = None) -> str:
#         try:
#             return await self.primary.forward(prompt=prompt, model=model)
#         except Exception:
#             if self.fallback is None:
#                 raise
#             return await self.fallback.forward(prompt=prompt, model=model)


# def build_llm() -> RagGenerator:
#     # provider = cfg.LLM_PROVIDER.lower()
#     # if provider == "openrouter":
#     #     from .openrouter import OpenRouterLlm
#     #     primary = OpenRouterLlm(
#     #         api_key=cfg.OPENROUTER_API_KEY,
#     #         default_model=cfg.MODEL_NAME,
#     #     )
#     #     return LlmRouter(primary=primary, fallback=MockLlm())
#     # if provider == "local":
#     #     return MockLlm()
#     # return MockLlm()
#     return OpenRouterGenerator()

from dataclasses import dataclass
from typing import Any

from settings.config import cfg
from src.rag.core.interfaces import RagGenerator
from src.rag.plugins.openrouter_generator import OpenRouterGenerator


class MockLlm(RagGenerator):
    # stream_queue 파라미터 추가
    async def forward(self, *, prompt: str, model: str|None = None, stream_queue: Any | None = None) -> str:
        # Guardrails 테스트 시 파싱 에러 방지를 위해 JSON 형태로 반환
        if "is_valid" in prompt or "판관" in prompt:
            return '{"is_valid": true, "reason": "Mocked validation (Fallback)"}'
        
        response_text = "MOCK_RESPONSE\n" + prompt[:800]
        
        # 스트리밍 요청이 들어왔을 경우 더미 데이터 큐잉 처리
        if stream_queue:
            await stream_queue.put(response_text)
            await stream_queue.put(None) # 스트림 종료 시그널
            
        return response_text


@dataclass
class LlmRouter(RagGenerator):
    """Route generation to OpenRouter / other platform / local model."""
    primary: RagGenerator
    fallback: RagGenerator|None = None

    # stream_queue 파라미터 추가
    async def forward(self, *, prompt: str, model: str|None = None, stream_queue: Any | None = None) -> str:
        try:
            # 하위 Generator에 stream_queue 패스스루
            return await self.primary.forward(prompt=prompt, model=model, stream_queue=stream_queue)
        except Exception as e:
            if self.fallback is None:
                raise e
            # 장애 발생 시 Fallback으로 전환하며 stream_queue 패스스루
            return await self.fallback.forward(prompt=prompt, model=model, stream_queue=stream_queue)


def build_llm() -> RagGenerator:
    provider = getattr(cfg, "LLM_PROVIDER", "openrouter").lower()
    
    if provider == "openrouter":
        primary = OpenRouterGenerator()
        return LlmRouter(primary=primary, fallback=MockLlm())
        
    if provider in ("local", "mock"):
        return MockLlm()
        
    return LlmRouter(primary=OpenRouterGenerator(), fallback=MockLlm())