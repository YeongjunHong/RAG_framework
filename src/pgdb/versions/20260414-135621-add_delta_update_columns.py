"""add_delta_update_columns

Revision ID: 9a9df6b2d530
Revises: f1d6a878f625
Create Date: 2026-04-14 13:56:21.509490

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '<생성된_새로운_해시값>'
down_revision: Union[str, Sequence[str], None] = 'f1d6a878f625'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. source_knowledge 테이블에 content_hash와 is_active 추가
    op.add_column('source_knowledge', sa.Column('content_hash', sa.String(length=64), nullable=True))
    op.add_column('source_knowledge', sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    
    # 해시값을 이용한 빠른 조회를 위해 인덱스 추가
    op.create_index('ix_source_knowledge_content_hash', 'source_knowledge', ['content_hash'], unique=False)

    # 2. source_chunk 테이블에 is_active 추가
    op.add_column('source_chunk', sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    
    # 벡터 검색 시 활성화된 청크만 필터링하기 위한 인덱스 추가
    op.create_index('ix_source_chunk_is_active', 'source_chunk', ['is_active'], unique=False)


def downgrade() -> None:
    # 롤백 로직 (upgrade의 역순)
    op.drop_index('ix_source_chunk_is_active', table_name='source_chunk')
    op.drop_column('source_chunk', 'is_active')
    
    op.drop_index('ix_source_knowledge_content_hash', table_name='source_knowledge')
    op.drop_column('source_knowledge', 'is_active')
    op.drop_column('source_knowledge', 'content_hash')
