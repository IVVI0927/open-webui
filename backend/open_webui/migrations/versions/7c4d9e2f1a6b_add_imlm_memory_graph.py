"""Add IMLM memory graph schema.

Revision ID: 7c4d9e2f1a6b
Revises: 461111b60977
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '7c4d9e2f1a6b'
down_revision = '461111b60977'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    memory_columns = {column['name'] for column in inspector.get_columns('memory')}

    additions = (
        sa.Column('node_type', sa.String(), nullable=False, server_default='fact'),
        sa.Column('entity_name', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('source_chat_id', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('meta', sa.JSON(), nullable=True),
    )
    for column in additions:
        if column.name not in memory_columns:
            op.add_column('memory', column)

    inspector.clear_cache()
    tables = inspector.get_table_names()
    if 'memory_edge' not in tables:
        op.create_table(
            'memory_edge',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('source_node_id', sa.String(), nullable=False),
            sa.Column('target_node_id', sa.String(), nullable=False),
            sa.Column('relation', sa.String(), nullable=False),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('meta', sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(['source_node_id'], ['memory.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['target_node_id'], ['memory.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_memory_edge_user_id', 'memory_edge', ['user_id'], unique=False)

    if 'memory_conflict' not in tables:
        op.create_table(
            'memory_conflict',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('node_a_id', sa.String(), nullable=False),
            sa.Column('node_b_id', sa.String(), nullable=False),
            sa.Column('conflict_type', sa.String(), nullable=False),
            sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('resolution', sa.String(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('resolved_at', sa.BigInteger(), nullable=True),
            sa.ForeignKeyConstraint(['node_a_id'], ['memory.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['node_b_id'], ['memory.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_memory_conflict_user_id',
            'memory_conflict',
            ['user_id'],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index('ix_memory_conflict_user_id', table_name='memory_conflict')
    op.drop_table('memory_conflict')
    op.drop_index('ix_memory_edge_user_id', table_name='memory_edge')
    op.drop_table('memory_edge')

    for column_name in (
        'meta',
        'is_active',
        'source_chat_id',
        'confidence',
        'entity_name',
        'node_type',
    ):
        op.drop_column('memory', column_name)
