# from typing import TypedDict

# from .core.types import SourceChunk, RagRequest, RagResponse, RagContext
# from .stages.query_expansion import QueryExpansionStage, QueryExpansionConfig
# from .stages.retrieval import RetrievalStage, RetrievalConfig
# from .stages.reranking import RerankingStage, RerankingConfig
# from .stages.filtering import FilteringStage, FilteringConfig
# from .stages.assembly import AssemblyStage, AssemblyConfig
# from .stages.compression import CompressionStage, CompressionConfig
# from .stages.packing import PackingStage, PackingConfig
# from .stages.prompt_maker import PromptMakerStage, PromptMakerConfig
# from .stages.generator import GeneratorStage, GeneratorConfig
# from .stages.post_check import PostCheckStage, PostCheckConfig, to_response
# from .plugins.router import build_llm
# from .plugins.tracing import build_tracer
# from .plugins.noop import NoopReranker
# from .plugins.inmemory import InMemoryRetriever
# import src.rag.services.wiring as wiring

# class GraphState(TypedDict):
#     request: RagRequest
#     ctx: RagContext

# def build_graph():
#     from langgraph.graph import StateGraph, END

#     tracer = build_tracer()
#     llm = build_llm()

#     # 수정 
#     # from src.rag.plugins.openrouter_generator import OpenRouterGenerator
#     # llm = OpenRouterGenerator()


#     # registry
#     query_expander_registry = wiring.build_query_expander_registry()
#     retriever_registry = wiring.build_retriever_registry()
#     reranker_registry = wiring.build_reranker_registry()
#     filterer_registry = wiring.build_filterer_registry()
#     assembler_registry = wiring.build_assembler_registry()
#     compressor_registry = wiring.build_compressor_registry()
#     packer_registry = wiring.build_packer_registry()
#     promptmaker_registry = wiring.build_promptmaker_registry()
#     generator_registry = wiring.build_generator_registry()
#     postchecker_registry = wiring.build_postchecker_registry()

    
#     # Choose retriever implementation here (in-memory by default to avoid external deps)
#     sample_chunks = [
#         SourceChunk(chunk_id=1, source_id=1, source_name="mock", content="샘플 컨텍스트입니다. pgvector, bm25, tsvector를 함께 씁니다.", metadata={}),
#         SourceChunk(chunk_id=2, source_id=1, source_name="mock", content="LangGraph로 agentic routing를 구현할 계획입니다.", metadata={}),
#     ]
#     retriever_registry.items["default"]._chunks = sample_chunks

#     # Stages
#     qx = QueryExpansionStage(QueryExpansionConfig())
#     rt = RetrievalStage(RetrievalConfig(), registry=retriever_registry, tracer=tracer)
#     rr = RerankingStage(RerankingConfig(), registry=reranker_registry, tracer=tracer)
#     flt = FilteringStage(FilteringConfig(min_score=0.0))
#     asm = AssemblyStage(AssemblyConfig())
#     cmp = CompressionStage(CompressionConfig())
#     pck = PackingStage(PackingConfig())
#     pm = PromptMakerStage(PromptMakerConfig())
#     gen = GeneratorStage(GeneratorConfig(), llm=llm, tracer=tracer)
#     pc = PostCheckStage(PostCheckConfig(enable_guardrails=False))

#     async def node_query_expansion(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await qx(req, ctx)
#         return state

#     async def node_retrieval(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await rt(req, ctx)
#         return state

#     async def node_reranking(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await rr(req, ctx)
#         return state

#     async def node_filtering(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await flt(req, ctx)
#         return state

#     async def node_assembly(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await asm(req, ctx)
#         return state

#     async def node_compression(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await cmp(req, ctx)
#         return state

#     async def node_packing(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await pck(req, ctx)
#         return state

#     async def node_prompt_maker(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await pm(req, ctx)
#         return state

#     async def node_generator(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await gen(req, ctx)
#         return state

#     async def node_post_check(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await pc(req, ctx)
#         return state

#     # Agentic planner (minimal skeleton): choose plan_id / weights / model based on request knobs
#     async def node_planner(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         # Example: more strict plan for high safety
#         if req.safety_level == "high":
#             ctx.plan_id = "strict"
#             ctx.plan = {"bm25_weight": 0.7, "vector_weight": 0.3, "postcheck": "strict"}
#         else:
#             ctx.plan_id = "default"
#             ctx.plan = {"bm25_weight": 0.5, "vector_weight": 0.5, "postcheck": "basic"}
#         return state

#     def route_after_planner(state: GraphState) -> str:
#         # Example routing: could skip expansion for very short queries
#         q = state["request"].user_query.strip()
#         if len(q) <= 2:
#             return "retrieval"
#         return "query_expansion"

#     g = StateGraph(GraphState)

#     g.add_node("planner", node_planner)
#     g.add_node("query_expansion", node_query_expansion)
#     g.add_node("retrieval", node_retrieval)
#     g.add_node("reranking", node_reranking)
#     g.add_node("filtering", node_filtering)
#     g.add_node("assembly", node_assembly)
#     g.add_node("compression", node_compression)
#     g.add_node("packing", node_packing)
#     g.add_node("prompt_maker", node_prompt_maker)
#     g.add_node("generator", node_generator)
#     g.add_node("post_check", node_post_check)

#     g.set_entry_point("planner")
#     g.add_conditional_edges("planner", route_after_planner, {
#         "query_expansion": "query_expansion",
#         "retrieval": "retrieval",
#     })

#     g.add_edge("query_expansion", "retrieval")
#     g.add_edge("retrieval", "reranking")
#     g.add_edge("reranking", "filtering")
#     g.add_edge("filtering", "assembly")
#     g.add_edge("assembly", "compression")
#     g.add_edge("compression", "packing")
#     g.add_edge("packing", "prompt_maker")
#     g.add_edge("prompt_maker", "generator")
#     g.add_edge("generator", "post_check")
#     g.add_edge("post_check", END)

#     return g.compile()


# async def run_graph(app, request: RagRequest) -> RagResponse:
#     state: GraphState = {"request": request, "ctx": RagContext()}
#     out = await app.ainvoke(state)
#     return to_response(out["request"], out["ctx"])

# from typing import TypedDict

# from .core.types import SourceChunk, RagRequest, RagResponse, RagContext
# from .stages.planner import PlannerStage, PlannerConfig  # 새로 추가된 Planner 임포트
# from .stages.query_expansion import QueryExpansionStage, QueryExpansionConfig
# from .stages.retrieval import RetrievalStage, RetrievalConfig
# from .stages.reranking import RerankingStage, RerankingConfig
# from .stages.filtering import FilteringStage, FilteringConfig
# from .stages.assembly import AssemblyStage, AssemblyConfig
# from .stages.compression import CompressionStage, CompressionConfig
# from .stages.packing import PackingStage, PackingConfig
# from .stages.prompt_maker import PromptMakerStage, PromptMakerConfig
# from .stages.generator import GeneratorStage, GeneratorConfig
# from .stages.post_check import PostCheckStage, PostCheckConfig, to_response
# from .plugins.router import build_llm
# from .plugins.tracing import build_tracer
# from .plugins.noop import NoopReranker
# from .plugins.inmemory import InMemoryRetriever
# import src.rag.services.wiring as wiring

# class GraphState(TypedDict):
#     request: RagRequest
#     ctx: RagContext

# def build_graph():
#     from langgraph.graph import StateGraph, END

#     tracer = build_tracer()
#     llm = build_llm()

#     # registry 조립
#     planner_registry = wiring.build_planner_registry()  # 플래너 레지스트리 추가
#     query_expander_registry = wiring.build_query_expander_registry()
#     retriever_registry = wiring.build_retriever_registry()
#     reranker_registry = wiring.build_reranker_registry()
#     filterer_registry = wiring.build_filterer_registry()
#     assembler_registry = wiring.build_assembler_registry()
#     compressor_registry = wiring.build_compressor_registry()
#     packer_registry = wiring.build_packer_registry()
#     promptmaker_registry = wiring.build_promptmaker_registry()
#     generator_registry = wiring.build_generator_registry()
#     postchecker_registry = wiring.build_postchecker_registry()

    
#     # Choose retriever implementation here 
#     sample_chunks = [
#         SourceChunk(chunk_id=1, source_id=1, source_name="mock", content="샘플 컨텍스트입니다. pgvector, bm25, tsvector를 함께 씁니다.", metadata={}),
#         SourceChunk(chunk_id=2, source_id=1, source_name="mock", content="LangGraph로 agentic routing를 구현할 계획입니다.", metadata={}),
#     ]
#     # DB(Postgres) 사용 시 _chunks 속성이 없어 터지는 버그 방어 로직 추가
#     if hasattr(retriever_registry.items["default"], "_chunks"):
#         retriever_registry.items["default"]._chunks = sample_chunks

#     # Stages 인스턴스화
#     pln = PlannerStage(PlannerConfig(), registry=planner_registry, tracer=tracer) # 플래너 스테이지 객체 생성
#     qx = QueryExpansionStage(QueryExpansionConfig())
#     rt = RetrievalStage(RetrievalConfig(), registry=retriever_registry, tracer=tracer)
#     rr = RerankingStage(RerankingConfig(), registry=reranker_registry, tracer=tracer)
#     flt = FilteringStage(FilteringConfig(min_score=0.0))
#     asm = AssemblyStage(AssemblyConfig())
#     cmp = CompressionStage(CompressionConfig())
#     pck = PackingStage(PackingConfig())
#     pm = PromptMakerStage(PromptMakerConfig())
#     gen = GeneratorStage(GeneratorConfig(), llm=llm, tracer=tracer)
#     pc = PostCheckStage(PostCheckConfig(enable_guardrails=False))

#     # --- Node 래퍼 함수들 ---
#     async def node_planner(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         # 우리가 만든 실제 sLM Planner Stage 호출
#         await pln(req, ctx)
#         return state

#     async def node_query_expansion(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await qx(req, ctx)
#         return state

#     async def node_retrieval(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await rt(req, ctx)
#         return state

#     async def node_reranking(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await rr(req, ctx)
#         return state

#     async def node_filtering(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await flt(req, ctx)
#         return state

#     async def node_assembly(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await asm(req, ctx)
#         return state

#     async def node_compression(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await cmp(req, ctx)
#         return state

#     async def node_packing(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await pck(req, ctx)
#         return state

#     async def node_prompt_maker(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await pm(req, ctx)
#         return state

#     async def node_generator(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await gen(req, ctx)
#         return state

#     async def node_post_check(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await pc(req, ctx)
#         return state

#     # --- 라우팅 (Conditional Edge) 로직 ---
#     def route_after_planner(state: GraphState) -> str:
#         ctx = state["ctx"]
#         # 안전한 딕셔너리 조회를 위해 get 메서드 사용
#         plan = ctx.plan if isinstance(ctx.plan, dict) else {}
#         intent = plan.get("intent", "search")
#         requires_db = plan.get("requires_db", True)
        
#         # sLM이 '인사말/잡담'이거나 'DB 검색이 필요 없다'고 판단한 경우
#         if intent == "chitchat" or not requires_db:
#             # 검색(Retrieval) 노드들을 전부 스킵하고 바로 프롬프트 메이커로 직행 (Fast Path)
#             return "prompt_maker"
            
#         # 기본값: 복잡한 지식 검색이 필요한 경우 쿼리 확장 노드로 이동
#         return "query_expansion"

#     # --- LangGraph 조립 ---
#     g = StateGraph(GraphState)

#     g.add_node("planner", node_planner)
#     g.add_node("query_expansion", node_query_expansion)
#     g.add_node("retrieval", node_retrieval)
#     g.add_node("reranking", node_reranking)
#     g.add_node("filtering", node_filtering)
#     g.add_node("assembly", node_assembly)
#     g.add_node("compression", node_compression)
#     g.add_node("packing", node_packing)
#     g.add_node("prompt_maker", node_prompt_maker)
#     g.add_node("generator", node_generator)
#     g.add_node("post_check", node_post_check)

#     # 시작점
#     g.set_entry_point("planner")
    
#     # 조건부 엣지 (플래너 판단에 따른 분기 처리)
#     g.add_conditional_edges("planner", route_after_planner, {
#         "query_expansion": "query_expansion",  # DB 검색 경로
#         "prompt_maker": "prompt_maker",        # DB 스킵 경로
#     })

#     # 선형 파이프라인 엣지
#     g.add_edge("query_expansion", "retrieval")
#     g.add_edge("retrieval", "reranking")
#     g.add_edge("reranking", "filtering")
#     g.add_edge("filtering", "assembly")
#     g.add_edge("assembly", "compression")
#     g.add_edge("compression", "packing")
#     g.add_edge("packing", "prompt_maker")
#     g.add_edge("prompt_maker", "generator")
#     g.add_edge("generator", "post_check")
#     g.add_edge("post_check", END)

#     return g.compile()


# async def run_graph(app, request: RagRequest) -> RagResponse:
#     state: GraphState = {"request": request, "ctx": RagContext()}
#     out = await app.ainvoke(state)
#     return to_response(out["request"], out["ctx"])

# from typing import TypedDict

# from .core.types import SourceChunk, RagRequest, RagResponse, RagContext
# from .stages.planner import PlannerStage, PlannerConfig
# from .stages.query_expansion import QueryExpansionStage, QueryExpansionConfig
# from .stages.retrieval import RetrievalStage, RetrievalConfig
# from .stages.reranking import RerankingStage, RerankingConfig
# from .stages.filtering import FilteringStage, FilteringConfig
# from .stages.assembly import AssemblyStage, AssemblyConfig
# from .stages.compression import CompressionStage, CompressionConfig
# from .stages.packing import PackingStage, PackingConfig
# from .stages.prompt_maker import PromptMakerStage, PromptMakerConfig
# from .stages.generator import GeneratorStage, GeneratorConfig
# from .stages.post_check import PostCheckStage, PostCheckConfig, to_response
# from .plugins.router import build_llm
# from .plugins.tracing import build_tracer
# from .plugins.noop import NoopReranker
# from .plugins.inmemory import InMemoryRetriever
# import src.rag.services.wiring as wiring
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class GraphState(TypedDict):
#     request: RagRequest
#     ctx: RagContext

# def build_graph():
#     from langgraph.graph import StateGraph, END

#     tracer = build_tracer()
#     llm = build_llm()

#     # Registry 조립
#     planner_registry = wiring.build_planner_registry()
#     query_expander_registry = wiring.build_query_expander_registry()
#     retriever_registry = wiring.build_retriever_registry()
#     reranker_registry = wiring.build_reranker_registry()
#     filterer_registry = wiring.build_filterer_registry()
#     assembler_registry = wiring.build_assembler_registry()
#     compressor_registry = wiring.build_compressor_registry()
#     packer_registry = wiring.build_packer_registry()
#     promptmaker_registry = wiring.build_promptmaker_registry()
#     generator_registry = wiring.build_generator_registry()
#     postchecker_registry = wiring.build_postchecker_registry()

#     # 테스트 및 디버깅용 Mock 데이터 
#     # sample_chunks = [
#     #     SourceChunk(chunk_id=1, source_id=1, source_name="mock", content="샘플 컨텍스트입니다. pgvector, bm25, tsvector를 함께 씁니다.", metadata={}),
#     #     SourceChunk(chunk_id=2, source_id=1, source_name="mock", content="LangGraph로 agentic routing를 구현할 계획입니다.", metadata={}),
#     # ]
#     # if hasattr(retriever_registry.items["default"], "_chunks"):
#     #     retriever_registry.items["default"]._chunks = sample_chunks

#     # Stages 인스턴스화
#     pln = PlannerStage(PlannerConfig(), registry=planner_registry, tracer=tracer)
#     qx = QueryExpansionStage(QueryExpansionConfig())
#     rt = RetrievalStage(RetrievalConfig(), registry=retriever_registry, tracer=tracer)
#     rr = RerankingStage(RerankingConfig(), registry=reranker_registry, tracer=tracer)
#     # flt = FilteringStage(FilteringConfig(min_score=0.0))
#     flt = FilteringStage(FilteringConfig())
#     asm = AssemblyStage(AssemblyConfig())
#     cmp = CompressionStage(CompressionConfig())
#     pck = PackingStage(PackingConfig(), tracer=tracer)
#     pm = PromptMakerStage(PromptMakerConfig())
#     gen = GeneratorStage(GeneratorConfig(), llm=llm, tracer=tracer)
#     # pc = PostCheckStage(PostCheckConfig(enable_guardrails=False))
#     pc = PostCheckStage(
#         PostCheckConfig(), 
#         guardrails_plugin=postchecker_registry.get("default"), 
#         tracer=tracer
#     )

#     # --- Node 래퍼 함수들 ---
#     async def node_planner(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await pln(req, ctx)
#         return state

#     async def node_query_expansion(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await qx(req, ctx)
#         return state

#     async def node_retrieval(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await rt(req, ctx)
#         return state

#     async def node_reranking(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await rr(req, ctx)
#         return state

#     async def node_filtering(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await flt(req, ctx)
#         return state

#     async def node_assembly(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await asm(req, ctx)
#         return state

#     async def node_compression(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await cmp(req, ctx)
#         return state

#     async def node_packing(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await pck(req, ctx)
#         return state

#     async def node_prompt_maker(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await pm(req, ctx)
#         return state

#     async def node_generator(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await gen(req, ctx)
#         return state

#     async def node_post_check(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         await pc(req, ctx)
#         return state

#     # --- 라우팅 (Conditional Edge) 로직 ---
#     def route_after_planner(state: GraphState) -> str:
#         ctx = state["ctx"]
        
#         # Planner가 검색 생략을 결정한 경우 (인사말 등)
#         if getattr(ctx, "skip_retrieval", False):
#             logger.info("[Router] 검색 파이프라인 스킵 -> Prompt Maker 직행")
#             return "prompt_maker"
            
#         logger.info("[Router] 검색 파이프라인 진입 -> Query Expansion")
#         return "query_expansion"

#     def route_after_retrieval(state: GraphState) -> str:
#         ctx = state["ctx"]
        
#         # Planner가 무거운 리랭커 연산을 생략하기로 결정한 경우 (단순 정보 검색 등)
#         if getattr(ctx, "skip_reranker", False):
#             logger.info("[Router] Reranker 스킵 -> Assembly 직행")
#             return "assembly"
            
#         logger.info("[Router] Reranker 파이프라인 진입")
#         return "reranking"

#     # --- LangGraph 조립 ---
#     g = StateGraph(GraphState)

#     # 1. 노드 등록
#     g.add_node("planner", node_planner)
#     g.add_node("query_expansion", node_query_expansion)
#     g.add_node("retrieval", node_retrieval)
#     g.add_node("reranking", node_reranking)
#     g.add_node("filtering", node_filtering)
#     g.add_node("assembly", node_assembly)
#     g.add_node("compression", node_compression)
#     g.add_node("packing", node_packing)
#     g.add_node("prompt_maker", node_prompt_maker)
#     g.add_node("generator", node_generator)
#     g.add_node("post_check", node_post_check)

#     # 2. 시작점
#     g.set_entry_point("planner")
    
#     # 3. 조건부 엣지 (다중 분기 처리)
#     g.add_conditional_edges("planner", route_after_planner, {
#         "query_expansion": "query_expansion", 
#         "prompt_maker": "prompt_maker",        
#     })

#     g.add_conditional_edges("retrieval", route_after_retrieval, {
#         "reranking": "reranking",
#         "assembly": "assembly", 
#     })

#     # 4. 선형 파이프라인 엣지
#     g.add_edge("query_expansion", "retrieval")
#     # retrieval 이후는 조건부 엣지로 처리되므로 여기서는 제외
#     g.add_edge("reranking", "filtering")
#     g.add_edge("filtering", "assembly")
#     g.add_edge("assembly", "compression")
#     g.add_edge("compression", "packing")
#     g.add_edge("packing", "prompt_maker")
#     g.add_edge("prompt_maker", "generator")
#     g.add_edge("generator", "post_check")
#     g.add_edge("post_check", END)

#     return g.compile()

# async def run_graph(app, request: RagRequest) -> RagResponse:
#     state: GraphState = {"request": request, "ctx": RagContext()}
#     out = await app.ainvoke(state)
#     # return to_response(out["request"], out["ctx"])
#     return to_response(out)["response"]



# from typing import TypedDict, Callable
# from langgraph.graph import StateGraph, END

# from .core.types import SourceChunk, RagRequest, RagResponse, RagContext
# from .stages.input_guard import InputGuardStage
# from .stages.planner import PlannerStage, PlannerConfig
# from .stages.query_expansion import QueryExpansionStage, QueryExpansionConfig
# from .stages.retrieval import RetrievalStage, RetrievalConfig
# from .stages.reranking import RerankingStage, RerankingConfig
# from .stages.filtering import FilteringStage, FilteringConfig
# from .stages.assembly import AssemblyStage, AssemblyConfig
# from .stages.compression import CompressionStage, CompressionConfig
# from .stages.packing import PackingStage, PackingConfig
# from .stages.prompt_maker import PromptMakerStage, PromptMakerConfig
# from .stages.generator import GeneratorStage, GeneratorConfig
# from .stages.post_check import PostCheckStage, PostCheckConfig, to_response

# from .plugins.router import build_llm
# from .plugins.tracing import build_tracer
# from .plugins.cache_manager import SemanticCacheManager
# import src.rag.services.wiring as wiring
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class GraphState(TypedDict):
#     request: RagRequest
#     ctx: RagContext

# def build_graph():
#     tracer = build_tracer()
#     llm = build_llm()

#     # DB, Registry 및 Cache Manager 조립
#     db_session_maker = wiring.build_db_session_maker()
#     input_guard_registry = wiring.build_input_guard_registry()
    
#     # [Cache] 시맨틱 캐시 매니저 초기화
#     cache_manager = SemanticCacheManager(host="localhost", port=6379)
    
#     planner_registry = wiring.build_planner_registry()
#     query_expander_registry = wiring.build_query_expander_registry()
#     retriever_registry = wiring.build_retriever_registry()
#     reranker_registry = wiring.build_reranker_registry()
#     filter_registry = wiring.build_filterer_registry()
#     assembler_registry = wiring.build_assembler_registry()
#     text_compressor_registry = wiring.build_text_compressor_registry() 
#     packer_registry = wiring.build_packer_registry()
#     promptmaker_registry = wiring.build_promptmaker_registry()
#     generator_registry = wiring.build_generator_registry()
#     postchecker_registry = wiring.build_postchecker_registry()

#     # Stages 인스턴스화
#     ig = InputGuardStage(registry=input_guard_registry, tracer=tracer, db_session_maker=db_session_maker)
#     pln = PlannerStage(PlannerConfig(), registry=planner_registry, tracer=tracer)
#     qx = QueryExpansionStage(config=QueryExpansionConfig(mode="dynamic", max_expansions=4), registry=query_expander_registry, tracer=tracer)
#     rt = RetrievalStage(RetrievalConfig(), registry=retriever_registry, tracer=tracer)
#     rr = RerankingStage(RerankingConfig(), registry=reranker_registry, tracer=tracer)
#     flt = FilteringStage(FilteringConfig())
#     asm = AssemblyStage(AssemblyConfig())
#     cmp = CompressionStage(CompressionConfig(), registry=text_compressor_registry)
#     pck = PackingStage(PackingConfig(), tracer=tracer)
#     pm = PromptMakerStage(PromptMakerConfig())
#     gen = GeneratorStage(GeneratorConfig(), llm=llm, tracer=tracer)
#     pc = PostCheckStage(PostCheckConfig(), guardrails_plugin=postchecker_registry.get("default"), tracer=tracer)

#     # --- Circuit Breaker Pattern: Safe Node Wrapper ---
#     def make_safe_node(node_name: str, stage_callable: Callable) -> Callable:
#         async def safe_node_func(state: GraphState) -> GraphState:
#             req, ctx = state["request"], state["ctx"]
#             if ctx.errors: return state
#             try:
#                 await stage_callable(req, ctx)
#             except Exception as e:
#                 logger.error(f"[{node_name}] 파이프라인 치명적 예외 발생: {str(e)}", exc_info=True)
#                 ctx.errors.append({"node": node_name, "error": str(e), "type": type(e).__name__})
#             return state
#         return safe_node_func

#     node_input_guard = make_safe_node("input_guard", ig)
#     node_planner = make_safe_node("planner", pln)
#     node_query_expansion = make_safe_node("query_expansion", qx)
#     node_retrieval = make_safe_node("retrieval", rt)
#     node_reranking = make_safe_node("reranking", rr)
#     node_filtering = make_safe_node("filtering", flt)
#     node_assembly = make_safe_node("assembly", asm)
#     node_compression = make_safe_node("compression", cmp)
#     node_packing = make_safe_node("packing", pck)
#     node_prompt_maker = make_safe_node("prompt_maker", pm)
#     node_generator = make_safe_node("generator", gen)
#     node_post_check = make_safe_node("post_check", pc)

#     # --- [MODIFIED] Cache Check Node: 미스 시 intent 초기화 추가 ---
#     async def node_cache_check(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         cached_response = cache_manager.check_cache(req.user_query, threshold=0.90)
        
#         if cached_response:
#             ctx.raw_generation = cached_response
#             ctx.intent = "cache_hit"
#             logger.info("[Router] Cache HIT -> 파이프라인 우회 (END)")
#         else:
#             # 캐시 미스 시 intent를 비워두어 Planner가 새 의도를 채우게 함
#             ctx.intent = None 
#             logger.info("[Router] Cache MISS -> 정상 파이프라인 진입")
#         return state

#     async def node_cache_save(state: GraphState) -> GraphState:
#         req, ctx = state["request"], state["ctx"]
#         if not ctx.errors and getattr(ctx, "raw_generation", None) and getattr(ctx.input_guard, "is_safe", True):
#              cache_manager.save_cache(req.user_query, ctx.raw_generation)
#         return state

#     async def node_error_handler(state: GraphState) -> GraphState:
#         ctx = state["ctx"]
#         last_error_node = ctx.errors[-1]["node"] if ctx.errors else "unknown"
#         ctx.raw_generation = "현재 시스템 내부 연산 지연 또는 통신 장애가 발생하여 답변을 생성할 수 없습니다."
#         ctx.postcheck = {"is_valid": False, "reason": f"System Fallback triggered by {last_error_node}"}
#         return state

#     # --- Routing Logic ---
#     def route_after_input_guard(state: GraphState) -> str:
#         ctx = state["ctx"]
#         if ctx.errors: return "error_handler"
#         if not ctx.input_guard.is_safe: return "prompt_maker"
#         return "cache_check"

#     def route_after_cache(state: GraphState) -> str:
#         ctx = state["ctx"]
#         if ctx.intent == "cache_hit": return END
#         return "planner"

#     def route_after_planner(state: GraphState) -> str:
#         ctx = state["ctx"]
#         if ctx.errors: return "error_handler"
#         if ctx.intent == "security_violation" or getattr(ctx, "skip_retrieval", False):
#             return "prompt_maker"
#         return "query_expansion"

#     def route_after_retrieval(state: GraphState) -> str:
#         ctx = state["ctx"]
#         if ctx.errors: return "error_handler"
#         if getattr(ctx, "skip_reranker", False): return "assembly"
#         return "reranking"

#     def check_error_and_route(next_node: str):
#         def router(state: GraphState) -> str:
#             if state["ctx"].errors: return "error_handler"
#             return next_node
#         return router

#     # --- Graph Assembly ---
#     g = StateGraph(GraphState)

#     g.add_node("input_guard", node_input_guard)
#     g.add_node("cache_check", node_cache_check)
#     g.add_node("planner", node_planner)
#     g.add_node("query_expansion", node_query_expansion)
#     g.add_node("retrieval", node_retrieval)
#     g.add_node("reranking", node_reranking)
#     g.add_node("filtering", node_filtering)
#     g.add_node("assembly", node_assembly)
#     g.add_node("compression", node_compression)
#     g.add_node("packing", node_packing)
#     g.add_node("prompt_maker", node_prompt_maker)
#     g.add_node("generator", node_generator)
#     g.add_node("cache_save", node_cache_save)
#     g.add_node("post_check", node_post_check)
#     g.add_node("error_handler", node_error_handler)

#     g.set_entry_point("input_guard")
    
#     g.add_conditional_edges("input_guard", route_after_input_guard, {
#         "cache_check": "cache_check",
#         "prompt_maker": "prompt_maker",
#         "error_handler": "error_handler"
#     })

#     g.add_conditional_edges("cache_check", route_after_cache, {
#         "planner": "planner",
#         END: END
#     })

#     g.add_conditional_edges("planner", route_after_planner, {
#         "query_expansion": "query_expansion", 
#         "prompt_maker": "prompt_maker",   
#         "error_handler": "error_handler"     
#     })

#     g.add_conditional_edges("retrieval", route_after_retrieval, {
#         "reranking": "reranking",
#         "assembly": "assembly", 
#         "error_handler": "error_handler"
#     })

#     g.add_conditional_edges("query_expansion", check_error_and_route("retrieval"))
#     g.add_conditional_edges("reranking", check_error_and_route("filtering"))
#     g.add_conditional_edges("filtering", check_error_and_route("assembly"))
#     g.add_conditional_edges("assembly", check_error_and_route("compression"))
#     g.add_conditional_edges("compression", check_error_and_route("packing"))
#     g.add_conditional_edges("packing", check_error_and_route("prompt_maker"))
#     g.add_conditional_edges("prompt_maker", check_error_and_route("generator"))
#     g.add_conditional_edges("generator", check_error_and_route("cache_save"))
#     g.add_conditional_edges("cache_save", check_error_and_route("post_check"))
#     g.add_conditional_edges("post_check", check_error_and_route(END))

#     g.add_edge("error_handler", END)

#     return g.compile()

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

logger = get_logger(__name__)

class GraphState(TypedDict):
    request: RagRequest
    ctx: RagContext

def build_graph():
    tracer = build_tracer()
    llm = build_llm()

    db_session_maker = wiring.build_db_session_maker()
    input_guard_registry = wiring.build_input_guard_registry()
    
    cache_manager = SemanticCacheManager(host="localhost", port=6379)
    
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