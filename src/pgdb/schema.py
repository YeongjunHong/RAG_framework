from datetime import datetime
import enum
from typing import Any, Optional
from sqlalchemy import Float, BigInteger, Integer, SmallInteger, Text, String, DateTime, Enum, ForeignKey, UniqueConstraint, Index, Computed, and_, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship, foreign
from pgvector.sqlalchemy import Vector


def set_unique_constraint(table_name: str, columns: list[str]|None=None):
    if not columns:
        raise ValueError("columns must not be empty")
    name = f"uq_{table_name}_{'_'.join(columns)}"
    return UniqueConstraint(*columns, name=name)


class Base(DeclarativeBase):
    pass


class TableBase(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @declared_attr.directive
    def __table_args__(cls):
        return {
            "comment": f"{cls.__tablename__} table"
        }


class SourceChunk(TableBase):
    __tablename__ = "source_chunk"

    content: Mapped[str] = mapped_column(Text, comment="chunk text")
    content_hash: Mapped[str] = mapped_column(String(64), Computed("encode(digest(coalesce(content,''), 'sha256'), 'hex')", persisted=True), comment="auto-generated sha256")
    chunk_tsv: Mapped[Any] = mapped_column(TSVECTOR, Computed("to_tsvector('simple', coalesce(content,''))", persisted=True), comment="auto-generated tsvector")
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_version: Mapped[str] = mapped_column(String(20))

    __table_args__ = (
        set_unique_constraint(__tablename__, ["content_hash", "chunk_index", "chunk_version"]),
        Index("ix_source_chunk_chunk_tsv_gin", "chunk_tsv", postgresql_using="gin"),
    )


class SourceChunkVec(TableBase):
    __tablename__ = "source_chunk_vec"

    chunk_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("source_chunk.id", ondelete="CASCADE"))
    # chunk_vec: Mapped[Any] = mapped_column(Vector(1536))
    chunk_vec: Mapped[Any] = mapped_column(Vector(768))
    vec_model_name: Mapped[str] = mapped_column(String(50))

    __table_args__ = (
        set_unique_constraint(__tablename__, ["chunk_id", "vec_model_name"]),
        Index("ix_source_chunk_vec_chunk_id", "chunk_id"),
        Index("ix_source_chunk_vec_chunk_vec_hnsw", "chunk_vec", postgresql_using="hnsw", postgresql_ops={"chunk_vec": "vector_cosine_ops"}),
    )


class SourceName(str, enum.Enum):
    prompt_template = "prompt_template"
    interface = "interface"
    fewshot_example = "fewshot_example"
    knowledge = "knowledge"


class MapSourceChunk(TableBase):
    __tablename__ = "map_source_chunk"

    chunk_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("source_chunk.id", ondelete="CASCADE"))
    source_id: Mapped[int] = mapped_column(BigInteger)
    source_name: Mapped[SourceName] = mapped_column(Enum(SourceName, name="source_name_enum", native_enum=True))

    __table_args__ = (
        set_unique_constraint(__tablename__, ["chunk_id", "source_id", "source_name"]),
        Index("ix_map_source_chunk_chunk_id", "chunk_id"),
        Index("ix_map_source_chunk_source_id_source_name", "source_id", "source_name"),
    )


class SourceTableBase(TableBase):
    __abstract__ = True

    content: Mapped[str] = mapped_column(Text, comment="source text")
    process: Mapped[str] = mapped_column(String(20), comment="processing step")

    # opt
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


class SourcePromptTemplate(SourceTableBase):
    __tablename__ = "source_prompt_template"

    model_name: Mapped[str] = mapped_column(String(50))
    template_name: Mapped[str] = mapped_column(String(20))

    # opt
    model_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    model_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Billion")
    model_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    template_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


class SourceInterface(SourceTableBase):
    __tablename__ = "source_interface"

    api_name: Mapped[str] = mapped_column(String(50))
    api_endpoint: Mapped[str] = mapped_column(Text)
    
    # opt
    auth_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


class SourceFewshotExample(SourceTableBase):
    __tablename__ = "source_fewshot_example"

    grade: Mapped[int] = mapped_column(SmallInteger)
    subject: Mapped[str] = mapped_column(String(20))
    example_type: Mapped[str] = mapped_column(String(20))

    # opt
    difficulty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    irt_a: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="IRT(discrimination)")
    irt_b: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="IRT(difficulty)")
    irt_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="IRT(guessing)")


class SourceKnowledge(SourceTableBase):
    __tablename__ = "source_knowledge"

    subject: Mapped[str] = mapped_column(String(20))

    # opt
    category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

# 공격 패턴을 db에 저장하고 
class RagExecutionLog(TableBase):
    __tablename__ = "rag_execution_log"

    trace_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, comment="Request 고유 ID")
    user_query: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(20))
    raw_generation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_valid: Mapped[Optional[bool]] = mapped_column(nullable=True, comment="Guardrails 통과 여부")
    error_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diagnostics: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, comment="소요 시간, 토큰 사용량 등")

    # 신규: 보안 위반 기록용 컬럼
    is_security_alert: Mapped[bool] = mapped_column(default=False, server_default="false", comment="보안 위반 여부")
    hit_patterns: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, comment="감지된 공격 패턴 (JSON Array)")