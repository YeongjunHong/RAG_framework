import src.rag.plugins as plugins
import src.rag.services as services
import src.rag.services.registry as registry



def build_query_expander_registry(**kwargs) -> registry.QueryExpanderRegistry:
    return registry.QueryExpanderRegistry()

#테스트용; jules 추가 

from settings.config import cfg
import src.common.utils as utils
from src.rag.services.registry import RetrieverRegistry
from src.rag.plugins.postgres_retriever import PostgresHybridRetriever

def build_retriever_registry(**kwargs) -> registry.RetrieverRegistry:

    #DB 연결 주소
    db_url = utils.get_pg_url(cfg.PG1_DATABASE, cfg.PG1_HOST, cfg.PG1_PORT, cfg.PG1_USERNAME, cfg.PG1_PASSWORD)
    async_db_url = db_url.replace("+psycopg", "")
    return RetrieverRegistry(
        items={
            # 기존 InMemoryRetriever 대신 PostgresHybridRetriever 로 테스트.
            "default": PostgresHybridRetriever(dsn=async_db_url)
        }
    # return registry.RetrieverRegistry(
    #     items={
    #         "default": plugins.InMemoryRetriever()
    #     }
    )


def build_reranker_registry(**kwargs) -> registry.RerankerRegistry:
    return registry.RerankerRegistry(
        items={
            "default": plugins.NoopReranker()
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
    return registry.PostCheckerRegistry()

