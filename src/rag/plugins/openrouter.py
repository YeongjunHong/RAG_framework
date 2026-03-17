from typing import Optional

from src.rag.core.interfaces import RagGenerator


class OpenRouterLlm(RagGenerator):
    """OpenRouter adapter.

    Uses httpx (optional dependency). Kept outside core to preserve framework/package-free steps.
    """

    def __init__(self, api_key: str, default_model: str):
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouterLlm")
        self.api_key = api_key
        self.default_model = default_model

    async def forward(self, *, prompt: str, model: Optional[str] = None) -> str:
        import httpx

        m = model or self.default_model
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": m,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
