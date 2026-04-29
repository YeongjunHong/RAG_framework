import asyncio
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from faststream.rabbit import RabbitBroker

from src.rag.graph import build_graph
from src.rag.core.types import RagRequest, RagContext
from src.common.logger import get_logger

# [신규 추가] 중앙 설정 객체 임포트
from settings.config import cfg

logger = get_logger(__name__)
router = APIRouter()

# 1. 싱글톤 객체 초기화
# RAG 엔진 빌드
rag_app = build_graph()

# RabbitMQ 브로커 (도커 컴포즈 서비스명인 'rabbitmq' 사용)
# 실무에서는 환경 변수 처리하는 것이 좋음
broker = RabbitBroker(cfg.RABBITMQ_URL)
# --- Pydantic Models ---

class ChatRequest(BaseModel):
    query: str
    session_id: str = "default_session"

class IngestionRequest(BaseModel):
    """데이터 적재 요청을 위한 스키마"""
    domain: str
    source_path: str = "default_path"
    description: str | None = None

# --- Helpers ---

async def generate_chat_stream(request: ChatRequest):
    """LangGraph의 큐를 소비하여 HTTP SSE 스트림으로 변환하는 제너레이터"""
    req = RagRequest(trace_id=request.session_id, user_query=request.query, stream_response=True)
    ctx = RagContext()
    ctx.stream_queue = asyncio.Queue()

    async def run_pipeline():
        try:
            await rag_app.ainvoke({"request": req, "ctx": ctx})
        except Exception as e:
            logger.error(f"파이프라인 실행 중 치명적 오류: {e}")
            await ctx.stream_queue.put(f"\n[시스템 오류] 답변 생성 중 문제가 발생했습니다.")
        finally:
            await ctx.stream_queue.put(None)

    pipeline_task = asyncio.create_task(run_pipeline())

    try:
        while True:
            token = await ctx.stream_queue.get()
            if token is None:
                break
            data_payload = json.dumps({"token": token}, ensure_ascii=False)
            yield f"data: {data_payload}\n\n"
    except asyncio.CancelledError:
        logger.info(f"[API] 클라이언트 연결 해제. 파이프라인 태스크 취소.")
        pipeline_task.cancel()
        raise

# --- Endpoints ---

@router.post("/v1/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """실시간 RAG 대화 엔드포인트 (Streaming)"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문 내용이 비어있습니다.")
    return StreamingResponse(
        generate_chat_stream(request), 
        media_type="text/event-stream"
    )

@router.post("/v1/knowledge/ingest", status_code=202)
async def trigger_ingestion_endpoint(request: IngestionRequest):
    """
    무거운 데이터 적재 작업을 RabbitMQ 큐에 등록합니다.
    임베딩 연산을 직접 수행하지 않고 워커에게 위임한 뒤 즉시 응답합니다.
    """
    try:
        # 브로커 연결 (이미 연결되어 있다면 무시됨)
        await broker.connect()
        
        # 워커가 구독 중인 'rag_ingestion_queue'로 작업 지시서 발송
        await broker.publish(
            message={
                "source_path": request.source_path,
                "domain": request.domain,
                "triggered_by": "api_user"
            },
            queue="rag_ingestion_queue"
        )
        
        logger.info(f"[API] Ingestion 작업 큐 등록 완료: {request.domain}")
        return {
            "status": "accepted",
            "message": f"[{request.domain}] 적재 작업이 시작되었습니다. 완료 후 DB에서 확인 가능합니다."
        }
        
    except Exception as e:
        logger.error(f"메시지 큐 발행 실패: {e}")
        raise HTTPException(status_code=500, detail="메시지 브로커 통신 에러")