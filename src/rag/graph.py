
from typing import TypedDict, Callable
from langgraph.graph import StateGraph, END

from .core.types import SourceChunk, RagRequest, RagResponse, RagContext, QueryIntent
from .stages.input_guard import InputGuardStage
from .stages.planner import PlannerStage, PlannerConfig
from .stages.query_expansion import QueryExpansionStage, QueryExpansionConfig
from .stages.retrieval import RetrievalStage, RetrievalConfig
from .stages.reranking import RerankingStage, RerankingConfig
from .stages.filtering import FilteringStage, FilteringConfig
from .stages.assembly import AssemblyStage, AssemblyConfig
from .stages.compression import CompressionStage, CompressionConfig
from .stages.packing import PackingStage, PackingConfig
from .stages.prompt_maker import PromptMakerStage, PromptMakerConfig
from .stages.generator import GeneratorStage, GeneratorConfig
from .stages.post_check import PostCheckStage, PostCheckConfig, to_response

from .plugins.router import build_llm
from .plugins.tracing import build_tracer
from .plugins.cache_manager import SemanticCacheManager
import src.rag.services.wiring as wiring
from src.common.logger import get_logger
from settings.config import cfg

logger = get_logger(__name__)

class GraphState(TypedDict):
    request: RagRequest
    ctx: RagContext

def build_graph():
    tracer = build_tracer()
    llm = build_llm()

    db_session_maker = wiring.build_db_session_maker()
    input_guard_registry = wiring.build_input_guard_registry()
    
    cache_manager = SemanticCacheManager()
    
    planner_registry = wiring.build_planner_registry()
    query_expander_registry = wiring.build_query_expander_registry()
    retriever_registry = wiring.build_retriever_registry()
    reranker_registry = wiring.build_reranker_registry()
    filter_registry = wiring.build_filterer_registry()
    assembler_registry = wiring.build_assembler_registry()
    text_compressor_registry = wiring.build_text_compressor_registry() 
    packer_registry = wiring.build_packer_registry()
    promptmaker_registry = wiring.build_promptmaker_registry()
    generator_registry = wiring.build_generator_registry()
    postchecker_registry = wiring.build_postchecker_registry()

    ig = InputGuardStage(registry=input_guard_registry, tracer=tracer, db_session_maker=db_session_maker)
    pln = PlannerStage(PlannerConfig(), registry=planner_registry, tracer=tracer)
    qx = QueryExpansionStage(config=QueryExpansionConfig(mode="dynamic", max_expansions=4), registry=query_expander_registry, tracer=tracer)
    rt = RetrievalStage(RetrievalConfig(), registry=retriever_registry, tracer=tracer)
    rr = RerankingStage(RerankingConfig(), registry=reranker_registry, tracer=tracer)
    flt = FilteringStage(FilteringConfig())
    asm = AssemblyStage(AssemblyConfig())
    cmp = CompressionStage(CompressionConfig(), registry=text_compressor_registry)
    pck = PackingStage(PackingConfig(), tracer=tracer)
    pm = PromptMakerStage(PromptMakerConfig())
    gen = GeneratorStage(GeneratorConfig(), llm=llm, tracer=tracer)
    pc = PostCheckStage(PostCheckConfig(), guardrails_plugin=postchecker_registry.get("default"), tracer=tracer)

    def make_safe_node(node_name: str, stage_callable: Callable) -> Callable:
        async def safe_node_func(state: GraphState) -> GraphState:
            req, ctx = state["request"], state["ctx"]
            # 노드 진입 전 에러가 이미 있다면 즉시 바이패스
            if ctx.errors: return state
            try:
                await stage_callable(req, ctx)
            except Exception as e:
                logger.error(f"[{node_name}] 파이프라인 치명적 예외 발생: {str(e)}", exc_info=True)
                ctx.errors.append({"node": node_name, "error": str(e), "type": type(e).__name__})
            return state
        return safe_node_func

    node_input_guard = make_safe_node("input_guard", ig)
    node_planner = make_safe_node("planner", pln)
    node_query_expansion = make_safe_node("query_expansion", qx)
    node_retrieval = make_safe_node("retrieval", rt)
    node_reranking = make_safe_node("reranking", rr)
    node_filtering = make_safe_node("filtering", flt)
    node_assembly = make_safe_node("assembly", asm)
    node_compression = make_safe_node("compression", cmp)
    node_packing = make_safe_node("packing", pck)
    node_prompt_maker = make_safe_node("prompt_maker", pm)
    node_generator = make_safe_node("generator", gen)
    node_post_check = make_safe_node("post_check", pc)

    async def node_cache_check(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        cached_response = cache_manager.check_cache(req.user_query, threshold=0.90)
        
        if cached_response:
            ctx.raw_generation = cached_response
            ctx.intent = QueryIntent.CACHE_HIT
            logger.info("[Router] Cache HIT -> 파이프라인 우회 (END)")
        else:
            ctx.intent = QueryIntent.UNKNOWN 
            logger.info("[Router] Cache MISS -> 정상 파이프라인 진입")
        return state

    async def node_cache_save(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        if not ctx.errors and getattr(ctx, "raw_generation", None) and getattr(ctx.input_guard, "is_safe", True):
             cache_manager.save_cache(req.user_query, ctx.raw_generation)
        return state

    async def node_error_handler(state: GraphState) -> GraphState:
        ctx = state["ctx"]
        last_error_node = ctx.errors[-1]["node"] if ctx.errors else "unknown"
        ctx.raw_generation = "현재 시스템 내부 연산 지연 또는 통신 장애가 발생하여 답변을 생성할 수 없습니다."
        ctx.postcheck = {"is_valid": False, "reason": f"System Fallback triggered by {last_error_node}"}
        return state

    # --- Routing Logic ---
    def route_after_input_guard(state: GraphState) -> str:
        ctx = state["ctx"]
        if ctx.errors: return "error_handler"
        if not ctx.input_guard.is_safe: return "prompt_maker"
        return "cache_check"

    def route_after_cache(state: GraphState) -> str:
        ctx = state["ctx"]
        if ctx.intent == QueryIntent.CACHE_HIT: return END
        return "planner"

    def route_after_planner(state: GraphState) -> str:
        ctx = state["ctx"]
        if ctx.errors: return "error_handler"
        if ctx.intent == QueryIntent.SECURITY_VIOLATION or getattr(ctx, "skip_retrieval", False):
            return "prompt_maker"
        return "query_expansion"

    def route_after_retrieval(state: GraphState) -> str:
        ctx = state["ctx"]
        if ctx.errors: return "error_handler"
        if getattr(ctx, "skip_reranker", False): return "assembly"
        return "reranking"

    def check_error_and_route(next_node: str):
        def router(state: GraphState) -> str:
            if state["ctx"].errors: return "error_handler"
            return next_node
        return router

    # --- Graph Assembly ---
    g = StateGraph(GraphState)

    g.add_node("input_guard", node_input_guard)
    g.add_node("cache_check", node_cache_check)
    g.add_node("planner", node_planner)
    g.add_node("query_expansion", node_query_expansion)
    g.add_node("retrieval", node_retrieval)
    g.add_node("reranking", node_reranking)
    g.add_node("filtering", node_filtering)
    g.add_node("assembly", node_assembly)
    g.add_node("compression", node_compression)
    g.add_node("packing", node_packing)
    g.add_node("prompt_maker", node_prompt_maker)
    g.add_node("generator", node_generator)
    g.add_node("cache_save", node_cache_save)
    g.add_node("post_check", node_post_check)
    g.add_node("error_handler", node_error_handler)

    g.set_entry_point("input_guard")
    
    g.add_conditional_edges("input_guard", route_after_input_guard, {
        "cache_check": "cache_check",
        "prompt_maker": "prompt_maker",
        "error_handler": "error_handler"
    })

    g.add_conditional_edges("cache_check", route_after_cache, {
        "planner": "planner",
        END: END
    })

    g.add_conditional_edges("planner", route_after_planner, {
        "query_expansion": "query_expansion", 
        "prompt_maker": "prompt_maker",   
        "error_handler": "error_handler"     
    })

    g.add_conditional_edges("retrieval", route_after_retrieval, {
        "reranking": "reranking",
        "assembly": "assembly", 
        "error_handler": "error_handler"
    })

    g.add_conditional_edges("query_expansion", check_error_and_route("retrieval"))
    g.add_conditional_edges("reranking", check_error_and_route("filtering"))
    g.add_conditional_edges("filtering", check_error_and_route("assembly"))
    g.add_conditional_edges("assembly", check_error_and_route("compression"))
    g.add_conditional_edges("compression", check_error_and_route("packing"))
    g.add_conditional_edges("packing", check_error_and_route("prompt_maker"))
    g.add_conditional_edges("prompt_maker", check_error_and_route("generator"))
    g.add_conditional_edges("generator", check_error_and_route("cache_save"))
    g.add_conditional_edges("cache_save", check_error_and_route("post_check"))
    g.add_conditional_edges("post_check", check_error_and_route(END))

    g.add_edge("error_handler", END)

    return g.compile()