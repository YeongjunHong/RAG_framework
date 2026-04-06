# import asyncio
# import uuid
# import time
# import logging
# from colorama import Fore, Style, init

# from src.rag.core.types import RagRequest, RagContext
# from src.rag.graph import build_graph

# # --- [추가된 로깅 설정] ---
# # 파이프라인 내부의 모든 logger 출력을 터미널이 아닌 파일로 리다이렉트
# logging.basicConfig(
#     filename='demo_system.log',
#     filemode='w',
#     level=logging.INFO,
#     format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
# )
# # 터미널에 출력되는 스트림 핸들러가 있다면 제거 (colorama print만 살림)
# logging.getLogger().handlers = [h for h in logging.getLogger().handlers if not isinstance(h, logging.StreamHandler)]

# init(autoreset=True)

# async def stream_consumer(queue: asyncio.Queue):
#     print(f"{Fore.CYAN}[Streaming]{Style.RESET_ALL} ", end="", flush=True)
#     while True:
#         token = await queue.get()
#         if token is None: 
#             break
#         print(f"{Fore.GREEN}{token}{Style.RESET_ALL}", end="", flush=True)
#     print("\n")

# async def run_scenario(app, query: str, scenario_name: str):
#     print(f"\n{'='*70}")
#     print(f"{Fore.YELLOW} [Scenario] {scenario_name}{Style.RESET_ALL}")
#     print(f"{Fore.YELLOW} [Query] {query}{Style.RESET_ALL}")
#     print(f"{'-'*70}")

#     trace_id = str(uuid.uuid4())[:8]
#     request = RagRequest(trace_id=trace_id, user_query=query)
    
#     stream_queue = asyncio.Queue()
#     ctx = RagContext(stream_queue=stream_queue)
#     state = {"request": request, "ctx": ctx}

#     start_time = time.time()

#     graph_task = asyncio.create_task(app.ainvoke(state))
#     await stream_consumer(stream_queue)
    
#     final_state = await graph_task
#     final_ctx = final_state["ctx"]
#     elapsed_time = time.time() - start_time

#     print(f"{'-'*70}")
#     print(f"{Fore.MAGENTA}[Pipeline Routing & DB Retrieval Report]{Style.RESET_ALL}")
#     print(f"  - Trace ID      : {trace_id}")
#     print(f"  - Detected Intent: {Fore.CYAN}{getattr(final_ctx, 'intent', 'unknown')}{Style.RESET_ALL}")
    
#     retrieval_status = "SKIPPED" if getattr(final_ctx, "skip_retrieval", False) else "EXECUTED"
#     reranker_status = "SKIPPED" if getattr(final_ctx, "skip_reranker", False) else "EXECUTED"
    
#     print(f"  - DB Retrieval  : {retrieval_status}")
#     print(f"  - Reranker      : {reranker_status}")
    
#     # 실제 DB 연동 확인을 위한 로깅 강화
#     if not getattr(final_ctx, "skip_retrieval", False):
#         retrieved_count = len(getattr(final_ctx, "retrieved", []))
#         reranked_count = len(getattr(final_ctx, "reranked", []))
#         packed_len = len(getattr(final_ctx, "packed_context", ""))
        
#         print(f"  - DB Fetched Chunks : {retrieved_count} 건 (from pgvector & BM25)")
#         if reranker_status == "EXECUTED":
#             print(f"  - Reranked Chunks   : {reranked_count} 건")
#         print(f"  - Assembled Context : {packed_len} characters loaded into Prompt.")
        
#     print(f"  - Total Latency : {elapsed_time:.2f} seconds")
#     print(f"{'='*70}\n")

# async def main():
#     print(f"{Fore.BLUE}{Style.BRIGHT} Finance RAG Pipeline Demo {Style.RESET_ALL}\n")
    
#     print("그래프를 빌드하고 PostgreSQL(pgvector) 및 레지스트리를 초기화합니다...")
#     app = build_graph()
#     print("초기화 완료. 데모를 시작합니다.\n")

#     # 금융, 카드, 정책 데이터셋에 맞춘 시나리오
#     scenarios = [
#         {
#             "name": "Semantic Router (Fast Path - No DB)",
#             "query": "안녕! 오늘 시스템 상태 어때?"
#         },
#         {
#             "name": "Simple Fact Retrieval (Skip Reranker)",
#             # BCCard 데이터셋 타겟팅
#             "query": "BC카드 고객센터 전화번호와 운영 시간을 알려줘."
#         },
#         {
#             "name": "Complex Finance Analysis (Full Pipeline + DB + Reranker)",
#             # KoInFoBench / 정책 데이터셋 타겟팅
#             "query": "신용카드 리볼빙 서비스의 개념을 설명하고, 이것이 개인 신용도와 금융권의 건전성에 미치는 영향을 문서에 기반해서 분석해줘."
#         }
#     ]

#     for sc in scenarios:
#         await run_scenario(app, sc["query"], sc["name"])
#         await asyncio.sleep(1.5)

#     print(f"\n{'='*70}")
#     print(f"{Fore.GREEN} [Interactive Mode] 데모 시나리오 종료. 자유롭게 쿼리를 입력하세요. (종료: 'q'){Style.RESET_ALL}")
    
#     while True:
#         user_input = input(f"\n{Fore.CYAN}Live Query > {Style.RESET_ALL}").strip()
#         if user_input.lower() in ['q', 'quit', 'exit']:
#             print("데모를 종료합니다.")
#             break
#         if not user_input:
#             continue
            
#         await run_scenario(app, user_input, "Live Interactive Run")

# if __name__ == "__main__":
#     asyncio.run(main())

import asyncio
import uuid
import time
import logging
from colorama import Fore, Style, init

from src.rag.core.types import RagRequest, RagContext
from src.rag.graph import build_graph

# --- [추가된 로깅 설정] ---
logging.basicConfig(
    filename='demo_system.log',
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
)
logging.getLogger().handlers = [h for h in logging.getLogger().handlers if not isinstance(h, logging.StreamHandler)]

init(autoreset=True)

async def stream_consumer(queue: asyncio.Queue):
    print(f"{Fore.CYAN}[Streaming]{Style.RESET_ALL} ", end="", flush=True)
    try:
        while True:
            token = await queue.get()
            if token is None: 
                break
            print(f"{Fore.GREEN}{token}{Style.RESET_ALL}", end="", flush=True)
    except asyncio.CancelledError:
        # Planner에 의해 스트리밍이 강제 종료/스킵되었을 때의 안전한 종료 처리
        pass
    print("\n")

async def run_scenario(app, query: str, scenario_name: str, stream_response: bool = True):
    print(f"\n{'='*70}")
    print(f"{Fore.YELLOW} [Scenario] {scenario_name}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW} [Query] {query}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW} [Client Stream Req] {stream_response}{Style.RESET_ALL}")
    print(f"{'-'*70}")

    trace_id = str(uuid.uuid4())[:8]
    # 클라이언트의 스트리밍 요청 상태를 Request에 주입
    request = RagRequest(trace_id=trace_id, user_query=query, stream_response=stream_response)
    
    stream_queue = asyncio.Queue()
    ctx = RagContext(stream_queue=stream_queue)
    state = {"request": request, "ctx": ctx}

    start_time = time.time()

    # 그래프 실행과 스트리밍 출력을 비동기 태스크로 분리
    graph_task = asyncio.create_task(app.ainvoke(state))
    consumer_task = asyncio.create_task(stream_consumer(stream_queue))
    
    # 둘 중 하나라도 먼저 끝나면 반환 (동시성 제어)
    done, pending = await asyncio.wait(
        [graph_task, consumer_task], 
        return_when=asyncio.FIRST_COMPLETED
    )
    
    if graph_task in done:
        # 그래프 파이프라인이 먼저 끝났다면 (예: Planner가 스트리밍을 닫아버린 경우)
        # 멈춰있는 컨슈머 태스크를 강제 종료하여 메모리 누수 방지
        if not consumer_task.done():
            consumer_task.cancel()
    else:
        # 스트리밍이 정상적으로 끝났다면, 파이프라인의 최종 상태 정리를 기다림
        await graph_task
        
    final_state = graph_task.result()
    final_ctx = final_state["ctx"]
    elapsed_time = time.time() - start_time

    # 스트리밍이 OFF된 모드였다면, 최종 완성된 텍스트를 한 번에 출력
    if not getattr(final_ctx, 'is_streaming', True) and getattr(final_ctx, 'raw_generation', None):
        print(f"\n{Fore.CYAN}[Generated Output (Non-Streaming / Batch Output)]{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{final_ctx.raw_generation}{Style.RESET_ALL}\n")

    print(f"{'-'*70}")
    print(f"{Fore.MAGENTA}[Pipeline Routing & Execution Report]{Style.RESET_ALL}")
    print(f"  - Trace ID      : {trace_id}")
    print(f"  - Detected Intent: {Fore.CYAN}{getattr(final_ctx, 'intent', 'unknown')}{Style.RESET_ALL}")
    
    print(f"  - Stream Mode   : {'ON' if getattr(final_ctx, 'is_streaming', True) else 'OFF'}")
    print(f"  - Strict Valid. : {'ON' if getattr(final_ctx, 'strict_validation', False) else 'OFF'}")
    
    retrieval_status = "SKIPPED" if getattr(final_ctx, "skip_retrieval", False) else "EXECUTED"
    reranker_status = "SKIPPED" if getattr(final_ctx, "skip_reranker", False) else "EXECUTED"
    
    print(f"  - DB Retrieval  : {retrieval_status}")
    print(f"  - Reranker      : {reranker_status}")
    
    if not getattr(final_ctx, "skip_retrieval", False):
        retrieved_count = len(getattr(final_ctx, "retrieved", []))
        reranked_count = len(getattr(final_ctx, "reranked", []))
        packed_len = len(getattr(final_ctx, "packed_context", ""))
        
        print(f"  - DB Fetched Chunks : {retrieved_count} 건")
        if reranker_status == "EXECUTED":
            print(f"  - Reranked Chunks   : {reranked_count} 건")
        print(f"  - Assembled Context : {packed_len} chars loaded.")
        
    print(f"  - Total Latency : {elapsed_time:.2f} seconds")
    print(f"{'='*70}\n")

async def main():
    print(f"{Fore.BLUE}{Style.BRIGHT} Finance RAG Pipeline Demo (Routing & Post-Check Ready) {Style.RESET_ALL}\n")
    
    print("그래프를 빌드하고 PostgreSQL(pgvector) 및 레지스트리를 초기화합니다...")
    app = build_graph()
    print("초기화 완료. 데모를 시작합니다.\n")

    scenarios = [
        {
            "name": "Semantic Router (Fast Path - No DB)",
            "query": "안녕! 오늘 시스템 상태 어때?",
            "stream": True
        },
        {
            "name": "Simple Fact Retrieval (Skip Reranker)",
            "query": "BC카드 고객센터 전화번호와 운영 시간을 알려줘.",
            "stream": True
        },
        {
            "name": "Complex Finance Analysis (Full Pipeline + DB + Reranker)",
            "query": "신용카드 리볼빙 서비스의 개념을 설명하고, 이것이 개인 신용도와 금융권의 건전성에 미치는 영향을 문서에 기반해서 분석해줘.",
            "stream": True
        },
        {
            "name": "Authoring Mode (Dynamic Strict Validation & Stream OFF)",
            "query": "제공된 문서들을 바탕으로 신입사원을 위한 금융 보안 가이드 문서를 작성해줘.",
            "stream": True # 클라이언트가 True를 보냈음에도 Planner가 강제로 False로 바꿈을 확인
        },
        {
            "name": "Client Explicit Non-Streaming Request",
            "query": "금리 인상이 부동산 대출에 미치는 영향을 요약해줘.",
            "stream": False # 클라이언트가 명시적으로 스트리밍을 거부함
        }
    ]

    for sc in scenarios:
        await run_scenario(app, sc["query"], sc["name"], sc["stream"])
        await asyncio.sleep(1.5)

    print(f"\n{'='*70}")
    print(f"{Fore.GREEN} [Interactive Mode] 데모 시나리오 종료. 자유롭게 쿼리를 입력하세요. (종료: 'q'){Style.RESET_ALL}")
    
    while True:
        user_input = input(f"\n{Fore.CYAN}Live Query > {Style.RESET_ALL}").strip()
        if user_input.lower() in ['q', 'quit', 'exit']:
            print("데모를 종료합니다.")
            break
        if not user_input:
            continue
            
        await run_scenario(app, user_input, "Live Interactive Run", True)

if __name__ == "__main__":
    asyncio.run(main())