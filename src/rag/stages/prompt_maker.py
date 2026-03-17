from pydantic import BaseModel

from src.rag.core.types import RagRequest, RagContext
from src.rag.core.interfaces import RagStage


class PromptMakerConfig(BaseModel):
    system_role: str = "You are a careful assistant. Use only provided context as evidence."
    answer_style: str = "Korean, concise, cite chunk ids when possible."


class PromptMakerStage(RagStage[PromptMakerConfig]):
    name = "prompt_maker"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        ctx.prompt = (
            f"SYSTEM:\n{self.config.system_role}\n\n"
            f"USER_QUERY:\n{request.user_query}\n\n"
            f"CONTEXT:\n{ctx.packed_context}\n\n"
            f"INSTRUCTIONS:\n{self.config.answer_style}\n"
        )
        return ctx
