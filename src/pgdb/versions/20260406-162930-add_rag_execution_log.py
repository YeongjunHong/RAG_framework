"""add_rag_execution_log

Revision ID: a8062502ddae
Revises: a817730a5f8d
Create Date: 2026-04-06 16:29:30.451394

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'a8062502ddae'
down_revision: Union[str, Sequence[str], None] = 'a817730a5f8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 쓸데없는 alter_column 제거 후, 순수하게 새 테이블 생성 로직만 남김
    op.create_table('rag_execution_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('trace_id', sa.String(length=100), nullable=False, comment='Request 고유 ID'),
        sa.Column('user_query', sa.Text(), nullable=False),
        sa.Column('intent', sa.String(length=20), nullable=False),
        sa.Column('raw_generation', sa.Text(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=True, comment='Guardrails 통과 여부'),
        sa.Column('error_type', sa.String(length=50), nullable=True),
        sa.Column('error_reason', sa.Text(), nullable=True),
        sa.Column('diagnostics', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='소요 시간, 토큰 사용량 등'),
        sa.PrimaryKeyConstraint('id'),
        comment='rag_execution_log table'
    )
    op.create_index(op.f('ix_rag_execution_log_trace_id'), 'rag_execution_log', ['trace_id'], unique=True)


def downgrade() -> None:
    # 롤백 시 해당 테이블과 인덱스만 제거
    op.drop_index(op.f('ix_rag_execution_log_trace_id'), table_name='rag_execution_log')
    op.drop_table('rag_execution_log')