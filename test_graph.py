import sys
import os
import asyncio
import uuid
from pathlib import Path
from dotenv import load_dotenv

# 1. 경로 설정 (src 모듈 임포트를 위해 필수)
current_file_path = Path(__file__).resolve()
project_root = current_file_path.parent
sys.path.append(str(project_root))

# 2. 환경변수 로드
env_path = project_root / "settings" / ".env.poc"
load_dotenv(dotenv_path=env_path)

from src.rag.graph import build_graph
from src.rag.core.types import RagRequest, RagContext
from src.rag.stages.post_check import to_response  # 경로에 맞춰 직접 임포트

async def main():
    print("RAG 파이프라인 그래프 빌드 중...")
    app = build_graph()
    
    test_query = "청년도약계좌나 청년주택드림청약통장 같은 청년 지원 금융 상품의 가입 조건이나 납입 관련 혜택이 어떻게 되나요?"
    print(f"\n[사용자 질문]: {test_query}\n")
    
    # 3. Request 객체 생성
    request = RagRequest(
        trace_id=str(uuid.uuid4()),
        user_query=test_query,
        safety_level="medium"
    )

    # 4. 스트리밍을 위한 비동기 큐 생성 및 Context에 주입
    token_queue = asyncio.Queue()
    ctx = RagContext(stream_queue=token_queue)
    state = {"request": request, "ctx": ctx}

    print("파이프라인 실행 중 (Planner -> Expansion -> Retrieval -> ...)\n")
    print("=" * 60)
    print("[최종 AI 답변] (스트리밍 중...)")
    
    # 5. 파이프라인(LangGraph) 실행을 백그라운드 태스크로 던짐 (이벤트 루프 블로킹 해제)
    graph_task = asyncio.create_task(app.ainvoke(state))

    # 6. 메인 스레드는 큐를 감시하며 들어오는 토큰을 즉시 화면에 출력 (Consumer)
    while True:
        token = await token_queue.get()
        if token is None:  # OpenRouterGenerator가 생성 완료 후 보낸 종료 시그널
            break
        # flush=True를 주어 버퍼에 담지 않고 터미널에 즉시 출력
        print(token, end="", flush=True)
    
    print("\n" + "=" * 60)

    # 7. 파이프라인의 모든 노드 실행(post_check 등)이 완전히 끝날 때까지 대기
    out_state = await graph_task
    
    # 8. 최종 상태를 Response 객체로 변환하여 메타데이터(Citations 등) 추출
    response = to_response(out_state["request"], out_state["ctx"])

    print("\n[파이프라인 실행 정보]")
    print(f"Trace ID: {response.trace_id}")
    
    if response.citations:
        print("\n[인용된 근거 데이터 (Citations)]")
        for cite in response.citations:
            print(f"- Source ID: {cite.source_id}, Chunk ID: {cite.chunk_id}")
    else:
        print("\n[인용된 근거 데이터] 없음 (환각 방지 또는 검색 실패)")

    if response.diagnostics:
        timings = response.diagnostics.get('timings_ms', {})
        print("\n[단계별 소요 시간 (Latency)]")
        for stage, ms in timings.items():
            print(f"- {stage}: {ms:.2f} ms")

if __name__ == "__main__":
    # Windows 환경 비동기 에러 방지용 설정
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())