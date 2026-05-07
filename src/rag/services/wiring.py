

import src.rag.plugins as plugins
import src.rag.services as services
import src.rag.services.registry as registry
import src.common.utils as utils
from settings.config import cfg

from src.rag.services.registry import RetrieverRegistry
from src.rag.plugins.postgres_retriever import PostgresHybridRetriever
from src.rag.plugins.local_reranker import LocalCrossEncoderReranker
from src.rag.plugins.slm_planner import CloudSlmPlanner
from src.rag.plugins.noop import NoopPostChecker 
from src.rag.plugins.guardrails_runner import CompositeGuardrails
from src.rag.plugins.router import build_llm
from src.rag.plugins.input_guard_regex import RegexInputGuard
from src.rag.plugins.qe_keyword import KeywordExtractorPlugin
from src.rag.plugins.qe_multi_query import MultiQueryPlugin

# [MODIFIED] 기존 SLMTextCompressorPlugin 거품을 걷어내고 LLMLingua 도입
# from src.rag.plugins.text_compressor import LLMLinguaCompressorPlugin
from src.rag.plugins.text_compressor import PassThroughCompressorPlugin
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

def build_planner_registry(**kwargs) -> registry.PlannerRegistry:
    return registry.PlannerRegistry(
        items={
            "default": CloudSlmPlanner(model_name="meta-llama/llama-3-8b-instruct")
        }
    )

def build_query_expander_registry(**kwargs) -> registry.QueryExpanderRegistry:
    return registry.QueryExpanderRegistry(
        items={
            "default": MultiQueryPlugin(),
            "keyword_extractor": KeywordExtractorPlugin(),
            "multi_query": MultiQueryPlugin()
        }
    )

def build_input_guard_registry(**kwargs) -> registry.InputGuardRegistry:
    default_guard = RegexInputGuard()
    return registry.InputGuardRegistry(
        items={
            "default": default_guard,
            "regex": default_guard
        }
    )

def build_retriever_registry(pool=None, **kwargs) -> registry.RetrieverRegistry:
    db_url = utils.get_pg_url(cfg.PG1_DATABASE, cfg.PG1_HOST, cfg.PG1_PORT, cfg.PG1_USERNAME, cfg.PG1_PASSWORD)
    async_db_url = db_url.replace("+psycopg", "")
    
    # [MODIFIED] Part 2 리팩토링 호환성 방어: 외부에서 pool이 주입되면 pool을 쓰고, 아니면 기존 dsn 방식 유지
    retriever_kwargs = {"pool": pool} if pool else {"dsn": async_db_url}
    
    return RetrieverRegistry(
        items={
            "default": PostgresHybridRetriever(**retriever_kwargs)
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

def build_postchecker_registry(**kwargs) -> registry.PostCheckerRegistry:
    judge_llm = build_llm()
    return registry.PostCheckerRegistry(
        items={
            "default": CompositeGuardrails(judge_llm=judge_llm),
            "noop": NoopPostChecker()
        }
    )

# [MODIFIED] 레지스트리에 LLMLinguaCompressorPlugin 등록 완료
# def build_text_compressor_registry(**kwargs) -> registry.TextCompressorRegistry:
#     return registry.TextCompressorRegistry(
#         items={
#             "default": LLMLinguaCompressorPlugin(target_token_ratio=0.5),
#             "slm_compressor": LLMLinguaCompressorPlugin(target_token_ratio=0.5)
#         }
#     )

def build_text_compressor_registry(**kwargs) -> registry.TextCompressorRegistry:
    return registry.TextCompressorRegistry(
        items={
            "default": PassThroughCompressorPlugin(),
            "slm_compressor": PassThroughCompressorPlugin()
        }
    )

def build_db_session_maker():
    db_url = utils.get_pg_url(
        cfg.PG1_DATABASE, cfg.PG1_HOST, cfg.PG1_PORT, 
        cfg.PG1_USERNAME, cfg.PG1_PASSWORD
    )
    async_db_url = db_url.replace("+psycopg", "")
    if async_db_url.startswith("postgresql://"):
        async_db_url = async_db_url.replace("postgresql://", "postgresql+asyncpg://")
        
    engine = create_async_engine(async_db_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


















