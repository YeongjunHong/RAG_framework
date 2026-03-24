# # from pydantic import BaseModel

# # from src.rag.core.types import RagRequest, RagContext
# # from src.rag.core.interfaces import RagStage

# # class PromptMakerConfig(BaseModel):
# #     system_role: str = (
# #         "당신은 주어진 문서(CONTEXT)에 기반하여 질문에 답변하는 꼼꼼한 AI 어시스턴트입니다.\n"
# #         "답변을 작성할 때 반드시 다음 규칙을 엄격하게 지키세요:\n"
# #         "1. 제공된 CONTEXT 정보만을 사용하여 답변하고, 문서에 없는 내용은 절대 지어내지 마세요.\n"
# #         "2. 각 문장의 끝에는 반드시 해당 정보가 포함된 문서의 식별자를 [REF-숫자] 형식으로 정확하게 복사해서 달아주세요.\n"
# #         "   (예시: 청년도약계좌는 만 19세 이상 가입 가능합니다. [REF-87774])\n"
# #         "3. 문서 식별자는 절대 임의로 만들어내거나 변형하지 말고, 주어진 형태 그대로 사용하세요."
# #     )
# #     answer_style: str = "한국어로 명확하고 간결하게 답변해 주세요."

# # class PromptMakerStage(RagStage[PromptMakerConfig]):
# #     name = "prompt_maker"

# #     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
# #         formatted_context = ""
        
# #         # 1. reranked가 아닌 filtered 데이터를 사용하고, 통과(kept=True)한 것만 취합
# #         if ctx.filtered:
# #             for doc in ctx.filtered:
# #                 if doc.kept:
# #                     chunk_id = doc.chunk.chunk_id
# #                     content = doc.chunk.content
# #                     formatted_context += f"문서 식별자: [REF-{chunk_id}]\n내용: {content}\n\n"
        
# #         # 2. 만약 필터링에서 모두 탈락했거나 데이터가 없다면 fallback 처리
# #         if not formatted_context.strip():
# #             formatted_context = ctx.packed_context or "제공된 문서 내용이 없습니다."

# #         ctx.prompt = (
# #             f"=== SYSTEM ===\n{self.config.system_role}\n\n"
# #             f"=== CONTEXT ===\n{formatted_context}\n"
# #             f"=== USER_QUERY ===\n{request.user_query}\n\n"
# #             f"=== INSTRUCTIONS ===\n{self.config.answer_style}\n"
# #         )
# #         return ctx

# from pydantic import BaseModel
# from src.rag.core.types import RagRequest, RagContext
# from src.rag.core.interfaces import RagStage

# class PromptMakerConfig(BaseModel):
#     system_role: str = (
#         "당신은 주어진 문서(CONTEXT)에 기반하여 질문에 답변하는 꼼꼼한 AI 어시스턴트입니다.\n"
#         "답변을 작성할 때 반드시 다음 규칙을 엄격하게 지키세요:\n"
#         "1. 제공된 CONTEXT 정보만을 사용하여 답변하고, 문서에 없는 내용은 절대 지어내지 마세요.\n"
#         "2. 각 문장의 끝에는 반드시 해당 정보가 포함된 문서의 식별자를 [REF-숫자] 형식으로 정확하게 복사해서 달아주세요.\n"
#         "   (예시: 청년도약계좌는 만 19세 이상 가입 가능합니다. [REF-87774])\n"
#         "3. 문서 식별자는 절대 임의로 만들어내거나 변형하지 말고, 주어진 형태 그대로 사용하세요."
#     )
#     answer_style: str = "한국어로 명확하고 간결하게 답변해 주세요."

# class PromptMakerStage(RagStage[PromptMakerConfig]):
#     name = "prompt_maker"

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         # 데이터 순회 및 포맷팅 로직은 모두 앞단으로 위임되었으므로, 여기선 템플릿 조립만 수행
#         ctx.prompt = (
#             f"=== SYSTEM ===\n{self.config.system_role}\n\n"
#             f"=== CONTEXT ===\n{ctx.packed_context}\n"
#             f"=== USER_QUERY ===\n{request.user_query}\n\n"
#             f"=== INSTRUCTIONS ===\n{self.config.answer_style}\n"
#         )
#         return ctx

from pydantic import BaseModel
from src.rag.core.types import RagRequest, RagContext
from src.rag.core.interfaces import RagStage
from src.common.logger import get_logger

logger = get_logger(__name__)

class PromptMakerConfig(BaseModel):
    # 엄격한 RAG용 시스템 프롬프트
    strict_system_role: str = (
        "당신은 주어진 문서(CONTEXT)에 기반하여 질문에 답변하는 꼼꼼한 AI 어시스턴트입니다.\n"
        "답변을 작성할 때 반드시 다음 규칙을 엄격하게 지키세요:\n"
        "1. 제공된 CONTEXT 정보만을 사용하여 답변하고, 문서에 없는 내용은 절대 지어내지 마세요.\n"
        "2. 각 문장의 끝에는 반드시 해당 정보가 포함된 문서의 식별자를 [REF-숫자] 형식으로 복사해서 달아주세요.\n"
        "3. 문서 식별자는 절대 임의로 만들어내거나 변형하지 말고, 주어진 형태 그대로 사용하세요."
    )
    # 단순 잡담/인사용 유연한 시스템 프롬프트
    chitchat_system_role: str = (
        "당신은 친절하고 도움이 되는 AI 어시스턴트입니다.\n"
        "사용자와 자연스럽게 대화하며, 출처나 형식에 얽매이지 말고 편안하게 답변해 주세요."
    )
    answer_style: str = "한국어로 명확하고 간결하게 답변해 주세요."

class PromptMakerStage(RagStage[PromptMakerConfig]):
    name = "prompt_maker"

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        # Planner가 세팅한 의도 파악 (안전한 딕셔너리 접근)
        plan = ctx.plan if isinstance(ctx.plan, dict) else {}
        intent = plan.get("intent", "search")

        # 의도에 따른 프롬프트 동적 스위칭
        if intent == "chitchat":
            logger.info("Chitchat 의도 감지: 유연한 프롬프트 적용 및 Context 주입 생략")
            system_role = self.config.chitchat_system_role
            context_section = "" # DB 검색을 안했으므로 비워둠
        else:
            system_role = self.config.strict_system_role
            context_section = f"=== CONTEXT ===\n{ctx.packed_context}\n"

        # 최종 프롬프트 조립
        ctx.prompt = (
            f"=== SYSTEM ===\n{system_role}\n\n"
            f"{context_section}"
            f"=== USER_QUERY ===\n{request.user_query}\n\n"
            f"=== INSTRUCTIONS ===\n{self.config.answer_style}\n"
        )
        return ctx