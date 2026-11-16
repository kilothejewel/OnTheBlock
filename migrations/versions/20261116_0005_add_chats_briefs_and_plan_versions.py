"""add chats briefs and plan versions

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-16 15:49:09.179745

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Chats, their messages, Brief versions and Plan versions (#88); itineraries can point at a Plan version."""
    op.create_table('chats',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('city', sa.String(length=40), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('chats', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_chats_user_id'), ['user_id'], unique=False)

    op.create_table('briefs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('chat_id', sa.String(length=36), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['chat_id'], ['chats.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('chat_id', 'version', name='uq_briefs_chat_version')
    )
    with op.batch_alter_table('briefs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_briefs_chat_id'), ['chat_id'], unique=False)

    op.create_table('chat_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('chat_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['chat_id'], ['chats.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_chat_messages_chat_id'), ['chat_id'], unique=False)

    op.create_table('plan_versions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('chat_id', sa.String(length=36), nullable=False),
    sa.Column('brief_version', sa.Integer(), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('trace_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['chat_id'], ['chats.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('plan_versions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_plan_versions_chat_id'), ['chat_id'], unique=False)

    with op.batch_alter_table('itineraries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plan_version_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('mode', sa.String(length=10), nullable=True))
        batch_op.create_foreign_key('fk_itineraries_plan_version_id', 'plan_versions', ['plan_version_id'], ['id'], ondelete='SET NULL')



def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('itineraries', schema=None) as batch_op:
        batch_op.drop_constraint('fk_itineraries_plan_version_id', type_='foreignkey')
        batch_op.drop_column('mode')
        batch_op.drop_column('plan_version_id')

    with op.batch_alter_table('plan_versions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_plan_versions_chat_id'))

    op.drop_table('plan_versions')
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chat_messages_chat_id'))

    op.drop_table('chat_messages')
    with op.batch_alter_table('briefs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_briefs_chat_id'))

    op.drop_table('briefs')
    with op.batch_alter_table('chats', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chats_user_id'))

    op.drop_table('chats')
