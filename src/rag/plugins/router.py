from dataclasses import dataclass

from settings.config import cfg
from src.rag.core.interfaces import RagGenerator
from src.rag.plugins.openrouter_generator import OpenRouterGenerator


class MockLlm(RagGenerator):
    async def forward(self, *, prompt: str, model: str|None = None) -> str:
        # Deterministic local response for testing without network.
        return "MOCK_RESPONSE\n" + prompt[:800]


@dataclass
class LlmRouter(RagGenerator):
    """Route generation to OpenRouter / other platform / local model.

    Selection via env:
    - LLM_PROVIDER=openrouter | local | mock
    """

    primary: RagGenerator
    fallback: RagGenerator|None = None

    async def forward(self, *, prompt: str, model: str|None = None) -> str:
        try:
            return await self.primary.forward(prompt=prompt, model=model)
        except Exception:
            if self.fallback is None:
                raise
            return await self.fallback.forward(prompt=prompt, model=model)


def build_llm() -> RagGenerator:
    # provider = cfg.LLM_PROVIDER.lower()
    # if provider == "openrouter":
    #     from .openrouter import OpenRouterLlm
    #     primary = OpenRouterLlm(
    #         api_key=cfg.OPENROUTER_API_KEY,
    #         default_model=cfg.MODEL_NAME,
    #     )
    #     return LlmRouter(primary=primary, fallback=MockLlm())
    # if provider == "local":
    #     return MockLlm()
    # return MockLlm()
    return OpenRouterGenerator()
