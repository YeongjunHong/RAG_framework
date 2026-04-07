import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert # DB 중복 방지 - Upsert
from src.pgdb.schema import RagExecutionLog
from pydantic import BaseModel
from src.rag.core.types import RagRequest, RagContext, SecurityStatus, InputGuardResponse
from src.rag.core.interfaces import RagStage, Tracer
from src.rag.services.registry import InputGuardRegistry
from src.common.logger import get_logger

logger = get_logger(__name__)

class InputGuardStage(RagStage):
    name = "input_guard"

    def __init__(self, registry: InputGuardRegistry, tracer: Tracer, db_session_maker):
        # RagStage의 부모 생성자 호출 (config가 따로 없으므로 None 전달 가능)
        super().__init__(config=None)
        self.registry = registry
        self.tracer = tracer
        self.db_session_maker = db_session_maker

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        with self.tracer.span("input_guard"):
            guard_plugin = self.registry.get("default")
            guard_result = await guard_plugin.forward(request.user_query)
            ctx.input_guard = guard_result
            
            if not guard_result.is_safe:
                logger.warning(f"[InputGuard] 보안 정책 위반 감지 (TraceID: {request.trace_id})")
                
                # 비동기 DB 로깅 실행
                await self._log_security_violation(request, guard_result)
                
                ctx.intent = "security_violation"
                ctx.skip_retrieval = True
                ctx.skip_reranker = True
                
        return ctx

    async def _log_security_violation(self, request: RagRequest, result: InputGuardResponse):
        """보안 위반 내역을 DB에 저장 (중복 호출 시 무시)"""
        try:
            async with self.db_session_maker() as session:
                # SQLAlchemy PostgreSQL 방언을 사용한 Upsert 로직
                stmt = pg_insert(RagExecutionLog).values(
                    trace_id=request.trace_id,
                    user_query=request.user_query,
                    intent="security_violation",
                    is_security_alert=True,
                    hit_patterns=result.hit_patterns
                )
                
                # trace_id가 이미 존재하면(예: astream과 ainvoke 중복 실행) 무시
                stmt = stmt.on_conflict_do_nothing(index_elements=['trace_id'])
                
                await session.execute(stmt)
                await session.commit()
                
        except Exception as e:
            # DB 에러가 발생해도 파이프라인이 멈추지 않도록 처리
            logger.error(f"Failed to insert security log into DB: {e}")