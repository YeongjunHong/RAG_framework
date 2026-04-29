import asyncio
from faststream import FastStream
from faststream.rabbit import RabbitBroker
from pydantic import BaseModel

from src.common.logger import get_logger
# 기존 인제스천 파이프라인 함수 임포트
from src.rag.bulk_source.source_chunk_ingestion import run_ingestion_pipeline

# [신규 추가] 중앙 설정 객체 임포트
from settings.config import cfg

logger = get_logger(__name__)

# 도커 컴포즈 환경에 맞춘 RabbitMQ 브로커 설정
broker = RabbitBroker(cfg.RABBITMQ_URL)
app = FastStream(broker)

class IngestionTask(BaseModel):
    domain: str
    source_path: str = "default_path"
    triggered_by: str = "api_user"

@broker.subscriber("rag_ingestion_queue")
async def process_ingestion(task: IngestionTask):
    logger.info(f"[Worker] 데이터 적재 작업 수신: 도메인 '{task.domain}' (요청자: {task.triggered_by})")
    
    try:
        # [핵심] 동기(Sync) 기반의 무거운 CPU/I/O 연산을 메인 이벤트 루프에서 분리
        # 이렇게 해야 RabbitMQ와의 Heartbeat 통신이 끊기지 않음
        await asyncio.to_thread(
            run_ingestion_pipeline, 
            target_domain=task.domain
        )
        
        logger.info(f"[Worker] 데이터 적재 완료: {task.domain}")
        
    except Exception as e:
        logger.error(f"[Worker] 적재 중 치명적 오류 발생: {e}")
        # 예외를 raise하면 FastStream이 자동으로 Nack 처리하여 메시지 유실을 방지함
        raise e