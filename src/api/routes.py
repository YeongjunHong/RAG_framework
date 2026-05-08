# import asyncio
# import json
# from fastapi import APIRouter, HTTPException, Request
# from fastapi.responses import StreamingResponse
# from pydantic import BaseModel
# from faststream.rabbit import RabbitBroker

# from src.rag.graph import build_graph
# from src.rag.core.types import RagRequest, RagContext
# from src.common.logger import get_logger

# # [신규 추가] 중앙 설정 객체 임포트
# from settings.config import cfg

# logger = get_logger(__name__)
# router = APIRouter()

# # 1. 싱글톤 객체 초기화
# # RAG 엔진 빌드
# rag_app = build_graph()

# # RabbitMQ 브로커 (도커 컴포즈 서비스명인 'rabbitmq' 사용)

# broker = RabbitBroker(cfg.RABBITMQ_URL)
# # --- Pydantic Models ---

# class ChatRequest(BaseModel):
#     query: str
#     session_id: str = "default_session"

# class IngestionRequest(BaseModel):
#     """데이터 적재 요청을 위한 스키마"""
#     domain: str
#     source_path: str = "default_path"
#     description: str | None = None

# # --- Helpers ---

# async def generate_chat_stream(request: ChatRequest):
#     """LangGraph의 큐를 소비하여 HTTP SSE 스트림으로 변환하는 제너레이터"""
#     req = RagRequest(trace_id=request.session_id, user_query=request.query, stream_response=True)
#     ctx = RagContext()
#     ctx.stream_queue = asyncio.Queue()

#     async def run_pipeline():
#         try:
#             await rag_app.ainvoke({"request": req, "ctx": ctx})
#         except Exception as e:
#             logger.error(f"파이프라인 실행 중 치명적 오류: {e}")
#             await ctx.stream_queue.put(f"\n[시스템 오류] 답변 생성 중 문제가 발생했습니다.")
#         finally:
#             await ctx.stream_queue.put(None)

#     pipeline_task = asyncio.create_task(run_pipeline())

#     try:
#         while True:
#             token = await ctx.stream_queue.get()
#             if token is None:
#                 break
#             data_payload = json.dumps({"token": token}, ensure_ascii=False)
#             yield f"data: {data_payload}\n\n"
#     except asyncio.CancelledError:
#         logger.info(f"[API] 클라이언트 연결 해제. 파이프라인 태스크 취소.")
#         pipeline_task.cancel()
#         raise

# # --- Endpoints ---

# @router.post("/v1/chat/stream")
# async def chat_stream_endpoint(request: ChatRequest):
#     """실시간 RAG 대화 엔드포인트 (Streaming)"""
#     if not request.query.strip():
#         raise HTTPException(status_code=400, detail="질문 내용이 비어있습니다.")
#     return StreamingResponse(
#         generate_chat_stream(request), 
#         media_type="text/event-stream"
#     )

# @router.post("/v1/knowledge/ingest", status_code=202)
# async def trigger_ingestion_endpoint(request: IngestionRequest):
#     """
#     무거운 데이터 적재 작업을 RabbitMQ 큐에 등록합니다.
#     임베딩 연산을 직접 수행하지 않고 워커에게 위임한 뒤 즉시 응답합니다.
#     """
#     try:
#         # 브로커 연결 (이미 연결되어 있다면 무시됨)
#         await broker.connect()
        
#         # 워커가 구독 중인 'rag_ingestion_queue'로 작업 지시서 발송
#         await broker.publish(
#             message={
#                 "source_path": request.source_path,
#                 "domain": request.domain,
#                 "triggered_by": "api_user"
#             },
#             queue="rag_ingestion_queue"
#         )
        
#         logger.info(f"[API] Ingestion 작업 큐 등록 완료: {request.domain}")
#         return {
#             "status": "accepted",
#             "message": f"[{request.domain}] 적재 작업이 시작되었습니다. 완료 후 DB에서 확인 가능합니다."
#         }
        
#     except Exception as e:
#         logger.error(f"메시지 큐 발행 실패: {e}")
#         raise HTTPException(status_code=500, detail="메시지 브로커 통신 에러")


import re
import time
import json
import asyncio
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from faststream.rabbit import RabbitBroker

# RAG 코어 및 타입 임포트
from src.rag.graph import build_graph
from src.rag.core.types import RagRequest, RagContext
from src.common.logger import get_logger

# 플러그인 임포트
from src.rag.plugins.openrouter_generator import OpenRouterGenerator

# 중앙 설정 객체 임포트
from settings.config import cfg

logger = get_logger(__name__)
router = APIRouter()

# --- 1. 싱글톤 객체 초기화 ---
# RAG 엔진 빌드
rag_app = build_graph()

# RabbitMQ 브로커 (도커 컴포즈 서비스명인 'rabbitmq' 사용)
broker = RabbitBroker(cfg.RABBITMQ_URL)


# --- 2. Pydantic Models ---

# (1) 기본 챗봇 및 적재용 모델
class ChatRequest(BaseModel):
    query: str
    session_id: str = "default_session"

class IngestionRequest(BaseModel):
    """데이터 적재 요청을 위한 스키마"""
    domain: str
    source_path: str = "default_path"
    description: str | None = None

# (2) A/B 테스트 데모용 모델
class ABTestRequest(BaseModel):
    query: str

class TestMetrics(BaseModel):
    answer: str
    latency_ms: float
    groundedness_score: int = 0
    has_hallucination: bool = False
    retrieved_sources: List[Dict[str, str]] = []

class ABTestResponse(BaseModel):
    query: str
    with_rag: TestMetrics
    without_rag: TestMetrics


# --- 3. Helpers ---

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


# --- A/B 테스트용 비동기 헬퍼 함수 ---

async def run_vanilla_llm(query: str) -> tuple[str, float]:
    """RAG 파이프라인 없이 순수 LLM만 호출 (Without RAG)"""
    gen = OpenRouterGenerator()
    t0 = time.perf_counter()
    answer = await gen.forward(prompt=query)
    t1 = time.perf_counter()
    return answer, (t1 - t0) * 1000

async def run_rag_pipeline(query: str) -> tuple[str, float, List[Dict[str, str]], str]:
    """전체 LangGraph RAG 파이프라인 호출 (With RAG)"""
    req = RagRequest(trace_id="ab_test_demo", user_query=query, stream_response=False)
    ctx = RagContext()
    
    t0 = time.perf_counter()
    state = await rag_app.ainvoke({"request": req, "ctx": ctx})
    t1 = time.perf_counter()
    
    out_ctx = state["ctx"]
    answer = out_ctx.raw_generation or "생성된 답변이 없습니다."
    
    # 프론트엔드 노출용 소스 정리 (상위 3개 제한)
    sources = [
        {"doc_id": str(c.chunk.source_name), "snippet": c.chunk.content[:150] + "..."}
        for c in out_ctx.retrieved[:3]
    ]
    
    # Judge 평가용 컨텍스트 병합 (전체)
    full_context = "\n".join([f"[{c.chunk.source_name}] {c.chunk.content}" for c in out_ctx.retrieved])
    
    return answer, (t1 - t0) * 1000, sources, full_context

async def evaluate_with_judge(query: str, answer: str, context: str) -> Dict[str, Any]:
    """LLM Judge를 활용한 정량적 평가 (Groundedness & Hallucination)"""
    if not context.strip():
        # 검색된 컨텍스트가 없으면 판단 불가 처리
        return {"groundedness_score": 0, "has_hallucination": True}

    # Judge는 빠르고 JSON 포맷팅에 강한 모델 사용
    judge_gen = OpenRouterGenerator(default_model="openai/gpt-4o-mini") 
    
    prompt = f"""당신은 RAG 시스템의 신뢰성을 검증하는 엄격한 평가자입니다.
아래의 [Context]에 기반하여 [Answer]를 평가하고, 반드시 아래 JSON 포맷으로만 응답하세요.
Markdown 코드 블록(```json)을 사용하지 말고 순수 JSON 텍스트만 출력하세요.

[Query]: {query}

[Context]:
{context}

[Answer]:
{answer}

평가 기준:
1. groundedness_score (0~100): 답변의 내용이 Context에 얼마나 사실적으로 부합하는가?
2. has_hallucination (true/false): Context에 없는 수치, 고유명사, 규정을 지어내어 답변했는가?

Output JSON format:
{{"groundedness_score": 85, "has_hallucination": false}}
"""
    try:
        judge_result = await judge_gen.forward(prompt=prompt)
        # JSON 추출 (마크다운 포맷팅 방어)
        json_match = re.search(r'\{.*\}', judge_result, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return {"groundedness_score": 0, "has_hallucination": True}
    except Exception as e:
        logger.error(f"[LLM Judge] 평가 중 오류 발생: {e}")
        return {"groundedness_score": 0, "has_hallucination": True}


# --- 4. Endpoints ---

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

@router.post("/v1/demo/ab-test", response_model=ABTestResponse)
async def ab_test_endpoint(request: ABTestRequest):
    """프론트엔드 대시보드용 RAG vs No-RAG A/B 테스트 병렬 실행 API"""
    query = request.query
    if not query.strip():
        raise HTTPException(status_code=400, detail="쿼리가 비어 있습니다.")

    # 1. Vanilla LLM과 RAG 파이프라인 동시 실행 (I/O 병목 최소화)
    vanilla_task = asyncio.create_task(run_vanilla_llm(query))
    rag_task = asyncio.create_task(run_rag_pipeline(query))
    
    (vanilla_ans, vanilla_lat), (rag_ans, rag_lat, rag_sources, rag_context) = await asyncio.gather(vanilla_task, rag_task)

    # 2. RAG에서 찾은 Ground Truth Context를 기준으로 두 답변을 동시 평가
    eval_vanilla_task = asyncio.create_task(evaluate_with_judge(query, vanilla_ans, rag_context))
    eval_rag_task = asyncio.create_task(evaluate_with_judge(query, rag_ans, rag_context))
    
    vanilla_eval, rag_eval = await asyncio.gather(eval_vanilla_task, eval_rag_task)

    # 3. 최종 결과 조합 반환
    return ABTestResponse(
        query=query,
        without_rag=TestMetrics(
            answer=vanilla_ans,
            latency_ms=round(vanilla_lat, 2),
            groundedness_score=vanilla_eval.get("groundedness_score", 0),
            has_hallucination=vanilla_eval.get("has_hallucination", True),
            retrieved_sources=[] # Vanilla는 소스가 없음
        ),
        with_rag=TestMetrics(
            answer=rag_ans,
            latency_ms=round(rag_lat, 2),
            groundedness_score=rag_eval.get("groundedness_score", 0),
            has_hallucination=rag_eval.get("has_hallucination", False),
            retrieved_sources=rag_sources
        )
    )