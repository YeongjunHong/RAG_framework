from pydantic import BaseModel
from src.rag.core.types import RagRequest, RagContext
from src.rag.core.interfaces import RagStage, Tracer
from src.rag.services.registry import PlannerRegistry
from src.common.logger import get_logger

logger = get_logger(__name__)

class PlannerConfig(BaseModel):
    provider: str = "default"

class PlannerStage(RagStage[PlannerConfig]):
    name = "planner"

    def __init__(self, config: PlannerConfig, registry: PlannerRegistry, tracer: Tracer):
        super().__init__(config)
        self.registry = registry
        self.tracer = tracer

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        # 1. 레지스트리에서 설정된 플래너(sLM 등) 객체 획득
        planner_plugin = self.registry.get(self.config.provider)
        
        # 2. 트레이싱 스팬을 열고 플래너 실행
        with self.tracer.span("planner", provider=self.config.provider):
            plan_result = await planner_plugin.forward(request.user_query)
            
            # 3. 분석 결과를 파이프라인 컨텍스트에 저장
            ctx.plan = plan_result
            ctx.plan_id = plan_result.get("intent", "search")
            
            logger.info(f"[PlannerStage] 의도 분석 완료: {ctx.plan_id}")

        return ctx