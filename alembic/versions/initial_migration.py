"""initial migration

Revision ID: initial_revision
Revises: 
Create Date: 2026-07-16 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'initial_revision'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_name'), 'documents', ['name'], unique=False)

    # 2. Create document_versions table
    op.create_table(
        'document_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('document_id', sa.String(length=36), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_versions_document_id'), 'document_versions', ['document_id'], unique=False)

    # 3. Create document_nodes table
    op.create_table(
        'document_nodes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('node_uuid', sa.String(length=36), nullable=False),
        sa.Column('document_version_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.String(length=36), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['document_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_nodes_content_hash'), 'document_nodes', ['content_hash'], unique=False)
    op.create_index(op.f('ix_document_nodes_document_version_id'), 'document_nodes', ['document_version_id'], unique=False)
    op.create_index(op.f('ix_document_nodes_node_uuid'), 'document_nodes', ['node_uuid'], unique=False)
    op.create_index(op.f('ix_document_nodes_parent_id'), 'document_nodes', ['parent_id'], unique=False)
    op.create_index(op.f('ix_document_nodes_title'), 'document_nodes', ['title'], unique=False)

    # 4. Create selections table
    op.create_table(
        'selections',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('document_version_id', sa.String(length=36), nullable=False),
        sa.Column('selection_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_selections_document_version_id'), 'selections', ['document_version_id'], unique=False)
    op.create_index(op.f('ix_selections_name'), 'selections', ['name'], unique=False)
    op.create_index(op.f('ix_selections_selection_hash'), 'selections', ['selection_hash'], unique=False)

    # 5. Create selection_nodes table
    op.create_table(
        'selection_nodes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('selection_id', sa.String(length=36), nullable=False),
        sa.Column('node_id', sa.String(length=36), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['node_id'], ['document_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['selection_id'], ['selections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_selection_nodes_node_id'), 'selection_nodes', ['node_id'], unique=False)
    op.create_index(op.f('ix_selection_nodes_selection_id'), 'selection_nodes', ['selection_id'], unique=False)

    # 6. Create generations table
    op.create_table(
        'generations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('selection_id', sa.String(length=36), nullable=False),
        sa.Column('selection_hash', sa.String(length=64), nullable=False),
        sa.Column('llm_provider', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['selection_id'], ['selections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_generations_selection_id'), 'generations', ['selection_id'], unique=False)
    op.create_index(op.f('ix_generations_selection_hash'), 'generations', ['selection_hash'], unique=False)
    op.create_index(op.f('ix_generations_status'), 'generations', ['status'], unique=False)

    # 7. Create generation_nodes table
    op.create_table(
        'generation_nodes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('generation_id', sa.String(length=36), nullable=False),
        sa.Column('node_id', sa.String(length=36), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['generation_id'], ['generations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['document_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_generation_nodes_generation_id'), 'generation_nodes', ['generation_id'], unique=False)
    op.create_index(op.f('ix_generation_nodes_node_id'), 'generation_nodes', ['node_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_generation_nodes_node_id'), table_name='generation_nodes')
    op.drop_index(op.f('ix_generation_nodes_generation_id'), table_name='generation_nodes')
    op.drop_table('generation_nodes')
    op.drop_index(op.f('ix_generations_status'), table_name='generations')
    op.drop_index(op.f('ix_generations_selection_hash'), table_name='generations')
    op.drop_index(op.f('ix_generations_selection_id'), table_name='generations')
    op.drop_table('generations')
    op.drop_index(op.f('ix_selection_nodes_selection_id'), table_name='selection_nodes')
    op.drop_index(op.f('ix_selection_nodes_node_id'), table_name='selection_nodes')
    op.drop_table('selection_nodes')
    op.drop_index(op.f('ix_selections_selection_hash'), table_name='selections')
    op.drop_index(op.f('ix_selections_name'), table_name='selections')
    op.drop_index(op.f('ix_selections_document_version_id'), table_name='selections')
    op.drop_table('selections')
    op.drop_index(op.f('ix_document_nodes_title'), table_name='document_nodes')
    op.drop_index(op.f('ix_document_nodes_parent_id'), table_name='document_nodes')
    op.drop_index(op.f('ix_document_nodes_node_uuid'), table_name='document_nodes')
    op.drop_index(op.f('ix_document_nodes_document_version_id'), table_name='document_nodes')
    op.drop_index(op.f('ix_document_nodes_content_hash'), table_name='document_nodes')
    op.drop_table('document_nodes')
    op.drop_index(op.f('ix_document_versions_document_id'), table_name='document_versions')
    op.drop_table('document_versions')
    op.drop_index(op.f('ix_documents_name'), table_name='documents')
    op.drop_table('documents')
