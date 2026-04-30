"""create_rag_execution_log_table

Revision ID: 543e4661f6f7
Revises: 543e4661f6f7
Create Date: 2026-04-29 08:56:47.186216

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '543e4661f6f7'
down_revision: Union[str, Sequence[str], None] = '9a9df6b2d530'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('rag_execution_log',
        sa.Column('trace_id', sa.String(length=100), nullable=False, comment='Request 고유 ID'),
        sa.Column('user_query', sa.Text(), nullable=False),
        sa.Column('intent', sa.String(length=20), nullable=False),
        sa.Column('raw_generation', sa.Text(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=True, comment='Guardrails 통과 여부'),
        sa.Column('error_type', sa.String(length=50), nullable=True),
        sa.Column('error_reason', sa.Text(), nullable=True),
        sa.Column('diagnostics', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='소요 시간, 토큰 사용량 등'),
        sa.Column('is_security_alert', sa.Boolean(), server_default='false', nullable=False, comment='보안 위반 여부'),
        sa.Column('hit_patterns', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='감지된 공격 패턴 (JSON Array)'),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        comment='rag_execution_log table'
    )
    op.create_index(op.f('ix_rag_execution_log_trace_id'), 'rag_execution_log', ['trace_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_rag_execution_log_trace_id'), table_name='rag_execution_log')
    op.drop_table('rag_execution_log')