import html
from pydantic import BaseModel
from typing import List

from src.rag.core.types import RagRequest, RagContext, EvidenceGroup
from src.rag.core.interfaces import RagStage, Tracer
from src.common.logger import get_logger

logger = get_logger(__name__)

class PackingConfig(BaseModel):
    # 기본 포맷은 xml. 향후 markdown, json 등으로 확장 가능
    format_type: str = "xml"
    # 패킹 후 메모리 확보를 위해 중간 객체를 삭제할지 여부
    clear_intermediate_data: bool = True 

class PackingStage(RagStage[PackingConfig]):
    name = "packing"

    def __init__(self, config: PackingConfig, tracer: Tracer):
        super().__init__(config)
        self.tracer = tracer

    def _format_to_xml(self, groups: List[EvidenceGroup]) -> str:
        """압축된 EvidenceGroup 리스트를 XML 문자열로 직렬화"""
        if not groups:
            return ""
            
        assembled_text = "<context>\n"
        for group in groups:
            # title에 들어갈 수 있는 특수문자 이스케이프 처리
            safe_title = html.escape(group.title or f"Source_{group.group_id}")
            assembled_text += f"  <document id='{group.group_id}' title='{safe_title}'>\n"
            
            for chunk in group.chunks:
                # 수학 수식에 포함된 <, > 기호가 XML 태그로 오인되는 것을 방지
                safe_content = html.escape(chunk.content.strip())
                assembled_text += f"    <chunk id='{chunk.chunk_id}'>\n"
                assembled_text += f"      {safe_content}\n"
                assembled_text += f"    </chunk>\n"
                
            assembled_text += "  </document>\n"
        assembled_text += "</context>"
        
        return assembled_text

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        with self.tracer.span("packing", format=self.config.format_type):
            groups = getattr(ctx, "evidence_groups", [])
            
            if not groups:
                logger.info(f"[{self.name}] 패킹할 문서 그룹이 없습니다.")
                ctx.packed_context = ""
                return ctx

            # 지정된 포맷으로 문자열 변환
            if self.config.format_type == "xml":
                packed_text = self._format_to_xml(groups)
            else:
                # 확장성을 위해 열어둠. 현재는 모두 XML로 처리
                packed_text = self._format_to_xml(groups)
                
            ctx.packed_context = packed_text
            
            # 최적화: 대용량 텍스트 객체들이 메모리(RAM)를 점유하는 것을 방지
            # 어차피 문자열로 직렬화되었으므로, 더 이상 필요 없는 파이썬 객체 참조를 끊어 GC(Garbage Collector)가 회수하도록 유도
            if self.config.clear_intermediate_data:
                ctx.evidence_groups = []
                # 필요하다면 ctx.retrieved, ctx.reranked 등도 여기서 비워버릴 수 있음

            logger.info(f"[{self.name}] 패킹 완료. (최종 문자열 길이: {len(packed_text)} characters)")

        return ctx