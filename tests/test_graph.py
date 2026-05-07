

import sys
import os
import asyncio
import uuid
from pathlib import Path
from dotenv import load_dotenv

current_file_path = Path(__file__).resolve()
project_root = current_file_path.parent
sys.path.append(str(project_root))

env_path = project_root / "settings" / ".env.poc"
load_dotenv(dotenv_path=env_path)

from src.rag.graph import build_graph
from src.rag.core.types import RagRequest, RagContext
from src.rag.stages.post_check import to_response

async def main():
    print("RAG 파이프라인 그래프 빌드 중...")
    app = build_graph()
    
    # 테스트 질문 변경: DB 검색이 필요 없는 단순 잡담(chitchat)으로 변경
    test_query = "안녕? 넌 누구야? 어떤 일을 할 수 있어?"
    # test_query = "청년도약계좌나 청년주택드림청약통장 같은 청년 지원 금융 상품의 가입 조건이나 납입 관련 혜택이 어떻게 되나요?"
    print(f"\n[사용자 질문]: {test_query}\n")
    
    request = RagRequest(
        trace_id=str(uuid.uuid4()),
        user_query=test_query,
        safety_level="medium"
    )

    token_queue = asyncio.Queue()
    ctx = RagContext(stream_queue=token_queue)
    state = {"request": request, "ctx": ctx}

    print("파이프라인 실행 중 ...\n")
    print("=" * 60)
    print("[최종 AI 답변] (스트리밍 중...)")
    
    graph_task = asyncio.create_task(app.ainvoke(state))

    while True:
        token = await token_queue.get()
        if token is None:
            break
        print(token, end="", flush=True)
    
    print("\n" + "=" * 60)

    out_state = await graph_task
    response = to_response(out_state["request"], out_state["ctx"])

    print("\n[파이프라인 실행 정보]")
    print(f"Trace ID: {response.trace_id}")
    
    # 플래너가 어떻게 판단했는지 출력
    print(f"\n[플래너 분석 결과 (ctx.plan)]")
    print(out_state["ctx"].plan)
    
    if response.diagnostics:
        timings = response.diagnostics.get('timings_ms', {})
        print("\n[단계별 소요 시간 (Latency)]")
        for stage, ms in timings.items():
            print(f"- {stage}: {ms:.2f} ms")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())