from pydantic import BaseModel

from src.rag.core.types import RagRequest, RagContext
from src.rag.core.interfaces import RagStage

class PromptMakerConfig(BaseModel):
    #  지시문을 훨씬 더 공격적이고 방어적으로 수정
    system_role: str = (
        "당신은 주어진 문서(CONTEXT)에 기반하여 질문에 답변하는 꼼꼼한 AI 어시스턴트입니다.\n"
        "답변을 작성할 때 반드시 다음 규칙을 엄격하게 지키세요:\n"
        "1. 제공된 CONTEXT 정보만을 사용하여 답변하고, 문서에 없는 내용은 절대 지어내지 마세요.\n"
        "2. 각 문장의 끝에는 반드시 해당 정보가 포함된 문서의 식별자를 [REF-숫자] 형식으로 정확하게 복사해서 달아주세요.\n"
        "   (예시: 청년도약계좌는 만 19세 이상 가입 가능합니다. [REF-87774])\n"
        "3. 문서 식별자는 절대 임의로 만들어내거나 변형하지 말고, 주어진 형태 그대로 사용하세요."
    )
    answer_style: str = "한국어로 명확하고 간결하게 답변해 주세요."

class PromptMakerStage(RagStage[PromptMakerConfig]):
    name = "prompt_maker"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        formatted_context = ""
        for doc in ctx.reranked:
            chunk_id = doc.chunk.chunk_id
            content = doc.chunk.content
            #  식별자를 LLM이 쉽게 인식하고 복사할 수 있는 특이한 포맷으로 변경
            formatted_context += f"문서 식별자: [REF-{chunk_id}]\n내용: {content}\n\n"
            
        if not formatted_context:
            formatted_context = ctx.packed_context

        ctx.prompt = (
            f"=== SYSTEM ===\n{self.config.system_role}\n\n"
            f"=== CONTEXT ===\n{formatted_context}\n"
            f"=== USER_QUERY ===\n{request.user_query}\n\n"
            f"=== INSTRUCTIONS ===\n{self.config.answer_style}\n"
        )
        return ctx