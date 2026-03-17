import asyncio
import uuid
from dotenv import load_dotenv

# 환경변수 로드 (.env.poc 파일을 읽어옵니다)
load_dotenv(".env.poc")

from src.rag.graph import build_graph, run_graph
from src.rag.core.types import RagRequest

async def main():
    print("RAG 파이프라인 그래프 빌드 중...")
    app = build_graph()
    
    # 테스트할 사용자 질문 
    test_query = "청년도약계좌나 청년주택드림청약통장 같은 청년 지원 금융 상품의 가입 조건이나 납입 관련 혜택이 어떻게 되나요?"
    print(f"\n 사용자 질문: {test_query}\n")
    
    request = RagRequest(
        user_query=test_query,
        user_id="test_user_01",
        session_id="session_999",
        trace_id = str(uuid.uuid4()),
        safety_level="medium" 
    )

    print(" 파이프라인 실행 중 (Query Expansion -> Retrieval -> Prompt -> Generator)...\n")
    
    # 파이프라인 실행!
    response = await run_graph(app, request)

    print("=" * 60)
    print(" [최종 AI 답변] ")
    print(response.answer)
    print("=" * 60)

    print("\n [파이프라인 실행 정보]")
    print(response)
    
    #  에러 수정 구간: RagResponse의 실제 구조에 맞춰 출력
    print("\n [파이프라인 실행 정보]")
    print(f"Trace ID: {response.trace_id}")
    
    # 만약 사수분의 프레임워크에서 인용구(Citations) 기능을 지원한다면:
    if hasattr(response, 'citations') and response.citations:
        print("\n [인용된 근거 데이터]")
        for cite in response.citations:
            print(f"- {cite}")

    # 디버깅을 위해 diagnostics(시간 측정 등) 출력
    if hasattr(response, 'diagnostics'):
        print(f"\n 소요 시간: {response.diagnostics.get('timings_ms', {}).get('generator_llm', 0):.2f} ms (LLM 생성)")

if __name__ == "__main__":
    asyncio.run(main())