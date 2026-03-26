from typing import TypedDict

from .core.types import SourceChunk, RagRequest, RagResponse, RagContext
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
from .plugins.noop import NoopReranker
from .plugins.inmemory import InMemoryRetriever
import src.rag.services.wiring as wiring

class GraphState(TypedDict):
    request: RagRequest
    ctx: RagContext

def build_graph():
    from langgraph.graph import StateGraph, END

    tracer = build_tracer()
    llm = build_llm()

    # 수정 
    # from src.rag.plugins.openrouter_generator import OpenRouterGenerator
    # llm = OpenRouterGenerator()


    # registry
    query_expander_registry = wiring.build_query_expander_registry()
    retriever_registry = wiring.build_retriever_registry()
    reranker_registry = wiring.build_reranker_registry()
    filterer_registry = wiring.build_filterer_registry()
    assembler_registry = wiring.build_assembler_registry()
    compressor_registry = wiring.build_compressor_registry()
    packer_registry = wiring.build_packer_registry()
    promptmaker_registry = wiring.build_promptmaker_registry()
    generator_registry = wiring.build_generator_registry()
    postchecker_registry = wiring.build_postchecker_registry()

    
    # Choose retriever implementation here (in-memory by default to avoid external deps)
    sample_chunks = [
        SourceChunk(chunk_id=1, source_id=1, source_name="mock", content="샘플 컨텍스트입니다. pgvector, bm25, tsvector를 함께 씁니다.", metadata={}),
        SourceChunk(chunk_id=2, source_id=1, source_name="mock", content="LangGraph로 agentic routing를 구현할 계획입니다.", metadata={}),
    ]
    retriever_registry.items["default"]._chunks = sample_chunks

    # Stages
    qx = QueryExpansionStage(QueryExpansionConfig())
    rt = RetrievalStage(RetrievalConfig(), registry=retriever_registry, tracer=tracer)
    rr = RerankingStage(RerankingConfig(), registry=reranker_registry, tracer=tracer)
    flt = FilteringStage(FilteringConfig(min_score=0.0))
    asm = AssemblyStage(AssemblyConfig())
    cmp = CompressionStage(CompressionConfig())
    pck = PackingStage(PackingConfig())
    pm = PromptMakerStage(PromptMakerConfig())
    gen = GeneratorStage(GeneratorConfig(), llm=llm, tracer=tracer)
    pc = PostCheckStage(PostCheckConfig(enable_guardrails=False))

    async def node_query_expansion(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        await qx(req, ctx)
        return state

    async def node_retrieval(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        await rt(req, ctx)
        return state

    async def node_reranking(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        await rr(req, ctx)
        return state

    async def node_filtering(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        await flt(req, ctx)
        return state

    async def node_assembly(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        await asm(req, ctx)
        return state

    async def node_compression(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        await cmp(req, ctx)
        return state

    async def node_packing(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        await pck(req, ctx)
        return state

    async def node_prompt_maker(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        await pm(req, ctx)
        return state

    async def node_generator(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        await gen(req, ctx)
        return state

    async def node_post_check(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        await pc(req, ctx)
        return state

    # Agentic planner (minimal skeleton): choose plan_id / weights / model based on request knobs
    async def node_planner(state: GraphState) -> GraphState:
        req, ctx = state["request"], state["ctx"]
        # Example: more strict plan for high safety
        if req.safety_level == "high":
            ctx.plan_id = "strict"
            ctx.plan = {"bm25_weight": 0.7, "vector_weight": 0.3, "postcheck": "strict"}
        else:
            ctx.plan_id = "default"
            ctx.plan = {"bm25_weight": 0.5, "vector_weight": 0.5, "postcheck": "basic"}
        return state

    def route_after_planner(state: GraphState) -> str:
        # Example routing: could skip expansion for very short queries
        q = state["request"].user_query.strip()
        if len(q) <= 2:
            return "retrieval"
        return "query_expansion"

    g = StateGraph(GraphState)

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
    g.add_node("post_check", node_post_check)

    g.set_entry_point("planner")
    g.add_conditional_edges("planner", route_after_planner, {
        "query_expansion": "query_expansion",
        "retrieval": "retrieval",
    })

    g.add_edge("query_expansion", "retrieval")
    g.add_edge("retrieval", "reranking")
    g.add_edge("reranking", "filtering")
    g.add_edge("filtering", "assembly")
    g.add_edge("assembly", "compression")
    g.add_edge("compression", "packing")
    g.add_edge("packing", "prompt_maker")
    g.add_edge("prompt_maker", "generator")
    g.add_edge("generator", "post_check")
    g.add_edge("post_check", END)

    return g.compile()


async def run_graph(app, request: RagRequest) -> RagResponse:
    state: GraphState = {"request": request, "ctx": RagContext()}
    out = await app.ainvoke(state)
    return to_response(out["request"], out["ctx"])
