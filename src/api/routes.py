import asyncio
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.rag.graph import build_graph
from src.rag.core.types import RagRequest, RagContext
from src.common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# 애플리케이션 시작 시 한 번만 RAG 엔진(그래프)을 빌드 (Singleton)
rag_app = build_graph()

class ChatRequest(BaseModel):
    query: str
    session_id: str = "default_session"

async def generate_chat_stream(request: ChatRequest):
    """LangGraph의 큐를 소비하여 HTTP SSE 스트림으로 변환하는 제너레이터"""
    
    req = RagRequest(trace_id=request.session_id, user_query=request.query, stream_response=True)
    ctx = RagContext()
    
    # 프론트로 토큰을 밀어낼 비동기 파이프 생성
    ctx.stream_queue = asyncio.Queue()

    # RAG 파이프라인을 백그라운드 태스크로 분리하여 비동기 실행
    async def run_pipeline():
        try:
            await rag_app.ainvoke({"request": req, "ctx": ctx})
        except Exception as e:
            logger.error(f"파이프라인 실행 중 치명적 오류: {e}")
            await ctx.stream_queue.put(f"\n[시스템 오류] 답변 생성 중 문제가 발생했습니다.")
        finally:
            # 파이프라인이 정상/비정상 종료되든 무조건 큐에 종료 시그널 전송
            await ctx.stream_queue.put(None)

    pipeline_task = asyncio.create_task(run_pipeline())

    try:
        while True:
            # generator.py에서 put한 토큰을 여기서 get
            token = await ctx.stream_queue.get()
            
            if token is None: # 파이프라인 종료 신호 감지
                break
                
            # SSE(Server-Sent Events) 규격에 맞게 포매팅하여 전송
            data_payload = json.dumps({"token": token}, ensure_ascii=False)
            yield f"data: {data_payload}\n\n"
            
    except asyncio.CancelledError:
        # 클라이언트가 중간에 브라우저 창을 닫아 연결을 끊었을 때 방어
        logger.info(f"[API] 클라이언트 연결 해제. 파이프라인 태스크 취소.")
        pipeline_task.cancel()
        raise

@router.post("/v1/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문 내용이 비어있습니다.")
        
    return StreamingResponse(
        generate_chat_stream(request), 
        media_type="text/event-stream"
    )