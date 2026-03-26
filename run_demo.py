import asyncio
import uuid
import time
import logging
from colorama import Fore, Style, init

from src.rag.core.types import RagRequest, RagContext
from src.rag.graph import build_graph

# --- [추가된 로깅 설정] ---
# 파이프라인 내부의 모든 logger 출력을 터미널이 아닌 파일로 리다이렉트
logging.basicConfig(
    filename='demo_system.log',
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
)
# 터미널에 출력되는 스트림 핸들러가 있다면 제거 (colorama print만 살림)
logging.getLogger().handlers = [h for h in logging.getLogger().handlers if not isinstance(h, logging.StreamHandler)]

init(autoreset=True)

async def stream_consumer(queue: asyncio.Queue):
    print(f"{Fore.CYAN}[Streaming]{Style.RESET_ALL} ", end="", flush=True)
    while True:
        token = await queue.get()
        if token is None: 
            break
        print(f"{Fore.GREEN}{token}{Style.RESET_ALL}", end="", flush=True)
    print("\n")

async def run_scenario(app, query: str, scenario_name: str):
    print(f"\n{'='*70}")
    print(f"{Fore.YELLOW} [Scenario] {scenario_name}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW} [Query] {query}{Style.RESET_ALL}")
    print(f"{'-'*70}")

    trace_id = str(uuid.uuid4())[:8]
    request = RagRequest(trace_id=trace_id, user_query=query)
    
    stream_queue = asyncio.Queue()
    ctx = RagContext(stream_queue=stream_queue)
    state = {"request": request, "ctx": ctx}

    start_time = time.time()

    graph_task = asyncio.create_task(app.ainvoke(state))
    await stream_consumer(stream_queue)
    
    final_state = await graph_task
    final_ctx = final_state["ctx"]
    elapsed_time = time.time() - start_time

    print(f"{'-'*70}")
    print(f"{Fore.MAGENTA}[Pipeline Routing & DB Retrieval Report]{Style.RESET_ALL}")
    print(f"  - Trace ID      : {trace_id}")
    print(f"  - Detected Intent: {Fore.CYAN}{getattr(final_ctx, 'intent', 'unknown')}{Style.RESET_ALL}")
    
    retrieval_status = "SKIPPED" if getattr(final_ctx, "skip_retrieval", False) else "EXECUTED"
    reranker_status = "SKIPPED" if getattr(final_ctx, "skip_reranker", False) else "EXECUTED"
    
    print(f"  - DB Retrieval  : {retrieval_status}")
    print(f"  - Reranker      : {reranker_status}")
    
    # 실제 DB 연동 확인을 위한 로깅 강화
    if not getattr(final_ctx, "skip_retrieval", False):
        retrieved_count = len(getattr(final_ctx, "retrieved", []))
        reranked_count = len(getattr(final_ctx, "reranked", []))
        packed_len = len(getattr(final_ctx, "packed_context", ""))
        
        print(f"  - DB Fetched Chunks : {retrieved_count} 건 (from pgvector & BM25)")
        if reranker_status == "EXECUTED":
            print(f"  - Reranked Chunks   : {reranked_count} 건")
        print(f"  - Assembled Context : {packed_len} characters loaded into Prompt.")
        
    print(f"  - Total Latency : {elapsed_time:.2f} seconds")
    print(f"{'='*70}\n")

async def main():
    print(f"{Fore.BLUE}{Style.BRIGHT} Finance RAG Pipeline Demo {Style.RESET_ALL}\n")
    
    print("그래프를 빌드하고 PostgreSQL(pgvector) 및 레지스트리를 초기화합니다...")
    app = build_graph()
    print("초기화 완료. 데모를 시작합니다.\n")

    # 금융, 카드, 정책 데이터셋에 맞춘 시나리오
    scenarios = [
        {
            "name": "Semantic Router (Fast Path - No DB)",
            "query": "안녕! 오늘 시스템 상태 어때?"
        },
        {
            "name": "Simple Fact Retrieval (Skip Reranker)",
            # BCCard 데이터셋 타겟팅
            "query": "BC카드 고객센터 전화번호와 운영 시간을 알려줘."
        },
        {
            "name": "Complex Finance Analysis (Full Pipeline + DB + Reranker)",
            # KoInFoBench / 정책 데이터셋 타겟팅
            "query": "신용카드 리볼빙 서비스의 개념을 설명하고, 이것이 개인 신용도와 금융권의 건전성에 미치는 영향을 문서에 기반해서 분석해줘."
        }
    ]

    for sc in scenarios:
        await run_scenario(app, sc["query"], sc["name"])
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
            
        await run_scenario(app, user_input, "Live Interactive Run")

if __name__ == "__main__":
    asyncio.run(main())