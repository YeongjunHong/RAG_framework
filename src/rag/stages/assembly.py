# from pydantic import BaseModel

# from src.rag.core.types import RagContext, RagRequest
# from src.rag.core.interfaces import RagStage


# class AssemblyConfig(BaseModel):
#     include_metadata: bool = False


# class AssemblyStage(RagStage[AssemblyConfig]):
#     name = "assembly"

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         # Grouping / formatting for later compression/packing
#         parts = []
#         for i, sc in enumerate(ctx.filtered):
#             header = f"[{i}] source={sc.chunk.source_id} chunk={sc.chunk.chunk_id} score={sc.score:.4f}"
#             body = sc.chunk.content
#             parts.append(header + "\n" + body)

#         ctx.packed_context = "\n\n".join(parts)
#         return ctx

# from pydantic import BaseModel
# from src.rag.core.types import RagContext, RagRequest
# from src.rag.core.interfaces import RagStage

# class AssemblyConfig(BaseModel):
#     include_metadata: bool = False

# class AssemblyStage(RagStage[AssemblyConfig]):
#     name = "assembly"

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         blocks = []
#         # 필터링을 통과한 데이터(kept=True)만 조립
#         for fc in ctx.filtered:
#             if fc.kept:
#                 chunk_id = fc.chunk.chunk_id
#                 content = fc.chunk.content
#                 # Prompt Maker가 하던 포맷팅 역할을 Assembly로 이관
#                 blocks.append(f"문서 식별자: [REF-{chunk_id}]\n내용: {content}")
        
#         # 블록 단위 조작을 위해 특수 구분자로 묶어서 Compression으로 전달
#         ctx.packed_context = "||CHUNK_SPLIT||".join(blocks)
#         return ctx

# from pydantic import BaseModel
# from collections import defaultdict

# from src.rag.core.types import RagRequest, RagContext, EvidenceGroup, ScoredChunk
# from src.rag.core.interfaces import RagStage
# from src.common.logger import get_logger

# logger = get_logger(__name__)

# class AssemblyConfig(BaseModel):
#     # 조립 시 사용할 포맷 (xml, markdown 등)
#     format_type: str = "xml"

# class AssemblyStage(RagStage[AssemblyConfig]):
#     name = "assembly"

#     def __init__(self, config: AssemblyConfig):
#         super().__init__(config)

#     def _group_by_source(self, chunks: list[ScoredChunk]) -> list[EvidenceGroup]:
#         """동일한 출처(source_id)를 가진 청크들을 하나의 그룹으로 묶음"""
#         grouped = defaultdict(list)
        
#         for scored_chunk in chunks:
#             # chunk 내부의 실제 SourceChunk 객체 접근
#             c = scored_chunk.chunk
#             grouped[c.source_id].append(c)

#         evidence_groups = []
#         for source_id, chunk_list in grouped.items():
#             # chunk_id 기준으로 오름차순 정렬하여 문맥 순서 복원
#             chunk_list.sort(key=lambda x: x.chunk_id)
            
#             # 첫 번째 청크의 source_name을 그룹 타이틀로 사용
#             title = chunk_list[0].source_name if chunk_list else f"Source_{source_id}"
            
#             evidence_groups.append(EvidenceGroup(
#                 group_id=str(source_id),
#                 title=title,
#                 chunks=chunk_list
#             ))
            
#         return evidence_groups

#     def _format_to_xml(self, groups: list[EvidenceGroup]) -> str:
#         """LLM이 파싱하기 가장 명확한 XML 태그 형태로 어셈블리"""
#         assembled_text = ""
#         for group in groups:
#             assembled_text += f"<document id='{group.group_id}' title='{group.title}'>\n"
#             for chunk in group.chunks:
#                 assembled_text += f"  <chunk id='{chunk.chunk_id}'>\n"
#                 assembled_text += f"    {chunk.content.strip()}\n"
#                 assembled_text += f"  </chunk>\n"
#             assembled_text += "</document>\n\n"
#         return assembled_text.strip()

#     async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
#         logger.info(f"[{self.name}] 검색된 문서 조립 시작")
        
#         # 1. 파이프라인 분기에 따라 입력 데이터 결정
#         # Reranker를 거쳤으면 reranked 데이터를, 건너뛰었으면 retrieved 데이터를 사용
#         if getattr(ctx, "skip_reranker", False):
#             source_chunks = ctx.retrieved
#         else:
#             # source_chunks = ctx.reranked
#             source_chunks = ctx.retrieved

#         valid_chunks = []
#         for c in source_chunks:
#             # FilteredChunk 객체이고 kept 플래그가 있다면 확인
#             if hasattr(c, 'kept') and not c.kept:
#                 continue
#             valid_chunks.append(c)

#         if not valid_chunks:
#             logger.info(f"[{self.name}] 조립할 청크가 없습니다.")
#             ctx.packed_context = ""
#             return ctx
            
#         # 2. 출처별로 청크들을 그룹화 (이하 동일)
#         evidence_groups = self._group_by_source(valid_chunks)
            
#         if not source_chunks:
#             logger.info(f"[{self.name}] 조립할 청크가 없습니다.")
#             ctx.packed_context = ""
#             return ctx

#         # 2. 출처별로 청크들을 그룹화 (문맥 복원)
#         evidence_groups = self._group_by_source(source_chunks)

#         # 3. LLM 주입용 문자열로 포맷팅
#         if self.config.format_type == "xml":
#             assembled_context = self._format_to_xml(evidence_groups)
#         else:
#             # 마크다운 등 다른 포맷 확장 가능
#             assembled_context = self._format_to_xml(evidence_groups) 

#         # 4. Context에 최종 조립된 텍스트 저장
#         ctx.packed_context = assembled_context
        
#         logger.info(f"[{self.name}] 총 {len(evidence_groups)}개의 문서 그룹으로 조립 완료")
        
#         return ctx


from pydantic import BaseModel
from collections import defaultdict
from typing import List

from src.rag.core.types import RagRequest, RagContext, EvidenceGroup, SourceChunk
from src.rag.core.interfaces import RagStage
from src.common.logger import get_logger

logger = get_logger(__name__)

class AssemblyConfig(BaseModel):
    format_type: str = "xml"

class AssemblyStage(RagStage[AssemblyConfig]):
    name = "assembly"

    def _group_by_source(self, chunks: List[SourceChunk]) -> List[EvidenceGroup]:
        grouped = defaultdict(list)
        for c in chunks:
            grouped[c.source_id].append(c)

        evidence_groups = []
        for source_id, chunk_list in grouped.items():
            chunk_list.sort(key=lambda x: x.chunk_id)
            title = chunk_list[0].source_name if chunk_list else f"Source_{source_id}"
            evidence_groups.append(EvidenceGroup(
                group_id=str(source_id), title=title, chunks=chunk_list
            ))
        return evidence_groups

    def _format_to_xml(self, groups: List[EvidenceGroup]) -> str:
        assembled_text = ""
        for group in groups:
            assembled_text += f"<document id='{group.group_id}' title='{group.title}'>\n"
            for chunk in group.chunks:
                assembled_text += f"  <chunk id='{chunk.chunk_id}'>\n"
                assembled_text += f"    {chunk.content.strip()}\n"
                assembled_text += f"  </chunk>\n"
            assembled_text += "</document>\n\n"
        return assembled_text.strip()

    async def run(self, request: RagRequest, ctx: RagContext) -> RagContext:
        valid_chunks: List[SourceChunk] = []

        # 1. 라우팅 분기에 따른 데이터 소스 선택 및 알맹이(SourceChunk) 추출
        if getattr(ctx, "skip_reranker", False):
            logger.info(f"[{self.name}] Reranker 스킵됨. Retrieved 데이터에서 조립합니다.")
            valid_chunks = [c.chunk for c in ctx.retrieved]
        else:
            logger.info(f"[{self.name}] Reranker 실행됨. Filtered 데이터에서 조립합니다.")
            # kept == True 인 것만 살림
            valid_chunks = [c.chunk for c in ctx.filtered if getattr(c, 'kept', True)]
            
            # [안전망] 만약 Filtering 로직에 버그가 있어 ctx.filtered가 비어버렸다면, 
            # Reranker가 뱉은 ctx.reranked 데이터를 강제로 가져옴
            if not valid_chunks and ctx.reranked:
                logger.warning(f"[{self.name}] ctx.filtered가 비어있어 ctx.reranked를 Fallback으로 사용합니다.")
                valid_chunks = [c.chunk for c in ctx.reranked]

        # 2. 데이터 유무 확인
        if not valid_chunks:
            logger.warning(f"[{self.name}] 조립할 청크가 0건입니다.")
            ctx.packed_context = ""
            return ctx

        # 3. 객체 조립 및 문자열 포맷팅
        evidence_groups = self._group_by_source(valid_chunks)
        ctx.packed_context = self._format_to_xml(evidence_groups)
        
        # 여기서 생성된 evidence_groups를 저장해둬야 다음 단계인 Compression/Packing에서 읽을 수 있음
        ctx.evidence_groups = evidence_groups 
        
        logger.info(f"[{self.name}] 총 {len(evidence_groups)}개 그룹, 텍스트 길이 {len(ctx.packed_context)} 조립 완료")
        return ctx