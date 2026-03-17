import uuid
from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector

# 기존 프로젝트 구조에 맞춰 Base 임포트 (경로는 환경에 맞게 조정)
# from .env import Base 
from sqlalchemy.orm import declarative_base
Base = declarative_base()

class DocumentChunk(Base):
    """
    범용 RAG 파이프라인을 위한 기본 벡터 테이블 스키마
    """
    __tablename__ = 'document_chunks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False, comment="청크 텍스트 원본")
    # 임베딩 차원 수는 추후 사용할 모델(예: OpenAI 1536, Upstage 4096 등)에 맞게 수정
    embedding = Column(Vector(1536), comment="텍스트 임베딩 벡터") 
    # 도메인이 바뀌어도 스키마 변경 없이 필터링을 테스트할 수 있도록 JSONB 사용
    metadata_ = Column("metadata", JSONB, default={}, comment="도메인 특화 메타데이터 (필터링 용도)")