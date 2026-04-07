# import src.rag.plugins as plugins
# import src.rag.services as services
# import src.rag.services.registry as registry



# def build_query_expander_registry(**kwargs) -> registry.QueryExpanderRegistry:
#     return registry.QueryExpanderRegistry()

# #테스트용; 

# from settings.config import cfg
# import src.common.utils as utils
# from src.rag.services.registry import RetrieverRegistry
# from src.rag.plugins.postgres_retriever import PostgresHybridRetriever
# from src.rag.plugins.slm_planner import CloudSlmPlanner


# # --- Planner 추가 ---
# def build_planner_registry(**kwargs) -> registry.PlannerRegistry:
#     return registry.PlannerRegistry(
#         items={
#             "default": CloudSlmPlanner(model_name="meta-llama/llama-3-8b-instruct")
#         }
#     )
# # --------------------

# def build_retriever_registry(**kwargs) -> registry.RetrieverRegistry:

#     #DB 연결 주소
#     db_url = utils.get_pg_url(cfg.PG1_DATABASE, cfg.PG1_HOST, cfg.PG1_PORT, cfg.PG1_USERNAME, cfg.PG1_PASSWORD)
#     async_db_url = db_url.replace("+psycopg", "")
#     return RetrieverRegistry(
#         items={
#             # 기존 InMemoryRetriever 대신 PostgresHybridRetriever 로 테스트.
#             "default": PostgresHybridRetriever(dsn=async_db_url)
#         }
#     # return registry.RetrieverRegistry(
#     #     items={
#     #         "default": plugins.InMemoryRetriever()
#     #     }
#     )

# from src.rag.plugins.local_reranker import LocalCrossEncoderReranker

# def build_reranker_registry(**kwargs) -> registry.RerankerRegistry:
#     return registry.RerankerRegistry(
#         items={
#             # "default": plugins.NoopReranker()
#             "default": LocalCrossEncoderReranker()
#         }
#     )

# def build_filterer_registry(**kwargs) -> registry.FiltererRegistry:
#     return registry.FiltererRegistry()


# def build_assembler_registry(**kwargs) -> registry.AssemblerRegistry:
#     return registry.AssemblerRegistry()


# def build_compressor_registry(**kwargs) -> registry.CompressorRegistry:
#     return registry.CompressorRegistry()


# def build_packer_registry(**kwargs) -> registry.PackerRegistry:
#     return registry.PackerRegistry()


# def build_promptmaker_registry(**kwargs) -> registry.PromptMakerRegistry:
#     return registry.PromptMakerRegistry()


# def build_generator_registry(**kwargs) -> registry.GeneratorRegistry:
#     return registry.GeneratorRegistry()


# def build_postchecker_registry(**kwargs) -> registry.PostCheckerRegistry:
#     return registry.PostCheckerRegistry()


# import src.rag.plugins as plugins
# import src.rag.services as services
# import src.rag.services.registry as registry
# import src.common.utils as utils
# from settings.config import cfg

# from src.rag.services.registry import RetrieverRegistry
# from src.rag.plugins.postgres_retriever import PostgresHybridRetriever
# from src.rag.plugins.local_reranker import LocalCrossEncoderReranker
# from src.rag.plugins.slm_planner import CloudSlmPlanner

# def build_planner_registry(**kwargs) -> registry.PlannerRegistry:
#     return registry.PlannerRegistry(
#         items={
#             "default": CloudSlmPlanner(model_name="meta-llama/llama-3-8b-instruct")
#         }
#     )

# def build_query_expander_registry(**kwargs) -> registry.QueryExpanderRegistry:
#     return registry.QueryExpanderRegistry()

# def build_retriever_registry(**kwargs) -> registry.RetrieverRegistry:
#     db_url = utils.get_pg_url(cfg.PG1_DATABASE, cfg.PG1_HOST, cfg.PG1_PORT, cfg.PG1_USERNAME, cfg.PG1_PASSWORD)
#     async_db_url = db_url.replace("+psycopg", "")
#     return RetrieverRegistry(
#         items={
#             "default": PostgresHybridRetriever(dsn=async_db_url)
#         }
#     )

# def build_reranker_registry(**kwargs) -> registry.RerankerRegistry:
#     return registry.RerankerRegistry(
#         items={
#             "default": LocalCrossEncoderReranker()
#         }
#     )

# def build_filterer_registry(**kwargs) -> registry.FiltererRegistry:
#     return registry.FiltererRegistry()

# def build_assembler_registry(**kwargs) -> registry.AssemblerRegistry:
#     return registry.AssemblerRegistry()

# def build_compressor_registry(**kwargs) -> registry.CompressorRegistry:
#     return registry.CompressorRegistry()

# def build_packer_registry(**kwargs) -> registry.PackerRegistry:
#     return registry.PackerRegistry()

# def build_promptmaker_registry(**kwargs) -> registry.PromptMakerRegistry:
#     return registry.PromptMakerRegistry()

# def build_generator_registry(**kwargs) -> registry.GeneratorRegistry:
#     return registry.GeneratorRegistry()

# def build_postchecker_registry(**kwargs) -> registry.PostCheckerRegistry:
#     return registry.PostCheckerRegistry()

import src.rag.plugins as plugins
import src.rag.services as services
import src.rag.services.registry as registry
import src.common.utils as utils
from settings.config import cfg

from src.rag.services.registry import RetrieverRegistry
from src.rag.plugins.postgres_retriever import PostgresHybridRetriever
from src.rag.plugins.local_reranker import LocalCrossEncoderReranker
from src.rag.plugins.slm_planner import CloudSlmPlanner
from src.rag.plugins.noop import NoopPostChecker # post_check
from src.rag.plugins.guardrails_runner import CompositeGuardrails
from src.rag.plugins.router import build_llm

def build_planner_registry(**kwargs) -> registry.PlannerRegistry:
    return registry.PlannerRegistry(
        items={
            "default": CloudSlmPlanner(model_name="meta-llama/llama-3-8b-instruct")
        }
    )

def build_query_expander_registry(**kwargs) -> registry.QueryExpanderRegistry:
    return registry.QueryExpanderRegistry()

def build_retriever_registry(**kwargs) -> registry.RetrieverRegistry:
    db_url = utils.get_pg_url(cfg.PG1_DATABASE, cfg.PG1_HOST, cfg.PG1_PORT, cfg.PG1_USERNAME, cfg.PG1_PASSWORD)
    async_db_url = db_url.replace("+psycopg", "")
    return RetrieverRegistry(
        items={
            "default": PostgresHybridRetriever(dsn=async_db_url)
        }
    )

def build_reranker_registry(**kwargs) -> registry.RerankerRegistry:
    return registry.RerankerRegistry(
        items={
            "default": LocalCrossEncoderReranker()
        }
    )

def build_filterer_registry(**kwargs) -> registry.FiltererRegistry:
    return registry.FiltererRegistry()

def build_assembler_registry(**kwargs) -> registry.AssemblerRegistry:
    return registry.AssemblerRegistry()

def build_compressor_registry(**kwargs) -> registry.CompressorRegistry:
    return registry.CompressorRegistry()

def build_packer_registry(**kwargs) -> registry.PackerRegistry:
    return registry.PackerRegistry()

def build_promptmaker_registry(**kwargs) -> registry.PromptMakerRegistry:
    return registry.PromptMakerRegistry()

def build_generator_registry(**kwargs) -> registry.GeneratorRegistry:
    return registry.GeneratorRegistry()

# def build_postchecker_registry(**kwargs) -> registry.PostCheckerRegistry:
#     return registry.PostCheckerRegistry()

# def build_postchecker_registry(**kwargs) -> registry.PostCheckerRegistry:
#     return registry.PostCheckerRegistry(
#         items={
#             "default": NoopPostChecker(),
#             "noop": NoopPostChecker()
#         }
#     )
def build_postchecker_registry(**kwargs) -> registry.PostCheckerRegistry:
    # 1. 판관(Judge) 역할을 할 LLM 인스턴스 초기화
    # 비용/속도를 최적화하려면 여기서 별도의 가벼운 모델(gpt-4o-mini 등)을 세팅해도 된다.
    # 지금은 범용성을 위해 기존 시스템의 LLM을 그대로 주입한다.
    judge_llm = build_llm()

    # 2. 레지스트리에 등록
    return registry.PostCheckerRegistry(
        items={
            # 프로덕션/데모 실행 시 기본적으로 작동할 복합 검증기
            "default": CompositeGuardrails(judge_llm=judge_llm),
            
            # 장애 발생 시나 테스트 목적을 위한 Bypass(안전망) 용도
            "noop": NoopPostChecker()
        }
    )